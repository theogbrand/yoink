#!/usr/bin/env python3
"""
Lint orchestrator skill and agent files for convention compliance. Generates
ORCHESTRATION_FLOW.md as a side effect.

Validates these conventions in skills/*/SKILL.md:

  Sections:       ## headers (e.g., "## Phase 2: Test Curation")
  Steps:          ### N. headers, sequential per section (e.g., "### 1. Dequeue")
  Substeps:       #### a. headers, rendered as nested flow items
  Agents:         **yoink:agent-name** agent (must exist in agents/)
  Skills:         /yoink:skill-name references for sub-skills
  Conditionals:   - If **condition** then **action**.
  Loop start:     **Begin loop.** (before first loop step)
  Loop end:       **Loop back to step N.** (after last loop step, paired with Begin)
  Scripts:        ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/ prefix (no hardcoded or bare paths)

Validates these conventions in agents/*.md:

  Frontmatter:    name, description required (shared with skills)
  Conditionals:   - If **condition** then **action**. (shared with skills)
  Scripts:        ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/ prefix (shared with skills)
  Input:          ## Input section with a JSON Schema code block (reference-only note required)
  Output:         ## Output section with a JSON Schema code block

  Input and Output both use JSON Schema code blocks for field definitions.
  Input includes a "reference only" note because the orchestrator may pass
  input in varying formats. Output is authoritative since agents control
  their own output.

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
  OL306  Skill reference missing required /yoink: prefix
  OL307  Agent reference missing required yoink: prefix

  Schema (OL4xx):
  OL401  Missing required frontmatter field (name, description)
  OL402  Malformed YAML frontmatter
  OL403  Agent missing ## Input section
  OL404  Agent missing ## Output section
  OL405  Agent Input missing JSON Schema or reference-only note
  OL406  Agent Output missing JSON Schema (```json block with type+description per field)
  OL408  Frontmatter name format (lowercase alphanumeric + hyphens, max 64 chars)
  OL409  Frontmatter name/description contains XML tags
  OL410  Frontmatter description exceeds 1024 characters

  Directory (OL5xx):
  OL501  Non-executable file in scripts/ (only .py, .sh, .js allowed)
  OL502  Non-documentation file in references/ (only .md allowed)

Usage:
  python scripts/orchestration-linter.py                # lint + print flow
  python scripts/orchestration-linter.py --write        # lint + write ORCHESTRATION_FLOW.md
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal, TypedDict

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "yoink"
SKILLS_DIR = PLUGIN_DIR / "skills"
AGENTS_DIR = PLUGIN_DIR / "agents"
OUTPUT_FILE = REPO_ROOT / "ORCHESTRATION_FLOW.md"

ORCHESTRATOR_COMMANDS = ["setup", "curate-tests", "decompose", "yoink", "yoink-loop"]

BEGIN_LOOP_PATTERN = re.compile(r"^\*\*Begin loop\.\*\*", re.MULTILINE)
LOOP_BACK_PATTERN = re.compile(r"^\*\*Loop back to step (\d+)\.\*\*", re.MULTILINE)
# Use [ \t] (not \s) after the dot to avoid matching across newlines.
STEP_HEADER_PATTERN = re.compile(r"^###\s+(\d+)\.[ \t]+(.*)", re.MULTILINE)
SUBSTEP_HEADER_PATTERN = re.compile(r"^####\s+([a-z])\.[ \t]+(.*)", re.MULTILINE)
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
INLINE_SKILL_REFERENCE_PATTERN = re.compile(r"`/([A-Za-z0-9:_-]+)`")

PLUGIN_PATH_VAR_CAPTURING = r"\$\{(CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR)\}"
YOINK_PREFIX = "yoink:"

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


class Frontmatter(TypedDict, total=False):
    name: str
    description: str


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
    SKILL_MISSING_PREFIX = "OL306"
    AGENT_MISSING_PREFIX = "OL307"
    # Schema (OL4xx)
    FRONTMATTER_MISSING_FIELD = "OL401"
    FRONTMATTER_MALFORMED = "OL402"
    AGENT_MISSING_INPUT = "OL403"
    AGENT_MISSING_OUTPUT = "OL404"
    AGENT_PARAM_FORMAT = "OL405"
    AGENT_OUTPUT_NOT_JSON_SCHEMA = "OL406"
    # Frontmatter values (OL4xx continued)
    # Spec: platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
    FRONTMATTER_NAME_FORMAT = "OL408"
    FRONTMATTER_XML_TAGS = "OL409"
    FRONTMATTER_DESCRIPTION_TOO_LONG = "OL410"
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
class Substep:
    marker: str
    header: str
    body: str
    kind: StepType
    skill_name: str | None = None
    agent_name: str | None = None
    conditionals: list[Conditional] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    details: list[StepDetail] = field(default_factory=list)


@dataclass
class _StepBase:
    header: str
    body: str
    num: int
    conditionals: list[Conditional] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    details: list[StepDetail] = field(default_factory=list)
    substeps: list[Substep] = field(default_factory=list)


@dataclass
class SkillStep(_StepBase):
    skill_name: str = ""


@dataclass
class AgentStep(_StepBase):
    agent_name: str = ""


@dataclass
class InlineStep(_StepBase):
    pass


Step = SkillStep | AgentStep | InlineStep


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


INPUT_REFERENCE_NOTE_PATTERN = re.compile(
    r">\s+\*\*Note:\*\*.*schema.*reference only", re.IGNORECASE
)

FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)^---\n", re.DOTALL | re.MULTILINE)


def parse_frontmatter(
    content: str, filename: str | None = None
) -> tuple[Frontmatter, list[LintWarning]]:
    """Parse YAML frontmatter from a markdown file.

    Returns (parsed_dict, warnings). When filename is provided, malformed
    frontmatter produces an OL402 warning instead of silently returning {}.
    """
    empty: Frontmatter = {}
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return empty, []
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
        return empty, warning
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
        return empty, warning
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
    """Extract top-level input field names from an Input JSON Schema block."""
    json_block_match = re.search(r"```json\n(.*?)```", section_text, re.DOTALL)
    if json_block_match is None:
        return []

    try:
        parsed_input_schema = json.loads(json_block_match.group(1))
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed_input_schema, dict):
        return []

    return [
        field_name
        for field_name, field_schema in parsed_input_schema.items()
        if isinstance(field_schema, dict)
    ]


def _extract_output_schema_keys(output_section_text: str) -> list[str]:
    """Extract top-level output field names from an Output JSON Schema block."""
    json_block_match = re.search(r"```json\n(.*?)```", output_section_text, re.DOTALL)
    if json_block_match is None:
        return []

    try:
        parsed_output_schema = json.loads(json_block_match.group(1))
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed_output_schema, dict):
        return []

    return [
        field_name
        for field_name, field_schema in parsed_output_schema.items()
        if isinstance(field_schema, dict)
    ]


def _has_yoink_prefix(reference_name: str) -> bool:
    return reference_name.startswith(YOINK_PREFIX)


def _strip_yoink_prefix(reference_name: str) -> str:
    if _has_yoink_prefix(reference_name):
        return reference_name[len(YOINK_PREFIX) :]
    return reference_name


def _format_skill_reference(skill_name: str) -> str:
    canonical_skill_name = _strip_yoink_prefix(skill_name)
    return f"/{YOINK_PREFIX}{canonical_skill_name}"


def _format_agent_reference(agent_name: str) -> str:
    return f"{YOINK_PREFIX}{_strip_yoink_prefix(agent_name)}"


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
        canonical_agent_name = _strip_yoink_prefix(name)
        description = frontmatter.get("description", "")

        input_text = _extract_section_text(content, "Input")
        output_text = _extract_section_text(content, "Output")

        agents[canonical_agent_name] = AgentData(
            name=canonical_agent_name,
            description=description,
            input_keys=_extract_param_keys(input_text) if input_text else [],
            output_keys=(
                _extract_output_schema_keys(output_text) if output_text else []
            ),
        )
    return agents


def _format_script_label(groups: tuple[str | None, ...]) -> str:
    """Format a script label from regex match groups.

    Handles three match shapes:
      (tool,)                        -> "pytest"
      (path_var, script_path)        -> "${CLAUDE_PLUGIN_ROOT}/scripts/foo.py"
      (path_var, script_path, subcmd) -> "${CLAUDE_PLUGIN_ROOT}/scripts/foo.py dequeue"
    """
    match groups:
        case (tool,):
            return tool or ""
        case (path_var, script_path):
            return f"${{{path_var}}}/{script_path}"
        case (path_var, script_path, subcommand):
            label = f"${{{path_var}}}/{script_path}"
            if subcommand:
                label = f"{label} {subcommand}"
            return label
        case _:
            return ""


def _resolve_script_path(path_var: str, script_path: str, command_name: str) -> Path:
    """Resolve a script variable reference to an absolute path."""
    if path_var == "CLAUDE_PLUGIN_ROOT":
        return PLUGIN_DIR / script_path
    # CLAUDE_SKILL_DIR -> skills/<command_name>/
    return SKILLS_DIR / command_name / script_path


# --- Shared lint checks ---


def lint_frontmatter(
    filename: str, frontmatter: Frontmatter, required_fields: list[str]
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


def lint_frontmatter_values(
    filename: str, frontmatter: Frontmatter
) -> list[LintWarning]:
    """OL408/OL409/OL410: Check frontmatter field values against the Agent Skills spec.

    Spec: platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
    """
    warnings: list[LintWarning] = []
    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")

    # OL408: name must be lowercase alphanumeric + hyphens, max 64 chars
    if name:
        if not FRONTMATTER_NAME_PATTERN.fullmatch(name):
            warnings.append(
                LintWarning(
                    LintRule.FRONTMATTER_NAME_FORMAT,
                    filename,
                    1,
                    f"Name must contain only lowercase letters, numbers, and hyphens "
                    f"(pattern: [a-z0-9-]+). Found: '{name}'",
                )
            )
        if len(name) > FRONTMATTER_NAME_MAX_LENGTH:
            warnings.append(
                LintWarning(
                    LintRule.FRONTMATTER_NAME_FORMAT,
                    filename,
                    1,
                    f"Name must be at most {FRONTMATTER_NAME_MAX_LENGTH} characters. "
                    f"Found: {len(name)} characters",
                )
            )

    # OL409: name and description must not contain XML-like tags
    for field_name, value in [("name", name), ("description", description)]:
        if value and XML_TAG_PATTERN.search(value):
            warnings.append(
                LintWarning(
                    LintRule.FRONTMATTER_XML_TAGS,
                    filename,
                    1,
                    f"'{field_name}' must not contain XML tags (they break system prompt "
                    f"injection). Found in: '{value[:80]}'",
                )
            )

    # OL410: description must not exceed 1024 characters
    if description and len(description) > FRONTMATTER_DESCRIPTION_MAX_LENGTH:
        warnings.append(
            LintWarning(
                LintRule.FRONTMATTER_DESCRIPTION_TOO_LONG,
                filename,
                1,
                f"Description must be at most {FRONTMATTER_DESCRIPTION_MAX_LENGTH} characters. "
                f"Found: {len(description)} characters",
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


# Frontmatter value constraints from the Anthropic Agent Skills spec:
# platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
FRONTMATTER_NAME_PATTERN = re.compile(r"^[a-z0-9-]+$")
FRONTMATTER_NAME_MAX_LENGTH = 64
FRONTMATTER_DESCRIPTION_MAX_LENGTH = 1024
XML_TAG_PATTERN = re.compile(r"<[A-Za-z][^>]*>")

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
            if "__pycache__" in file_path.parts:
                continue
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
    # OL408/OL409/OL410: Frontmatter value constraints
    warnings.extend(lint_frontmatter_values(filename, frontmatter))
    # Declarative single-line rules (OL101, OL103, OL301-OL305)
    warnings.extend(lint_line_rules(filename, lines))

    # OL102: Step numbering
    warnings.extend(lint_step_numbering(filename, lines))

    # OL201: Agent references must point to known agents
    for match in AGENT_PATTERN.finditer(body):
        referenced_agent_name = match.group(1)
        canonical_agent_name = _strip_yoink_prefix(referenced_agent_name)
        line_num = next(
            (
                i
                for i, line in enumerate(lines, 1)
                if f"**{referenced_agent_name}**" in line
            ),
            0,
        )
        if not _has_yoink_prefix(referenced_agent_name):
            warnings.append(
                LintWarning(
                    LintRule.AGENT_MISSING_PREFIX,
                    filename,
                    line_num,
                    f"Agent references must use the '{YOINK_PREFIX}' prefix. "
                    f"Found '**{referenced_agent_name}** agent'.",
                )
            )
        if canonical_agent_name not in known_agents:
            line_num = next(
                (
                    i
                    for i, line in enumerate(lines, 1)
                    if f"**{referenced_agent_name}**" in line
                ),
                line_num,
            )
            warnings.append(
                LintWarning(
                    LintRule.AGENT_NOT_FOUND,
                    filename,
                    line_num,
                    f"Agent '{referenced_agent_name}' referenced but not found in agents/",
                )
            )

    # OL202: Skill invocations must point to existing skills
    seen_skill_references: set[tuple[str, int]] = set()
    for pattern in (SKILL_INVOKE_PATTERN, INLINE_SKILL_REFERENCE_PATTERN):
        for match in pattern.finditer(body):
            referenced_skill_name = match.group(1)
            line_num = next(
                (
                    i
                    for i, line in enumerate(lines, 1)
                    if f"/{referenced_skill_name}" in line
                ),
                0,
            )
            if (referenced_skill_name, line_num) in seen_skill_references:
                continue
            seen_skill_references.add((referenced_skill_name, line_num))

            canonical_skill_name = _strip_yoink_prefix(referenced_skill_name)
            if not _has_yoink_prefix(referenced_skill_name):
                warnings.append(
                    LintWarning(
                        LintRule.SKILL_MISSING_PREFIX,
                        filename,
                        line_num,
                        "Skill references must use the '/yoink:' prefix. "
                        f"Found '/{referenced_skill_name}'.",
                    )
                )

            skill_file = SKILLS_DIR / canonical_skill_name / "SKILL.md"
            if skill_file.exists():
                continue

            warnings.append(
                LintWarning(
                    LintRule.SKILL_NOT_FOUND,
                    filename,
                    line_num,
                    f"Skill '{_format_skill_reference(referenced_skill_name)}' "
                    "invoked but not found in skills/",
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


JSON_CODE_BLOCK_PATTERN = re.compile(r"```json\n(.*?)```", re.DOTALL)
JSON_SCHEMA_REQUIRED_KEYS = {"type", "description"}


def _lint_json_schema_fields(
    filename: str,
    rule: LintRule,
    section_line: int,
    section_label: str,
    json_blocks: list[str],
) -> list[LintWarning]:
    """Shared validation: each top-level key must have 'type' and 'description'."""
    warnings: list[LintWarning] = []

    for block in json_blocks:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError as exc:
            warnings.append(
                LintWarning(
                    rule,
                    filename,
                    section_line,
                    f"{section_label} JSON code block is not valid JSON: {exc}",
                )
            )
            continue

        if not isinstance(parsed, dict):
            warnings.append(
                LintWarning(
                    rule,
                    filename,
                    section_line,
                    f"{section_label} JSON Schema must be an object with field definitions.",
                )
            )
            continue

        for key, value in parsed.items():
            if not isinstance(value, dict):
                warnings.append(
                    LintWarning(
                        rule,
                        filename,
                        section_line,
                        f"{section_label} field '{key}' must be a JSON Schema property "
                        f"(object with 'type' and 'description'), got {type(value).__name__}.",
                    )
                )
                continue
            missing = JSON_SCHEMA_REQUIRED_KEYS - value.keys()
            if missing:
                warnings.append(
                    LintWarning(
                        rule,
                        filename,
                        section_line,
                        f"{section_label} field '{key}' is missing required JSON Schema "
                        f"key(s): {', '.join(sorted(missing))}.",
                    )
                )

    return warnings


def _lint_input_json_schema(
    filename: str, input_text: str, file_lines: list[str]
) -> list[LintWarning]:
    """OL405: Validate that the Input section contains a valid JSON Schema code block
    and a reference-only note."""
    warnings: list[LintWarning] = []
    input_section_line = next(
        (
            i
            for i, line in enumerate(file_lines, 1)
            if re.match(r"^##\s+Input\s*$", line)
        ),
        0,
    )

    if not INPUT_REFERENCE_NOTE_PATTERN.search(input_text):
        warnings.append(
            LintWarning(
                LintRule.AGENT_PARAM_FORMAT,
                filename,
                input_section_line,
                "Input section must contain a reference-only note "
                "(e.g., '> **Note:** This schema is for reference only — "
                "input may arrive in varying formats.').",
            )
        )

    json_blocks = JSON_CODE_BLOCK_PATTERN.findall(input_text)
    if not json_blocks:
        warnings.append(
            LintWarning(
                LintRule.AGENT_PARAM_FORMAT,
                filename,
                input_section_line,
                "Input section must contain a ```json code block with a JSON Schema "
                "defining each input field (each key needs 'type' and 'description').",
            )
        )
        return warnings

    warnings.extend(
        _lint_json_schema_fields(
            filename,
            LintRule.AGENT_PARAM_FORMAT,
            input_section_line,
            "Input",
            json_blocks,
        )
    )
    return warnings


def _lint_output_json_schema(
    filename: str, output_text: str, file_lines: list[str]
) -> list[LintWarning]:
    """OL406: Validate that the Output section contains a valid JSON Schema code block.

    Each top-level key in the JSON object must have at least 'type' and
    'description' fields to qualify as a JSON Schema property definition.
    """
    warnings: list[LintWarning] = []
    output_section_line = next(
        (
            i
            for i, line in enumerate(file_lines, 1)
            if re.match(r"^##\s+Output\s*$", line)
        ),
        0,
    )

    json_blocks = JSON_CODE_BLOCK_PATTERN.findall(output_text)
    if not json_blocks:
        warnings.append(
            LintWarning(
                LintRule.AGENT_OUTPUT_NOT_JSON_SCHEMA,
                filename,
                output_section_line,
                "Output section must contain a ```json code block with a JSON Schema "
                "defining each output field (each key needs 'type' and 'description').",
            )
        )
        return warnings

    warnings.extend(
        _lint_json_schema_fields(
            filename,
            LintRule.AGENT_OUTPUT_NOT_JSON_SCHEMA,
            output_section_line,
            "Output",
            json_blocks,
        )
    )
    return warnings


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
    # OL408/OL409/OL410: Frontmatter value constraints
    warnings.extend(lint_frontmatter_values(filename, frontmatter))
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

    # OL405: Input must use JSON Schema (like Output) with a reference-only note,
    # since the orchestrator may pass input in varying formats.
    if input_text is not None:
        warnings.extend(_lint_input_json_schema(filename, input_text, lines))

    # OL406: Output uses JSON Schema because agents control their own output and
    # a standardized structure makes downstream parsing reliable.
    if output_text is not None:
        warnings.extend(_lint_output_json_schema(filename, output_text, lines))

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
    parent_body, substeps = _split_substeps(body)
    agent_match = AGENT_PATTERN.search(parent_body)
    skill_match = SKILL_INVOKE_PATTERN.search(parent_body)

    conditionals = [
        Conditional(condition=cond.strip(), action=action.strip())
        for cond, action in CONDITIONAL_PATTERN.findall(parent_body)
    ]
    scripts = _extract_scripts(parent_body)
    common = {
        "header": header.strip(),
        "body": parent_body,
        "num": step_num,
        "conditionals": conditionals,
        "scripts": scripts,
        "substeps": substeps,
    }

    if skill_match:
        skill_name = _strip_yoink_prefix(skill_match.group(1))
        return SkillStep(
            **common,
            details=_build_ordered_details(parent_body, "skill", None),
            skill_name=skill_name,
        )
    if agent_match:
        agent_name = _strip_yoink_prefix(agent_match.group(1))
        return AgentStep(
            **common,
            details=_build_ordered_details(parent_body, "agent", agent_name),
            agent_name=agent_name,
        )
    return InlineStep(
        **common,
        details=_build_ordered_details(parent_body, "inline", None),
    )


def _split_substeps(step_body: str) -> tuple[str, list[Substep]]:
    substep_matches = list(SUBSTEP_HEADER_PATTERN.finditer(step_body))
    if not substep_matches:
        return step_body, []

    parent_body = step_body[: substep_matches[0].start()]
    substeps: list[Substep] = []
    for index, match in enumerate(substep_matches):
        start = match.start()
        end = (
            substep_matches[index + 1].start()
            if index + 1 < len(substep_matches)
            else len(step_body)
        )
        substeps.append(
            _classify_substep(match.group(0), step_body[start:end], match.group(1))
        )

    return parent_body, substeps


def _classify_substep(header: str, body: str, marker: str) -> Substep:
    agent_match = AGENT_PATTERN.search(body)
    skill_match = SKILL_INVOKE_PATTERN.search(body)
    conditionals = [
        Conditional(condition=cond.strip(), action=action.strip())
        for cond, action in CONDITIONAL_PATTERN.findall(body)
    ]
    scripts = _extract_scripts(body)

    if skill_match:
        skill_name = _strip_yoink_prefix(skill_match.group(1))
        return Substep(
            marker=marker,
            header=header.strip(),
            body=body,
            kind="skill",
            skill_name=skill_name,
            conditionals=conditionals,
            scripts=scripts,
            details=_build_ordered_details(body, "skill", None),
        )

    if agent_match:
        agent_name = _strip_yoink_prefix(agent_match.group(1))
        return Substep(
            marker=marker,
            header=header.strip(),
            body=body,
            kind="agent",
            agent_name=agent_name,
            conditionals=conditionals,
            scripts=scripts,
            details=_build_ordered_details(body, "agent", agent_name),
        )

    return Substep(
        marker=marker,
        header=header.strip(),
        body=body,
        kind="inline",
        conditionals=conditionals,
        scripts=scripts,
        details=_build_ordered_details(body, "inline", None),
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
    label = re.sub(r"^####\s+[a-z]\.\s*", "", label)
    label = re.sub(r"\*\*", "", label)
    label = label.strip()
    if len(label) > 60:
        label = label[:57] + "..."
    return label or "(inline)"


# --- Rendering ---


def _agent_signature(agent_name: str, agent_data: dict[str, AgentData]) -> str:
    """Format an agent detail label with I/O signature if available."""
    if agent_name not in agent_data:
        return f"agent: {_format_agent_reference(agent_name)}"
    agent = agent_data[agent_name]
    input_sig = ", ".join(agent.input_keys) if agent.input_keys else ""
    label = f"agent: {_format_agent_reference(agent_name)}({input_sig})"
    if agent.output_keys:
        output_sig = ", ".join(agent.output_keys)
        label += f" \u2192 {output_sig}"
    return label


def _render_detail_label(
    detail: StepDetail,
    kind: StepType,
    agent_name: str | None,
    agent_data: dict[str, AgentData] | None,
) -> str:
    if (
        detail.kind == "agent"
        and agent_data
        and kind == "agent"
        and agent_name is not None
    ):
        return _agent_signature(agent_name, agent_data)
    return detail.label


def _render_substeps(
    substeps: list[Substep],
    *,
    prefix: str,
    agent_data: dict[str, AgentData] | None,
) -> list[str]:
    lines: list[str] = []
    for substep_index, substep in enumerate(substeps):
        is_last_substep = substep_index == len(substeps) - 1
        branch = "\u2514\u2500" if is_last_substep else "\u251c\u2500"
        label = _clean_label(substep.header)
        if substep.kind == "skill" and substep.skill_name is not None:
            label += f" \u2192 {_format_skill_reference(substep.skill_name)}"
        lines.append(f"{prefix}{branch} {substep.marker}. {label}")

        detail_labels = [
            _render_detail_label(
                detail,
                substep.kind,
                substep.agent_name,
                agent_data,
            )
            for detail in substep.details
        ]
        substep_continuation = "   " if is_last_substep else "\u2502  "
        continuation_prefix = f"{prefix}{substep_continuation}"
        for detail_index, detail_label in enumerate(detail_labels):
            is_last_detail = detail_index == len(detail_labels) - 1
            detail_branch = "\u2514\u2500" if is_last_detail else "\u251c\u2500"
            lines.append(f"{continuation_prefix}{detail_branch} {detail_label}")

    return lines


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
        if isinstance(step, SkillStep):
            label += f" \u2192 {_format_skill_reference(step.skill_name)}"
        lines.append(f"{indent}{connector}{step.num}. {label}")

        detail_labels = [
            _render_detail_label(
                detail,
                "agent" if isinstance(step, AgentStep) else "inline",
                step.agent_name if isinstance(step, AgentStep) else None,
                agent_data,
            )
            for detail in step.details
        ]

        if not isinstance(step, SkillStep):
            total_children = len(detail_labels) + len(step.substeps)
            for index, detail_label in enumerate(detail_labels):
                is_last = index == total_children - 1 and not step.substeps
                branch = "\u2514\u2500" if is_last else "\u251c\u2500"
                lines.append(f"{indent}{connector}   {branch} {detail_label}")
            lines.extend(
                _render_substeps(
                    step.substeps,
                    prefix=f"{indent}{connector}   ",
                    agent_data=agent_data,
                )
            )

        # Expand nested skill inline
        if isinstance(step, SkillStep) and skill_data and step.skill_name:
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
    formatted_command_name = _format_skill_reference(command_name)
    header = (
        f"{formatted_command_name} {argument_hint}"
        if argument_hint
        else formatted_command_name
    )
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
            output_lines.append(
                f"- **{_format_agent_reference(name)}**{sig}: {agent.description}"
            )
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
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output lint warnings as a JSON array (for CI/IDE integration)",
    )
    args = parser.parse_args()

    agents = parse_agents()
    known_agent_names = set(agents.keys())

    # Linting is always the primary action
    warnings = run_lint(known_agent_names)
    if warnings:
        if args.json:
            json_warnings = [
                {
                    "rule": warning.rule.value,
                    "file": warning.file,
                    "line": warning.line,
                    "message": warning.message,
                }
                for warning in warnings
            ]
            print(json.dumps(json_warnings, indent=2))
        else:
            print(f"\u26a0\ufe0f  {len(warnings)} convention warning(s):")
            for warning in warnings:
                print(warning)
            print()
        sys.exit(1)

    if args.json:
        print("[]")
    else:
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
