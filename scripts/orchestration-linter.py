#!/usr/bin/env python3
"""
Lint orchestrator skill and agent files for convention compliance. Generates
ORCHESTRATION_FLOW.md as a side effect.

Validates these conventions in skills/*/SKILL.md:

  Sections:       ## headers (e.g., "## Phase 2: Test Curation")
  Steps:          ### N. headers, sequential per section (e.g., "### 1. Dequeue")
  Agents:         **agent-name** agent (must exist in agents/)
  Conditionals:   - If **condition** then **action**.
  Loop start:     **Begin loop.** (before first loop step)
  Loop end:       **Loop back to step N.** (after last loop step, paired with Begin)
  Scripts:        ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/ prefix (no hardcoded or bare paths)

Validates these conventions in agents/*.md:

  Frontmatter:    name, description required (shared with skills)
  Conditionals:   - If **condition** then **action**. (shared with skills)
  Scripts:        ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/ prefix (shared with skills)
  Input:          ## Input section with - **snake_case_key**: description parameters
  Output:         ## Output section with - **snake_case_key**: description parameters

Rules (grouped by domain):

  Structure (OL1xx):
  OL101  Step header format (### N. not ## Step N)
  OL102  Non-sequential step numbering
  OL103  Step header missing title
  OL104  SKILL.md exceeds 500 lines (progressive disclosure)
  OL105  Unpaired loop markers
  OL106  Loop back target mismatch

  References (OL2xx):
  OL201  Agent not found in agents/
  OL202  Skill not found in skills/
  OL203  Script file not found on disk

  Conventions (OL3xx):
  OL301  Conditional uses -> instead of 'then'
  OL302  Conditional has bold 'If' keyword
  OL303  Conditional missing bold condition/action
  OL304  Hardcoded .claude/plugins/ path
  OL305  Bare scripts/ path without variable prefix

  Schema (OL4xx):
  OL401  Missing required frontmatter field (name, description)
  OL402  Malformed YAML frontmatter
  OL403  Agent missing ## Input section
  OL404  Agent missing ## Output section
  OL405  Agent Input/Output parameter not in standard format

  Directory (OL5xx):
  OL501  Non-executable file in scripts/ (only .py, .sh, .js allowed)
  OL502  Non-documentation file in references/ (only .md allowed)

Usage:
  python scripts/orchestration-linter.py                # lint + print flow
  python scripts/orchestration-linter.py --write        # lint + write ORCHESTRATION_FLOW.md
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "yoink"
SKILLS_DIR = PLUGIN_DIR / "skills"
AGENTS_DIR = PLUGIN_DIR / "agents"
OUTPUT_FILE = REPO_ROOT / "ORCHESTRATION_FLOW.md"

ORCHESTRATOR_COMMANDS = ["setup", "test-curate", "decompose", "yoink", "yoink-loop"]

BEGIN_LOOP_PATTERN = re.compile(r"^\*\*Begin loop\.\*\*", re.MULTILINE)
LOOP_BACK_PATTERN = re.compile(r"^\*\*Loop back to step (\d+)\.\*\*", re.MULTILINE)
# Use [ \t] (not \s) after the dot to avoid matching across newlines.
STEP_HEADER_PATTERN = re.compile(r"^###\s+(\d+)\.[ \t]+(.*)", re.MULTILINE)
SECTION_HEADER_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)
AGENT_PATTERN = re.compile(r"\*\*(\S+?)\*\*\s+agent")
# Convention: - If **condition** then **action**.
CONDITIONAL_PATTERN = re.compile(
    r"[-*]\s+If\s+\*\*(.+?)\*\*\s+then\s+\*\*(.+?)\*\*", re.MULTILINE
)
# Match script invocations inside bash code blocks.
# Convention: plugin scripts use ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/.
PLUGIN_PATH_VAR = r"\$\{(?:CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR)\}"
SKILL_INVOKE_PATTERN = re.compile(r"Invoke\s+`?/(\S+?)`?\s")

PLUGIN_PATH_VAR_CAPTURING = r"\$\{(CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR)\}"

SCRIPT_PATTERNS = [
    # uv run python ${CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR}/scripts/foo.py subcommand
    re.compile(
        rf"uv run python {PLUGIN_PATH_VAR_CAPTURING}/(scripts/\S+\.py)(?:\s+(\w+))?"
    ),
    # uv run ${CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR}/foo.py (no "python" prefix)
    re.compile(rf"uv run {PLUGIN_PATH_VAR_CAPTURING}/(\S+\.py)"),
    # "${CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR}/scripts/foo.sh" (shell scripts, possibly quoted)
    re.compile(rf"{PLUGIN_PATH_VAR_CAPTURING}/(scripts/\S+\.sh)"),
    # uv run pytest (external tools, not plugin scripts)
    re.compile(r"uv run (pytest)\b"),
]

CODE_BLOCK_PATTERN = re.compile(r"```(?:bash|!)\n(.*?)```", re.DOTALL)

StepType = Literal["skill", "agent", "inline"]
DetailKind = Literal["agent", "runs", "conditional"]


class LintRule(StrEnum):
    # Structure (OL1xx)
    STEP_HEADER_FORMAT = "OL101"
    STEP_NUMBERING = "OL102"
    STEP_MISSING_TITLE = "OL103"
    SKILL_TOO_LONG = "OL104"
    UNPAIRED_LOOP = "OL105"
    LOOP_TARGET_MISMATCH = "OL106"
    # References (OL2xx)
    AGENT_NOT_FOUND = "OL201"
    SKILL_NOT_FOUND = "OL202"
    SCRIPT_NOT_FOUND = "OL203"
    # Conventions (OL3xx)
    CONDITIONAL_ARROW = "OL301"
    CONDITIONAL_BOLD_IF = "OL302"
    CONDITIONAL_UNBOLDED = "OL303"
    HARDCODED_PATH = "OL304"
    BARE_SCRIPT_PATH = "OL305"
    # Schema (OL4xx)
    FRONTMATTER_MISSING_FIELD = "OL401"
    FRONTMATTER_MALFORMED = "OL402"
    AGENT_MISSING_INPUT = "OL403"
    AGENT_MISSING_OUTPUT = "OL404"
    AGENT_PARAM_FORMAT = "OL405"
    # Directory (OL5xx)
    NON_EXECUTABLE_IN_SCRIPTS = "OL501"
    NON_DOCS_IN_REFERENCES = "OL502"


@dataclass
class LintWarning:
    rule: LintRule
    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"  {self.file}:{self.line}: {self.rule.value} {self.message}"


@dataclass
class StepDetail:
    kind: DetailKind
    label: str


@dataclass
class Conditional:
    condition: str
    action: str


@dataclass
class Step:
    header: str
    body: str
    num: int
    step_type: StepType
    # Set when step_type == "skill"; None otherwise.
    skill_name: str | None = None
    # Set when step_type == "agent"; None otherwise.
    agent_name: str | None = None
    conditionals: list[Conditional] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    details: list[StepDetail] = field(default_factory=list)


@dataclass
class Section:
    title: str | None
    steps: list[Step]
    loop_start: int | None = None
    loop_target: int | None = None


@dataclass
class SkillData:
    content: str
    sections: list[Section]
    argument_hint: str | None


@dataclass
class AgentData:
    name: str
    description: str
    input_keys: list[str]
    output_keys: list[str]


@dataclass
class LineRule:
    rule: LintRule
    pattern: re.Pattern[str]
    message: str
    exclude: re.Pattern[str] | None = None


# Convention: - **snake_case_key**: Description
AGENT_PARAM_PATTERN = re.compile(r"^[-*]\s+\*\*(\w+)\*\*:\s+\S", re.MULTILINE)

FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)^---\n", re.DOTALL | re.MULTILINE)


def parse_frontmatter(
    content: str, filename: str | None = None
) -> tuple[dict[str, Any], list[LintWarning]]:
    """Parse YAML frontmatter from a markdown file.

    Returns (parsed_dict, warnings). When filename is provided, malformed
    frontmatter produces an OL402 warning instead of silently returning {}.
    """
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}, []
    try:
        parsed = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        warning = (
            [
                LintWarning(
                    LintRule.FRONTMATTER_MALFORMED,
                    filename,
                    1,
                    f"Malformed YAML frontmatter: {exc}",
                )
            ]
            if filename
            else []
        )
        return {}, warning
    if not isinstance(parsed, dict):
        warning = (
            [
                LintWarning(
                    LintRule.FRONTMATTER_MALFORMED,
                    filename,
                    1,
                    f"Frontmatter must be a YAML mapping, got {type(parsed).__name__}",
                )
            ]
            if filename
            else []
        )
        return {}, warning
    return parsed, []


def _strip_frontmatter(content: str) -> str:
    """Return content with YAML frontmatter removed."""
    return FRONTMATTER_PATTERN.sub("", content, count=1)


def _extract_section_text(content: str, section_name: str) -> str | None:
    """Extract the body text of a ## section by name, up to the next ## header."""
    pattern = re.compile(
        rf"^##\s+{re.escape(section_name)}\s*$\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(1) if match else None


def _extract_param_keys(section_text: str) -> list[str]:
    """Extract **key** names from bullet lines in a section."""
    return AGENT_PARAM_PATTERN.findall(section_text)


def parse_agents() -> dict[str, AgentData]:
    """Read agent files and return {name: AgentData}."""
    agents: dict[str, AgentData] = {}
    if not AGENTS_DIR.exists():
        return agents
    for agent_file in sorted(AGENTS_DIR.glob("*.md")):
        content = agent_file.read_text()
        frontmatter, _ = parse_frontmatter(content)
        name = frontmatter.get("name")
        if not name:
            continue
        description = frontmatter.get("description", "")

        input_text = _extract_section_text(content, "Input")
        output_text = _extract_section_text(content, "Output")

        agents[name] = AgentData(
            name=name,
            description=description,
            input_keys=_extract_param_keys(input_text) if input_text else [],
            output_keys=_extract_param_keys(output_text) if output_text else [],
        )
    return agents


def _format_script_label(groups: tuple[str | None, ...]) -> str:
    """Format a script label from regex match groups.

    Handles three match shapes:
      (tool,)                        -> "pytest"
      (path_var, script_path)        -> "${CLAUDE_PLUGIN_ROOT}/scripts/foo.py"
      (path_var, script_path, subcmd) -> "${CLAUDE_PLUGIN_ROOT}/scripts/foo.py dequeue"
    """
    if len(groups) == 1:
        return groups[0] or ""
    if len(groups) == 2:
        path_var, script_path = groups
        return f"${{{path_var}}}/{script_path}"
    path_var, script_path, subcommand = groups
    label = f"${{{path_var}}}/{script_path}"
    if subcommand:
        label = f"{label} {subcommand}"
    return label


def _resolve_script_path(path_var: str, script_path: str, command_name: str) -> Path:
    """Resolve a script variable reference to an absolute path."""
    if path_var == "CLAUDE_PLUGIN_ROOT":
        return PLUGIN_DIR / script_path
    # CLAUDE_SKILL_DIR -> skills/<command_name>/
    return SKILLS_DIR / command_name / script_path


# --- Shared lint checks ---


def lint_frontmatter(
    filename: str, frontmatter: dict[str, Any], required_fields: list[str]
) -> list[LintWarning]:
    """OL401: Check that required frontmatter fields are present."""
    warnings: list[LintWarning] = []
    for field_name in required_fields:
        if field_name not in frontmatter:
            warnings.append(
                LintWarning(
                    LintRule.FRONTMATTER_MISSING_FIELD,
                    filename,
                    1,
                    f"Missing required frontmatter field: '{field_name}'",
                )
            )
    return warnings


LINE_RULES: list[LineRule] = [
    # Structure
    LineRule(
        LintRule.STEP_HEADER_FORMAT,
        re.compile(r"^##\s+Step\s+\d"),
        "Use '### N. Title' for steps, not '## Step N'.",
    ),
    LineRule(
        LintRule.STEP_MISSING_TITLE,
        re.compile(r"^###\s+\d+\.\s*$"),
        "Step is missing a title. Convention: '### N. Descriptive title'.",
    ),
    # Conventions
    LineRule(
        LintRule.CONDITIONAL_ARROW,
        re.compile(r"^[-*]\s+If\s+\*\*.+\*\*\s*(?:\u2192|->)"),
        "Use 'then' instead of '->'. Convention: '- If **condition** then **action**'.",
    ),
    LineRule(
        LintRule.CONDITIONAL_BOLD_IF,
        re.compile(r"^[-*]\s+\*\*If\s+"),
        "'If' should not be bold. Convention: '- If **condition** then **action**'.",
    ),
    LineRule(
        LintRule.CONDITIONAL_UNBOLDED,
        re.compile(r"^[-*]\s+[Ii]f\s+"),
        "Condition and action must be bold. Convention: '- If **condition** then **action**'.",
        exclude=CONDITIONAL_PATTERN,
    ),
    LineRule(
        LintRule.HARDCODED_PATH,
        re.compile(r"\.claude/plugins/yoink/\S+\.(py|sh)"),
        "Use ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/ instead of hardcoded plugin path.",
    ),
    LineRule(
        LintRule.BARE_SCRIPT_PATH,
        re.compile(
            r"(?<!\{CLAUDE_PLUGIN_ROOT\}/)(?<!\{CLAUDE_SKILL_DIR\}/)scripts/\S+\.(py|sh)"
        ),
        "Plugin scripts should use ${CLAUDE_PLUGIN_ROOT}/scripts/ or ${CLAUDE_SKILL_DIR}/scripts/, "
        "not bare 'scripts/' paths.",
        exclude=re.compile(r"\$\{CLAUDE_(?:PLUGIN_ROOT|SKILL_DIR)\}/scripts/"),
    ),
]


def lint_line_rules(filename: str, lines: list[str]) -> list[LintWarning]:
    """Apply all declarative single-line lint rules."""
    warnings: list[LintWarning] = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for rule in LINE_RULES:
            if rule.pattern.search(stripped):
                if rule.exclude and rule.exclude.search(stripped):
                    continue
                warnings.append(
                    LintWarning(
                        rule.rule, filename, i, f"{rule.message} Found: {stripped}"
                    )
                )
    return warnings


def lint_step_numbering(filename: str, lines: list[str]) -> list[LintWarning]:
    """OL102: Check step numbering is sequential within each section."""
    warnings: list[LintWarning] = []
    section_steps: list[int] = []
    current_section_start = 0
    for i, line in enumerate(lines, 1):
        if re.match(r"^##\s+", line) and not re.match(r"^###", line):
            warnings.extend(
                _check_step_sequence(filename, section_steps, current_section_start)
            )
            section_steps = []
            current_section_start = i
        step_match = re.match(r"^###\s+(\d+)\.", line)
        if step_match:
            section_steps.append(int(step_match.group(1)))
    warnings.extend(
        _check_step_sequence(filename, section_steps, current_section_start)
    )
    return warnings


def lint_script_existence(
    filename: str,
    lines: list[str],
    body: str,
    command_name: str | None = None,
) -> list[LintWarning]:
    """OL203: Check that referenced script files exist on disk.

    When command_name is provided (skill context), both CLAUDE_PLUGIN_ROOT and
    CLAUDE_SKILL_DIR are resolved. When None (agent context), only
    CLAUDE_PLUGIN_ROOT references are checked.
    """
    warnings: list[LintWarning] = []
    for code_block in CODE_BLOCK_PATTERN.findall(body):
        for pattern in SCRIPT_PATTERNS:
            for match in pattern.finditer(code_block):
                groups = match.groups()
                # External tools (single capture group, e.g. pytest) — skip
                if len(groups) < 2:
                    continue
                path_var = groups[0]
                script_path = groups[1]
                if not path_var or not script_path:
                    continue
                # Agents can only resolve CLAUDE_PLUGIN_ROOT (no skill dir context)
                if command_name is None and path_var != "CLAUDE_PLUGIN_ROOT":
                    continue
                resolved = _resolve_script_path(
                    path_var, script_path, command_name or ""
                )
                if not resolved.exists():
                    line_num = next(
                        (i for i, line in enumerate(lines, 1) if script_path in line),
                        0,
                    )
                    warnings.append(
                        LintWarning(
                            LintRule.SCRIPT_NOT_FOUND,
                            filename,
                            line_num,
                            f"Script not found: ${{{path_var}}}/{script_path} "
                            f"(resolved to {resolved.relative_to(REPO_ROOT)})",
                        )
                    )
    return warnings


EXECUTABLE_EXTENSIONS = {".py", ".sh", ".js"}
SKILL_MD_MAX_LINES = 500


def lint_skill_directory(skill_dir: Path) -> list[LintWarning]:
    """OL104/OL501/OL502: Check skill directory structure per progressive disclosure spec."""
    warnings: list[LintWarning] = []
    skill_name = skill_dir.name
    filename = f"skills/{skill_name}/SKILL.md"

    # OL104: SKILL.md should be under 500 lines
    skill_file = skill_dir / "SKILL.md"
    if skill_file.exists():
        line_count = len(skill_file.read_text().splitlines())
        if line_count > SKILL_MD_MAX_LINES:
            warnings.append(
                LintWarning(
                    LintRule.SKILL_TOO_LONG,
                    filename,
                    1,
                    f"SKILL.md is {line_count} lines (max {SKILL_MD_MAX_LINES}). "
                    "Move detailed reference material to references/ or assets/",
                )
            )

    # OL501: scripts/ should only contain executable files
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        for file_path in sorted(scripts_dir.rglob("*")):
            if file_path.is_file() and file_path.suffix not in EXECUTABLE_EXTENSIONS:
                warnings.append(
                    LintWarning(
                        LintRule.NON_EXECUTABLE_IN_SCRIPTS,
                        f"skills/{skill_name}/scripts/{file_path.name}",
                        1,
                        "Non-executable file in scripts/. "
                        "Move to assets/ (templates/resources) or references/ (documentation)",
                    )
                )

    # OL502: references/ should only contain documentation (.md)
    references_dir = skill_dir / "references"
    if references_dir.exists():
        for file_path in sorted(references_dir.rglob("*")):
            if file_path.is_file() and file_path.suffix != ".md":
                warnings.append(
                    LintWarning(
                        LintRule.NON_DOCS_IN_REFERENCES,
                        f"skills/{skill_name}/references/{file_path.name}",
                        1,
                        "Non-documentation file in references/. "
                        "Only .md files belong here. Move to assets/ or scripts/",
                    )
                )

    return warnings


# --- Linting ---


def lint_command(
    command_name: str, content: str, known_agents: set[str]
) -> list[LintWarning]:
    """Check a skill file follows conventions."""
    warnings: list[LintWarning] = []
    filename = f"skills/{command_name}/SKILL.md"
    lines = content.split("\n")
    frontmatter, fm_warnings = parse_frontmatter(content, filename)
    warnings.extend(fm_warnings)
    body = _strip_frontmatter(content)

    # OL401: Required frontmatter fields
    warnings.extend(lint_frontmatter(filename, frontmatter, ["name", "description"]))

    # Declarative single-line rules (OL101, OL103, OL301-OL305)
    warnings.extend(lint_line_rules(filename, lines))

    # OL102: Step numbering
    warnings.extend(lint_step_numbering(filename, lines))

    # OL201: Agent references must point to known agents
    for match in AGENT_PATTERN.finditer(body):
        agent_name = match.group(1)
        if agent_name not in known_agents:
            line_num = next(
                (i for i, line in enumerate(lines, 1) if f"**{agent_name}**" in line),
                0,
            )
            warnings.append(
                LintWarning(
                    LintRule.AGENT_NOT_FOUND,
                    filename,
                    line_num,
                    f"Agent '{agent_name}' referenced but not found in agents/",
                )
            )

    # OL202: Skill invocations must point to existing skills
    for match in SKILL_INVOKE_PATTERN.finditer(body):
        skill_name = match.group(1)
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_file.exists():
            line_num = next(
                (i for i, line in enumerate(lines, 1) if f"/{skill_name}" in line),
                0,
            )
            warnings.append(
                LintWarning(
                    LintRule.SKILL_NOT_FOUND,
                    filename,
                    line_num,
                    f"Skill '/{skill_name}' invoked but not found in skills/",
                )
            )

    # OL105/OL106: Loop marker checks
    begin_loops = list(BEGIN_LOOP_PATTERN.finditer(body))
    loop_backs = list(LOOP_BACK_PATTERN.finditer(body))

    # OL105: Loop markers must be paired
    if len(begin_loops) != len(loop_backs):
        for i, line in enumerate(lines, 1):
            if "**Begin loop.**" in line or "**Loop back to step" in line:
                warnings.append(
                    LintWarning(
                        LintRule.UNPAIRED_LOOP,
                        filename,
                        i,
                        f"Unpaired loop marker: found {len(begin_loops)} "
                        f"'Begin loop' and {len(loop_backs)} 'Loop back'. "
                        "They must be paired.",
                    )
                )
                break

    # OL106: Loop back target must match the first step after Begin loop
    for begin, back in zip(begin_loops, loop_backs, strict=False):
        first_step_after = STEP_HEADER_PATTERN.search(body, begin.end())
        if first_step_after:
            expected_target = int(first_step_after.group(1))
            actual_target = int(back.group(1))
            if actual_target != expected_target:
                line_num = next(
                    (
                        i
                        for i, line in enumerate(lines, 1)
                        if f"**Loop back to step {actual_target}.**" in line
                    ),
                    0,
                )
                warnings.append(
                    LintWarning(
                        LintRule.LOOP_TARGET_MISMATCH,
                        filename,
                        line_num,
                        f"Loop back targets step {actual_target} but the first "
                        f"step after 'Begin loop' is step {expected_target}",
                    )
                )

    # OL203: Script files must exist on disk
    warnings.extend(lint_script_existence(filename, lines, body, command_name))

    return warnings


def _check_step_sequence(
    filename: str,
    step_numbers: list[int],
    section_start_line: int,
) -> list[LintWarning]:
    if not step_numbers:
        return []
    expected = list(range(1, len(step_numbers) + 1))
    if step_numbers != expected:
        return [
            LintWarning(
                LintRule.STEP_NUMBERING,
                filename,
                section_start_line,
                f"Steps should be numbered 1, 2, 3... but found {step_numbers}",
            )
        ]
    return []


def lint_agent(agent_file: Path) -> list[LintWarning]:
    """Check an agent file follows conventions."""
    warnings: list[LintWarning] = []
    filename = f"agents/{agent_file.name}"
    content = agent_file.read_text()
    lines = content.split("\n")
    frontmatter, fm_warnings = parse_frontmatter(content, filename)
    warnings.extend(fm_warnings)

    # OL401: Required frontmatter fields
    warnings.extend(lint_frontmatter(filename, frontmatter, ["name", "description"]))

    # Declarative single-line rules (OL101, OL103, OL301-OL305)
    warnings.extend(lint_line_rules(filename, lines))

    # OL102: Step numbering
    warnings.extend(lint_step_numbering(filename, lines))

    # OL203: Script files must exist on disk (agent context — no skill dir)
    body = _strip_frontmatter(content)
    warnings.extend(lint_script_existence(filename, lines, body))

    input_text = _extract_section_text(content, "Input")
    output_text = _extract_section_text(content, "Output")

    # OL403: Agent must have ## Input section
    if input_text is None:
        warnings.append(
            LintWarning(
                LintRule.AGENT_MISSING_INPUT,
                filename,
                1,
                "Agent is missing a '## Input' section",
            )
        )

    # OL404: Agent must have ## Output section
    if output_text is None:
        warnings.append(
            LintWarning(
                LintRule.AGENT_MISSING_OUTPUT,
                filename,
                1,
                "Agent is missing a '## Output' section",
            )
        )

    # OL405: Parameters in Input/Output must use - **snake_case_key**: description
    for section_name, section_text in [("Input", input_text), ("Output", output_text)]:
        if section_text is None:
            continue
        # Find the starting line of this section in the file
        section_start = next(
            (
                i
                for i, line in enumerate(lines, 1)
                if re.match(rf"^##\s+{re.escape(section_name)}\s*$", line)
            ),
            0,
        )
        section_lines = section_text.split("\n")
        for offset, line in enumerate(section_lines):
            stripped = line.strip()
            # Skip empty lines, non-bullet lines, and conditional "If" lines
            if not stripped or not re.match(r"^[-*]\s+", stripped):
                continue
            if re.match(r"^[-*]\s+If\s+\*\*", stripped):
                continue
            # Must match: - **snake_case_key**: description
            if not re.match(r"^[-*]\s+\*\*\w+\*\*:\s+\S", stripped):
                warnings.append(
                    LintWarning(
                        LintRule.AGENT_PARAM_FORMAT,
                        filename,
                        section_start + offset,
                        f"Parameter in {section_name} must use '- **snake_case_key**: description'. "
                        f"Found: {stripped}",
                    )
                )

    return warnings


# --- Parsing ---


def extract_sections(content: str) -> list[Section]:
    """Split content into phases/sections, then extract steps from each."""
    content = re.sub(
        r"^---\n.*?^---\n", "", content, count=1, flags=re.DOTALL | re.MULTILINE
    )

    section_matches = list(SECTION_HEADER_PATTERN.finditer(content))
    sections: list[Section] = []

    if not section_matches:
        parsed = _parse_block(content)
        if parsed.steps:
            sections.append(parsed)
        return sections

    # Preamble before first ## header
    preamble = content[: section_matches[0].start()].strip()
    if preamble:
        parsed = _parse_block(preamble)
        if parsed.steps:
            sections.append(parsed)

    for i, match in enumerate(section_matches):
        title = match.group(1).strip()
        start = match.end()
        end = (
            section_matches[i + 1].start()
            if i + 1 < len(section_matches)
            else len(content)
        )
        parsed = _parse_block(content[start:end])
        parsed.title = title
        if parsed.steps:
            sections.append(parsed)

    return sections


def _parse_block(block: str) -> Section:
    """Extract steps and loop markers from a block of text."""
    section = Section(title=None, steps=[])

    # Detect loop markers
    begin_match = BEGIN_LOOP_PATTERN.search(block)
    back_match = LOOP_BACK_PATTERN.search(block)

    if begin_match and back_match:
        section.loop_target = int(back_match.group(1))
        first_step = STEP_HEADER_PATTERN.search(block, begin_match.end())
        if first_step:
            section.loop_start = int(first_step.group(1))

    # Extract ### N. steps
    step_matches = list(STEP_HEADER_PATTERN.finditer(block))
    for idx, match in enumerate(step_matches):
        start = match.start()
        end = (
            step_matches[idx + 1].start() if idx + 1 < len(step_matches) else len(block)
        )
        step_body = block[start:end]

        # Don't include loop-back marker in step body
        if back_match and start <= back_match.start() < end:
            step_body = block[start : back_match.start()]

        step = _classify_step(match.group(0), step_body, int(match.group(1)))
        section.steps.append(step)

    return section


def _classify_step(header: str, body: str, step_num: int) -> Step:
    """Classify a step by its primary type and extract structured details."""
    agent_match = AGENT_PATTERN.search(body)
    skill_match = SKILL_INVOKE_PATTERN.search(body)

    step_type: StepType
    skill_name: str | None = None
    agent_name: str | None = None

    if skill_match:
        step_type = "skill"
        skill_name = skill_match.group(1)
    elif agent_match:
        step_type = "agent"
        agent_name = agent_match.group(1)
    else:
        step_type = "inline"

    conditionals = [
        Conditional(condition=cond.strip(), action=action.strip())
        for cond, action in CONDITIONAL_PATTERN.findall(body)
    ]

    scripts = _extract_scripts(body)

    return Step(
        header=header.strip(),
        body=body,
        num=step_num,
        step_type=step_type,
        skill_name=skill_name,
        agent_name=agent_name,
        conditionals=conditionals,
        scripts=scripts,
        details=_build_ordered_details(body, step_type, agent_name),
    )


def _build_ordered_details(
    body: str, step_type: StepType, agent_name: str | None
) -> list[StepDetail]:
    """Build detail items ordered by their position in the source text."""
    positioned: list[tuple[int, StepDetail]] = []

    if step_type == "agent" and agent_name is not None:
        agent_match = AGENT_PATTERN.search(body)
        if agent_match:
            positioned.append(
                (agent_match.start(), StepDetail("agent", f"agent: {agent_name}"))
            )

    for match in CONDITIONAL_PATTERN.finditer(body):
        condition = match.group(1).strip()
        action = match.group(2).strip()
        positioned.append(
            (match.start(), StepDetail("conditional", f"{condition} \u2192 {action}"))
        )

    # Scripts are extracted from code blocks; use code block position as anchor.
    seen_scripts: set[str] = set()
    for block_match in CODE_BLOCK_PATTERN.finditer(body):
        block_pos = block_match.start()
        block_text = block_match.group(1)
        for pattern in SCRIPT_PATTERNS:
            for match in pattern.finditer(block_text):
                label = _format_script_label(match.groups())
                if label not in seen_scripts:
                    seen_scripts.add(label)
                    positioned.append(
                        (
                            block_pos + match.start(),
                            StepDetail("runs", f"runs: {label}"),
                        )
                    )

    positioned.sort(key=lambda item: item[0])
    return [detail for _, detail in positioned]


def _extract_scripts(body: str) -> list[str]:
    """Extract unique script invocations from bash code blocks in step body."""
    code_blocks = CODE_BLOCK_PATTERN.findall(body)
    if not code_blocks:
        return []

    seen: set[str] = set()
    scripts: list[str] = []
    for block in code_blocks:
        for pattern in SCRIPT_PATTERNS:
            for match in pattern.finditer(block):
                label = _format_script_label(match.groups())
                if label not in seen:
                    seen.add(label)
                    scripts.append(label)
    return scripts


def _clean_label(header: str) -> str:
    label = re.sub(r"^###\s+\d+\.\s*", "", header)
    label = re.sub(r"\*\*", "", label)
    label = label.strip()
    if len(label) > 60:
        label = label[:57] + "..."
    return label or "(inline)"


# --- Rendering ---


def _agent_signature(agent_name: str, agent_data: dict[str, AgentData]) -> str:
    """Format an agent detail label with I/O signature if available."""
    if agent_name not in agent_data:
        return f"agent: {agent_name}"
    agent = agent_data[agent_name]
    input_sig = ", ".join(agent.input_keys) if agent.input_keys else ""
    label = f"agent: {agent_name}({input_sig})"
    if agent.output_keys:
        output_sig = ", ".join(agent.output_keys)
        label += f" \u2192 {output_sig}"
    return label


def render_section(
    section: Section,
    skill_data: dict[str, SkillData] | None = None,
    agent_data: dict[str, AgentData] | None = None,
    indent: str = "  ",
    expanding: frozenset[str] = frozenset(),
) -> list[str]:
    """Render a section with its steps and loop markers."""
    lines: list[str] = []

    if section.title:
        lines.append(f"{indent}[{section.title}]")

    has_loop = section.loop_start is not None and section.loop_target is not None

    for step in section.steps:
        in_loop = has_loop and step.num >= (section.loop_start or 0)
        connector = "\u2502 " if in_loop else ""

        # Loop open marker
        if has_loop and step.num == section.loop_start:
            lines.append(f"{indent}\u250c\u2500 loop")

        # Label with optional skill annotation
        label = _clean_label(step.header)
        if step.step_type == "skill":
            label += f" \u2192 /{step.skill_name}"
        lines.append(f"{indent}{connector}{step.num}. {label}")

        # Collect sub-lines in source order, enriching agent labels with I/O
        sub_lines: list[str] = []
        for detail in step.details:
            if detail.kind == "agent" and agent_data and step.agent_name:
                sub_lines.append(_agent_signature(step.agent_name, agent_data))
            else:
                sub_lines.append(detail.label)

        # Don't render sub-lines for skill steps (the expansion replaces them)
        if step.step_type != "skill":
            for j, sub in enumerate(sub_lines):
                is_last = j == len(sub_lines) - 1
                branch = "\u2514\u2500" if is_last else "\u251c\u2500"
                lines.append(f"{indent}{connector}   {branch} {sub}")

        # Expand nested skill inline
        if step.step_type == "skill" and skill_data and step.skill_name:
            skill_name = step.skill_name
            if skill_name in skill_data and skill_name not in expanding:
                nested_indent = indent + connector + "   "
                nested_expanding = expanding | {skill_name}
                nested_sections = skill_data[skill_name].sections
                if nested_sections:
                    for nested_section in nested_sections:
                        lines.extend(
                            render_section(
                                nested_section,
                                skill_data=skill_data,
                                agent_data=agent_data,
                                indent=nested_indent,
                                expanding=nested_expanding,
                            )
                        )
                else:
                    # Skill has no structured steps; extract scripts from raw content
                    raw_content = skill_data[skill_name].content
                    scripts = _extract_scripts(raw_content)
                    for j, script in enumerate(scripts):
                        is_last = j == len(scripts) - 1
                        branch = "\u2514\u2500" if is_last else "\u251c\u2500"
                        lines.append(f"{nested_indent}{branch} runs: {script}")

    # Loop close marker
    if has_loop:
        lines.append(f"{indent}\u2514\u2500 back to step {section.loop_target}")

    return lines


def render_command(
    command_name: str,
    content: str,
    skill_data: dict[str, SkillData] | None = None,
    agent_data: dict[str, AgentData] | None = None,
) -> list[str]:
    argument_hint = parse_frontmatter(content)[0].get("argument-hint")
    header = f"/{command_name} {argument_hint}" if argument_hint else f"/{command_name}"
    lines = [header]

    sections = extract_sections(content)
    if not sections:
        lines.append("  (no orchestration steps detected)")
        lines.append("")
        return lines

    for section in sections:
        lines.extend(
            render_section(section, skill_data=skill_data, agent_data=agent_data)
        )

    lines.append("")
    return lines


# --- Output ---


def load_all_skills() -> dict[str, SkillData]:
    """Pre-load all skills for nested expansion during rendering."""
    skill_data: dict[str, SkillData] = {}
    if not SKILLS_DIR.exists():
        return skill_data
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        content = skill_file.read_text()
        skill_data[skill_dir.name] = SkillData(
            content=content,
            sections=extract_sections(content),
            argument_hint=parse_frontmatter(content)[0].get("argument-hint"),
        )
    return skill_data


def generate_flow() -> str:
    agents = parse_agents()
    skill_data = load_all_skills()

    output_lines = [
        "# Orchestration Flow",
        "",
        "Auto-generated by `scripts/orchestration-linter.py`. Do not edit manually.",
        "",
    ]

    if agents:
        output_lines.append("## Agents")
        output_lines.append("")
        for name in sorted(agents):
            agent = agents[name]
            input_sig = ", ".join(agent.input_keys) if agent.input_keys else ""
            output_sig = ", ".join(agent.output_keys) if agent.output_keys else ""
            sig = f"({input_sig})"
            if output_sig:
                sig += f" \u2192 {output_sig}"
            output_lines.append(f"- **{name}**{sig}: {agent.description}")
        output_lines.append("")

    output_lines.append("## Skill Flows")
    output_lines.append("")
    output_lines.append("```")

    for command_name in ORCHESTRATOR_COMMANDS:
        skill_file = SKILLS_DIR / command_name / "SKILL.md"
        if not skill_file.exists():
            continue
        content = skill_file.read_text()
        output_lines.extend(
            render_command(
                command_name, content, skill_data=skill_data, agent_data=agents
            )
        )

    output_lines.append("```")
    output_lines.append("")

    return "\n".join(output_lines)


def run_lint(known_agents: set[str]) -> list[LintWarning]:
    all_warnings: list[LintWarning] = []
    for command_name in ORCHESTRATOR_COMMANDS:
        skill_file = SKILLS_DIR / command_name / "SKILL.md"
        if not skill_file.exists():
            continue
        content = skill_file.read_text()
        all_warnings.extend(lint_command(command_name, content, known_agents))
        all_warnings.extend(lint_skill_directory(skill_file.parent))
    # Lint agent files
    if AGENTS_DIR.exists():
        for agent_file in sorted(AGENTS_DIR.glob("*.md")):
            all_warnings.extend(lint_agent(agent_file))
    return all_warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lint orchestrator commands and generate flow visualization"
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write ORCHESTRATION_FLOW.md after linting",
    )
    args = parser.parse_args()

    agents = parse_agents()
    known_agent_names = set(agents.keys())

    # Linting is always the primary action
    warnings = run_lint(known_agent_names)
    if warnings:
        print(f"\u26a0\ufe0f  {len(warnings)} convention warning(s):")
        for warning in warnings:
            print(warning)
        print()
        sys.exit(1)

    print("\u2705 All commands follow conventions")

    # Flow visualization is a side effect
    flow = generate_flow()

    if args.write:
        OUTPUT_FILE.write_text(flow)
        print(f"\u2705 Wrote {OUTPUT_FILE.name}")
    else:
        print()
        print(flow)


if __name__ == "__main__":
    main()
