#!/usr/bin/env python3
"""
Lint orchestrator command files for convention compliance. Generates
ORCHESTRATION_FLOW.md as a side effect.

Validates these conventions in commands/*.md:

  Sections:       ## headers (e.g., "## Phase 0: Test Curation")
  Steps:          ### N. headers, sequential per section (e.g., "### 1. Dequeue")
  Agents:         **agent-name** agent (must exist in agents/)
  Conditionals:   - If **condition** then **action**.
  Loop start:     **Begin loop.** (before first loop step)
  Loop end:       **Loop back to step N.** (after last loop step, paired with Begin)
  Scripts:        ${CLAUDE_PLUGIN_ROOT}/ prefix (no hardcoded or bare paths)

Usage:
  python scripts/orchestration-linter.py                # lint + print flow
  python scripts/orchestration-linter.py --write        # lint + write ORCHESTRATION_FLOW.md
  python scripts/orchestration-linter.py --check        # lint + verify ORCHESTRATION_FLOW.md is current
"""

import argparse
import re
import sys
from pathlib import Path

COMMANDS_DIR = Path(__file__).resolve().parent.parent / "commands"
AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "ORCHESTRATION_FLOW.md"

ORCHESTRATOR_COMMANDS = ["test-curate", "decompose", "diy-decomp", "diy-loop"]

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
# Convention: all plugin scripts use ${CLAUDE_PLUGIN_ROOT}/.
SCRIPT_PATTERNS = [
    # uv run python ${CLAUDE_PLUGIN_ROOT}/scripts/foo.py subcommand
    re.compile(
        r"uv run python \$\{CLAUDE_PLUGIN_ROOT\}/(scripts/\S+\.py)(?:\s+(\w+))?"
    ),
    # uv run ${CLAUDE_PLUGIN_ROOT}/foo.py (no "python" prefix)
    re.compile(r"uv run \$\{CLAUDE_PLUGIN_ROOT\}/(\S+\.py)"),
    # "${CLAUDE_PLUGIN_ROOT}/scripts/foo.sh" (shell scripts, possibly quoted)
    re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/(scripts/\S+\.sh)"),
    # uv run pytest (external tools, not plugin scripts)
    re.compile(r"uv run (pytest)\b"),
]


class LintWarning:
    def __init__(self, file: str, line: int, message: str) -> None:
        self.file = file
        self.line = line
        self.message = message

    def __str__(self) -> str:
        return f"  {self.file}:{self.line}: {self.message}"


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


# --- Linting ---


def lint_command(
    command_name: str, content: str, known_agents: set[str]
) -> list[LintWarning]:
    """Check a command file follows conventions."""
    warnings: list[LintWarning] = []
    filename = f"commands/{command_name}.md"
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
            if section_steps:
                _check_step_sequence(
                    warnings, filename, section_steps, current_section_start
                )
            section_steps = []
            current_section_start = i
        step_match = re.match(r"^###\s+(\d+)\.", line)
        if step_match:
            section_steps.append(int(step_match.group(1)))
    if section_steps:
        _check_step_sequence(warnings, filename, section_steps, current_section_start)

    # Script references should use ${CLAUDE_PLUGIN_ROOT}/, not hardcoded paths
    for i, line in enumerate(lines, 1):
        # Hardcoded .claude/plugins/ paths
        if re.search(r"\.claude/plugins/slash-diy/\S+\.(py|sh)", line):
            warnings.append(
                LintWarning(
                    filename,
                    i,
                    "Use ${CLAUDE_PLUGIN_ROOT}/ instead of hardcoded plugin path. "
                    f"Found: {line.strip()}",
                )
            )
        # Bare relative scripts/ paths (not inside ${CLAUDE_PLUGIN_ROOT}/)
        if re.search(r"(?<!\{CLAUDE_PLUGIN_ROOT\}/)scripts/\S+\.(py|sh)", line):
            # Skip if it's actually inside ${CLAUDE_PLUGIN_ROOT}/scripts/
            if "${CLAUDE_PLUGIN_ROOT}/scripts/" not in line:
                warnings.append(
                    LintWarning(
                        filename,
                        i,
                        "Plugin scripts should use ${CLAUDE_PLUGIN_ROOT}/scripts/, "
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
        # Find the first ### N. step after the Begin loop marker
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
    warnings: list[LintWarning],
    filename: str,
    step_numbers: list[int],
    section_start_line: int,
) -> None:
    expected = list(range(1, len(step_numbers) + 1))
    if step_numbers != expected:
        warnings.append(
            LintWarning(
                filename,
                section_start_line,
                f"Steps should be numbered 1, 2, 3... but found {step_numbers}",
            )
        )


# --- Parsing ---


def extract_sections(content: str) -> list[dict]:
    """Split content into phases/sections, then extract steps from each."""
    content = re.sub(
        r"^---\n.*?^---\n", "", content, count=1, flags=re.DOTALL | re.MULTILINE
    )

    section_matches = list(SECTION_HEADER_PATTERN.finditer(content))
    sections = []

    if not section_matches:
        parsed = _parse_block(content)
        if parsed["steps"]:
            sections.append(parsed)
        return sections

    # Preamble before first ## header
    preamble = content[: section_matches[0].start()].strip()
    if preamble:
        parsed = _parse_block(preamble)
        if parsed["steps"]:
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
        parsed["title"] = title
        if parsed["steps"]:
            sections.append(parsed)

    return sections


def _parse_block(block: str) -> dict:
    """Extract steps and loop markers from a block of text."""
    result: dict = {"title": None, "steps": [], "loop_start": None, "loop_target": None}

    # Detect loop markers
    begin_match = BEGIN_LOOP_PATTERN.search(block)
    back_match = LOOP_BACK_PATTERN.search(block)

    if begin_match and back_match:
        result["loop_target"] = int(back_match.group(1))
        # Find first step after Begin loop to determine loop_start
        first_step = STEP_HEADER_PATTERN.search(block, begin_match.end())
        if first_step:
            result["loop_start"] = int(first_step.group(1))

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
        result["steps"].append(step)

    return result


def _classify_step(header: str, body: str, step_num: int) -> dict:
    """Classify a step."""
    step: dict = {"header": header.strip(), "body": body, "num": step_num}

    agent_match = AGENT_PATTERN.search(body)
    if agent_match:
        step["type"] = "agent"
        step["agent"] = agent_match.group(1)
    else:
        step["type"] = "inline"

    conditionals = CONDITIONAL_PATTERN.findall(body)
    if conditionals:
        step["conditionals"] = [
            (cond.strip(), action.strip()) for cond, action in conditionals
        ]

    # Extract script references from bash code blocks
    scripts = _extract_scripts(body)
    if scripts:
        step["scripts"] = scripts

    return step


def _extract_scripts(body: str) -> list[str]:
    """Extract unique script invocations from bash code blocks in step body."""
    # Only look inside ```bash ... ``` or ```! ... ``` blocks
    code_blocks = re.findall(r"```(?:bash|!)\n(.*?)```", body, re.DOTALL)
    if not code_blocks:
        return []

    seen: set[str] = set()
    scripts: list[str] = []
    for block in code_blocks:
        for pattern in SCRIPT_PATTERNS:
            for match in pattern.finditer(block):
                script_name = match.group(1)
                # Include subcommand if present (e.g., "decomp.py enqueue")
                if match.lastindex and match.lastindex >= 2 and match.group(2):
                    label = f"{script_name} {match.group(2)}"
                else:
                    label = script_name
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


def render_section(section: dict) -> list[str]:
    """Render a section with its steps and loop markers."""
    lines = []
    indent = "  "

    if section["title"]:
        lines.append(f"{indent}[{section['title']}]")

    loop_start = section.get("loop_start")
    loop_target = section.get("loop_target")
    has_loop = loop_start is not None and loop_target is not None

    for step in section["steps"]:
        step_num = step["num"]
        in_loop = has_loop and step_num >= loop_start
        connector = "\u2502 " if in_loop else ""

        # Loop open marker
        if has_loop and step_num == loop_start:
            lines.append(f"{indent}\u250c\u2500 loop")

        # Label is always the step title
        label = _clean_label(step["header"])
        lines.append(f"{indent}{connector}{step_num}. {label}")

        # Collect sub-lines (agent + scripts + conditionals)
        sub_lines = []
        if step["type"] == "agent":
            sub_lines.append(f"agent: {step['agent']}")
        if step.get("scripts"):
            for script in step["scripts"]:
                sub_lines.append(f"runs: {script}")
        if step.get("conditionals"):
            for condition, action in step["conditionals"]:
                sub_lines.append(f"{condition} \u2192 {action}")

        for j, sub in enumerate(sub_lines):
            is_last = j == len(sub_lines) - 1
            branch = "\u2514\u2500" if is_last else "\u251c\u2500"
            lines.append(f"{indent}{connector}   {branch} {sub}")

    # Loop close marker
    if has_loop:
        lines.append(f"{indent}\u2514\u2500 back to step {loop_target}")

    return lines


def render_command(command_name: str, content: str) -> list[str]:
    argument_hint = parse_argument_hint(content)
    header = f"/{command_name} {argument_hint}" if argument_hint else f"/{command_name}"
    lines = [header]

    sections = extract_sections(content)
    if not sections:
        lines.append("  (no orchestration steps detected)")
        lines.append("")
        return lines

    for section in sections:
        lines.extend(render_section(section))

    lines.append("")
    return lines


# --- Output ---


def generate_flow() -> str:
    agents = parse_agents()

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

    output_lines.append("## Command Flows")
    output_lines.append("")
    output_lines.append("```")

    for command_name in ORCHESTRATOR_COMMANDS:
        command_file = COMMANDS_DIR / f"{command_name}.md"
        if not command_file.exists():
            continue
        content = command_file.read_text()
        output_lines.extend(render_command(command_name, content))

    output_lines.append("```")
    output_lines.append("")

    return "\n".join(output_lines)


def run_lint(known_agents: set[str]) -> list[LintWarning]:
    all_warnings: list[LintWarning] = []
    for command_name in ORCHESTRATOR_COMMANDS:
        command_file = COMMANDS_DIR / f"{command_name}.md"
        if not command_file.exists():
            continue
        content = command_file.read_text()
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
