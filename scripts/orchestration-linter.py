#!/usr/bin/env python3
"""
Lint orchestrator skill files for convention compliance. Generates
ORCHESTRATION_FLOW.md as a side effect.

Validates these conventions in skills/*/SKILL.md:

  Sections:       ## headers (e.g., "## Phase 0: Test Curation")
  Steps:          ### N. headers, sequential per section (e.g., "### 1. Dequeue")
  Agents:         **agent-name** agent (must exist in agents/)
  Conditionals:   - If **condition** then **action**.
  Loop start:     **Begin loop.** (before first loop step)
  Loop end:       **Loop back to step N.** (after last loop step, paired with Begin)
  Scripts:        ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/ prefix (no hardcoded or bare paths)

Usage:
  python scripts/orchestration-linter.py                # lint + print flow
  python scripts/orchestration-linter.py --write        # lint + write ORCHESTRATION_FLOW.md
  python scripts/orchestration-linter.py --check        # lint + verify ORCHESTRATION_FLOW.md is current
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "ORCHESTRATION_FLOW.md"

ORCHESTRATOR_COMMANDS = ["setup", "test-curate", "decompose", "diy-decomp", "diy-loop"]

BEGIN_LOOP_PATTERN = re.compile(r"^\*\*Begin loop\.\*\*", re.MULTILINE)
LOOP_BACK_PATTERN = re.compile(r"^\*\*Loop back to step (\d+)\.\*\*", re.MULTILINE)
STEP_HEADER_PATTERN = re.compile(r"^###\s+(\d+)\.\s+(.*)", re.MULTILINE)
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


@dataclass
class LintWarning:
    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"  {self.file}:{self.line}: {self.message}"


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


ARGUMENT_HINT_PATTERN = re.compile(r'^argument-hint:\s*"(.+)"$', re.MULTILINE)


def parse_argument_hint(content: str) -> str | None:
    """Extract argument-hint from YAML frontmatter."""
    frontmatter_match = re.match(
        r"^---\n(.*?)^---\n", content, re.DOTALL | re.MULTILINE
    )
    if not frontmatter_match:
        return None
    match = ARGUMENT_HINT_PATTERN.search(frontmatter_match.group(1))
    return match.group(1) if match else None


def parse_agents() -> dict[str, str]:
    """Read agent files and return {name: description}."""
    agents = {}
    if not AGENTS_DIR.exists():
        return agents
    for agent_file in sorted(AGENTS_DIR.glob("*.md")):
        content = agent_file.read_text()
        name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
        desc_match = re.search(r'^description:\s*"(.+)"$', content, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip()
            description = desc_match.group(1).strip() if desc_match else ""
            agents[name] = description
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
    elif len(groups) == 2:
        path_var, script_path = groups
        return f"${{{path_var}}}/{script_path}"
    else:
        path_var, script_path, subcommand = groups
        label = f"${{{path_var}}}/{script_path}"
        if subcommand:
            label = f"{label} {subcommand}"
        return label


# --- Linting ---


def lint_command(
    command_name: str, content: str, known_agents: set[str]
) -> list[LintWarning]:
    """Check a skill file follows conventions."""
    warnings: list[LintWarning] = []
    filename = f"skills/{command_name}/SKILL.md"
    lines = content.split("\n")
    body = re.sub(
        r"^---\n.*?^---\n", "", content, count=1, flags=re.DOTALL | re.MULTILINE
    )

    # Steps should use ### N. format, not ## Step N
    for i, line in enumerate(lines, 1):
        if re.match(r"^##\s+Step\s+\d", line):
            warnings.append(
                LintWarning(
                    filename,
                    i,
                    f"Use '### N. Title' for steps, not '## Step N'. "
                    f"Found: {line.strip()}",
                )
            )

    # Agent references must point to known agents
    for match in AGENT_PATTERN.finditer(body):
        agent_name = match.group(1)
        if agent_name not in known_agents:
            line_num = next(
                (i for i, line in enumerate(lines, 1) if f"**{agent_name}**" in line),
                0,
            )
            warnings.append(
                LintWarning(
                    filename,
                    line_num,
                    f"Agent '{agent_name}' referenced but not found in agents/",
                )
            )

    # Skill invocations must point to existing skills
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
                    filename,
                    line_num,
                    f"Skill '/{skill_name}' invoked but not found in skills/",
                )
            )

    # Conditionals must use: - If **condition** then **action**.
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Old convention: -> instead of then
        if re.match(r"^[-*]\s+If\s+\*\*.+\*\*\s*(?:\u2192|->)", stripped):
            warnings.append(
                LintWarning(
                    filename,
                    i,
                    "Use 'then' instead of '->'. "
                    f"Convention: '- If **condition** then **action**'. Found: {stripped}",
                )
            )
        # Bold wrapping the "If" keyword
        if re.match(r"^[-*]\s+\*\*If\s+", stripped):
            warnings.append(
                LintWarning(
                    filename,
                    i,
                    "'If' should not be bold. "
                    f"Convention: '- If **condition** then **action**'. Found: {stripped}",
                )
            )
        # Unbolded condition or action
        if re.match(r"^[-*]\s+[Ii]f\s+", stripped) and "**" not in stripped:
            warnings.append(
                LintWarning(
                    filename,
                    i,
                    "Condition and action must be bold. "
                    f"Convention: '- If **condition** then **action**'. Found: {stripped}",
                )
            )

    # Step numbering should be sequential within each section
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

    # Script references should use ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/, not hardcoded paths
    for i, line in enumerate(lines, 1):
        # Hardcoded .claude/plugins/ paths
        if re.search(r"\.claude/plugins/slash-diy/\S+\.(py|sh)", line):
            warnings.append(
                LintWarning(
                    filename,
                    i,
                    "Use ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/ instead of hardcoded plugin path. "
                    f"Found: {line.strip()}",
                )
            )
        # Bare relative scripts/ paths (not inside ${CLAUDE_PLUGIN_ROOT}/ or ${CLAUDE_SKILL_DIR}/)
        if re.search(
            r"(?<!\{CLAUDE_PLUGIN_ROOT\}/)(?<!\{CLAUDE_SKILL_DIR\}/)scripts/\S+\.(py|sh)",
            line,
        ):
            if (
                "${CLAUDE_PLUGIN_ROOT}/scripts/" not in line
                and "${CLAUDE_SKILL_DIR}/scripts/" not in line
            ):
                warnings.append(
                    LintWarning(
                        filename,
                        i,
                        "Plugin scripts should use ${CLAUDE_PLUGIN_ROOT}/scripts/ or ${CLAUDE_SKILL_DIR}/scripts/, "
                        f"not bare 'scripts/' paths. Found: {line.strip()}",
                    )
                )

    # Loop markers must be paired
    begin_loops = list(BEGIN_LOOP_PATTERN.finditer(body))
    loop_backs = list(LOOP_BACK_PATTERN.finditer(body))

    if len(begin_loops) != len(loop_backs):
        for i, line in enumerate(lines, 1):
            if "**Begin loop.**" in line or "**Loop back to step" in line:
                warnings.append(
                    LintWarning(
                        filename,
                        i,
                        f"Unpaired loop marker: found {len(begin_loops)} "
                        f"'Begin loop' and {len(loop_backs)} 'Loop back'. "
                        "They must be paired.",
                    )
                )
                break

    # Loop back target must match the first step after Begin loop
    for begin, back in zip(begin_loops, loop_backs):
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
                        filename,
                        line_num,
                        f"Loop back targets step {actual_target} but the first "
                        f"step after 'Begin loop' is step {expected_target}",
                    )
                )

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
                filename,
                section_start_line,
                f"Steps should be numbered 1, 2, 3... but found {step_numbers}",
            )
        ]
    return []


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


def render_section(
    section: Section,
    skill_data: dict[str, SkillData] | None = None,
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

        # Collect sub-lines in source order
        sub_lines = [detail.label for detail in step.details]

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
    command_name: str, content: str, skill_data: dict[str, SkillData] | None = None
) -> list[str]:
    argument_hint = parse_argument_hint(content)
    header = f"/{command_name} {argument_hint}" if argument_hint else f"/{command_name}"
    lines = [header]

    sections = extract_sections(content)
    if not sections:
        lines.append("  (no orchestration steps detected)")
        lines.append("")
        return lines

    for section in sections:
        lines.extend(render_section(section, skill_data=skill_data))

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
            argument_hint=parse_argument_hint(content),
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
        for name, description in sorted(agents.items()):
            output_lines.append(f"- **{name}**: {description}")
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
            render_command(command_name, content, skill_data=skill_data)
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
        "--check",
        action="store_true",
        help="Verify ORCHESTRATION_FLOW.md is up to date after linting",
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

    if args.check:
        if not OUTPUT_FILE.exists():
            print(
                f"\u274c {OUTPUT_FILE.name} does not exist. "
                "Run: uv run python scripts/orchestration-linter.py --write"
            )
            sys.exit(1)
        existing = OUTPUT_FILE.read_text()
        if existing != flow:
            print(
                f"\u274c {OUTPUT_FILE.name} is stale. "
                "Run: uv run python scripts/orchestration-linter.py --write"
            )
            sys.exit(1)
        print(f"\u2705 {OUTPUT_FILE.name} is up to date")
    elif args.write:
        OUTPUT_FILE.write_text(flow)
        print(f"\u2705 Wrote {OUTPUT_FILE.name}")
    else:
        print()
        print(flow)


if __name__ == "__main__":
    main()
