"""
Inner Ralph Loop — generate state body and rewrite sub-package imports.

Usage:
    uv run inner_ralph.py generate-state-body --context ctx.md --top-package litellm --sub-package annotated-types --max-iterations 10
    uv run inner_ralph.py rewrite-sub-imports --sub-package annotated-types --target-dir yoink_litellm
"""

import argparse
import json
import re
from pathlib import Path
from typing import Literal, TypedDict

CollectionState = Literal["functions_to_replace", "strategy"]


class DecompContext(TypedDict, total=False):
    category: str
    strategy: str
    functions_to_replace: list[str]
    reference_material: str
    acceptable_sub_dependencies: list[str]


# Fields recognized by the markdown parser (lowercase label → dict key).
_FIELD_HEADERS = {
    "category": "category",
    "strategy": "strategy",
    "reference material": "reference_material",
    "functions to replace": "functions_to_replace",
    "acceptable sub-dependencies": "acceptable_sub_dependencies",
}


def _parse_markdown_context(text: str) -> DecompContext:
    """Parse orchestrator evaluation markdown into the same dict as the JSON context."""
    ctx: DecompContext = {}
    collecting: CollectionState | None = None

    for raw_line in text.splitlines():
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", raw_line).strip()

        # Check if this line starts a recognized field.
        matched_key = None
        value = ""
        for label, key in _FIELD_HEADERS.items():
            if line.lower().startswith(label + ":"):
                matched_key = key
                value = line.split(":", 1)[1].strip()
                break

        if matched_key:
            collecting = None  # stop any previous multi-line collection

            match matched_key:
                case "functions_to_replace":
                    if value:  # comma-separated on same line
                        ctx["functions_to_replace"] = [
                            i.strip() for i in value.split(",") if i.strip()
                        ]
                    else:  # bullet list follows
                        ctx["functions_to_replace"] = []
                        collecting = "functions_to_replace"

                case "acceptable_sub_dependencies":
                    if value and not value.lower().startswith("none"):
                        ctx["acceptable_sub_dependencies"] = [
                            re.sub(r"\s*\(.*?\)", "", i).strip()
                            for i in value.split(",")
                            if i.strip()
                        ]
                    else:
                        ctx["acceptable_sub_dependencies"] = []

                case "strategy":
                    ctx["strategy"] = value
                    collecting = "strategy"

                case "category":
                    ctx["category"] = value
                case "reference_material":
                    ctx["reference_material"] = value
            continue

        # Continuation lines (multi-line fields).
        if collecting == "functions_to_replace" and line.startswith("- "):
            ctx.setdefault("functions_to_replace", []).append(line[2:].strip())
        elif collecting == "strategy" and line:
            ctx["strategy"] = ctx.get("strategy", "") + "\n" + line
        elif line:
            collecting = None  # unrecognized non-empty line ends collection

    return ctx


_JSON_BLOCK_PATTERN = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)


def _extract_json_from_agent_output(raw: str) -> DecompContext | None:
    """Try to parse agent output as JSON — either raw JSON or a ```json block in markdown.

    Agents are instructed to output JSON Schema but may wrap it in prose. Try
    raw JSON first, then look for a fenced ```json block. Returns None if
    neither works, so the caller can fall back to markdown parsing.
    """
    # Raw JSON (agent output is pure JSON with no surrounding text)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # JSON fenced in a ```json code block within markdown prose
    match = _JSON_BLOCK_PATTERN.search(raw)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def generate_state_body(args: argparse.Namespace) -> None:
    """Output the runtime variables as a markdown table for the state file body."""
    raw = Path(args.context).read_text()
    ctx: DecompContext = _extract_json_from_agent_output(
        raw
    ) or _parse_markdown_context(raw)

    sub_pkg = args.sub_package
    top_pkg = args.top_package

    variables = {
        "top_package": top_pkg,
        "sub_package": sub_pkg,
        "category": ctx.get("category", "Unknown"),
        "strategy": ctx.get("strategy", "Study reference and reimplement"),
        "functions_to_replace": ", ".join(ctx.get("functions_to_replace", []))
        or "none identified",
        "reference_material": ctx.get(
            "reference_material", f".yoink/reference/{sub_pkg}/"
        ),
        "acceptable_sub_dependencies": ", ".join(
            ctx.get("acceptable_sub_dependencies", [])
        )
        or "none",
        "max_iterations": str(args.max_iterations),
    }

    lines = ["| Field | Value |", "|---|---|"]
    for key, value in variables.items():
        lines.append(f"| {key} | {value} |")
    print("\n".join(lines))


def rewrite_sub_imports(args: argparse.Namespace) -> None:
    sub_pkg = args.sub_package
    target = f"yoink_{sub_pkg}"
    target_dir = Path(args.target_dir)

    if not target_dir.is_dir():
        print(f"Error: {target_dir} does not exist")
        raise SystemExit(1)

    count = 0
    for f in target_dir.rglob("*.py"):
        # Skip test files — they import from yoink_<top_pkg>, not the sub-package
        if "tests" in f.parts:
            continue
        content = f.read_text(errors="replace")
        new_content = re.sub(rf"\bfrom {sub_pkg}\b", f"from {target}", content)
        new_content = re.sub(rf"\bimport {sub_pkg}\b", f"import {target}", new_content)
        new_content = re.sub(rf"\b{sub_pkg}\.", f"{target}.", new_content)
        if new_content != content:
            f.write_text(new_content)
            count += 1

    print(
        f"Rewrote imports in {count} files ({sub_pkg} -> {target}) within {target_dir}/"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inner Ralph Loop utilities")
    sub = parser.add_subparsers(dest="command")

    gp = sub.add_parser(
        "generate-state-body",
        help="Generate runtime variables table for state file body",
    )
    gp.add_argument(
        "--context",
        required=True,
        help="Path to decomposition context (JSON or markdown)",
    )
    gp.add_argument("--top-package", required=True, help="Top-level package name")
    gp.add_argument("--sub-package", required=True, help="Sub-package to build")
    gp.add_argument(
        "--max-iterations", type=int, default=30, help="Max loop iterations"
    )

    rw = sub.add_parser(
        "rewrite-sub-imports", help="Rewrite sub-package imports in source"
    )
    rw.add_argument("--sub-package", required=True, help="Sub-package to rewrite")
    rw.add_argument(
        "--target-dir", required=True, help="Directory to rewrite imports in"
    )

    args = parser.parse_args()

    # Normalize package names: hyphens → underscores, strip accidental yoink_ prefix
    # (the templates/code add yoink_ themselves, so args must be the bare name)
    for attr in ("sub_package", "top_package"):
        if hasattr(args, attr):
            setattr(
                args, attr, getattr(args, attr).replace("-", "_").removeprefix("yoink_")
            )

    match args.command:
        case "generate-state-body":
            generate_state_body(args)
        case "rewrite-sub-imports":
            rewrite_sub_imports(args)
        case _:
            parser.print_help()
            raise SystemExit(1)


if __name__ == "__main__":
    main()
