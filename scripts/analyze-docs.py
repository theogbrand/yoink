#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.9"
# ///
"""
Analyze markdown documentation structure and dependencies.
Detects cross-references between docs and reports cyclic dependencies.

Run with: uv run scripts/analyze-docs.py docs
"""

import re
import sys
from collections import defaultdict
from graphlib import CycleError, TopologicalSorter
from pathlib import Path


def find_markdown_files(root_dir: Path) -> dict[str, Path]:
    """Find all markdown files and map relative paths to absolute paths."""
    files = {}
    for abs_path in root_dir.rglob("*.md"):
        if abs_path.name == "STRUCTURE.md":
            continue
        rel_path = str(abs_path.relative_to(root_dir))
        files[rel_path] = abs_path
    return files


def extract_references(content: str, available_files: dict[str, Path]) -> set[str]:
    """Extract markdown file references from content."""
    references = set()

    def resolve_reference(ref: str) -> str | None:
        """Resolve a .md reference to an available file key, or None."""
        if ref in available_files:
            return ref
        for available in available_files:
            if available.endswith(ref) or ref.endswith(available):
                return available
        return None

    # Pattern 1: Markdown links [text](path.md)
    markdown_links = re.findall(r"\[.*?\]\((.*?\.md)\)", content)
    for link in markdown_links:
        resolved = resolve_reference(link)
        if resolved:
            references.add(resolved)

    # Pattern 2: Code fence references `filename.md`
    code_refs = re.findall(r"`([^`]*\.md)`", content)
    for ref in code_refs:
        resolved = resolve_reference(ref)
        if resolved:
            references.add(resolved)

    return references


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Find cyclic dependencies using graphlib.TopologicalSorter."""
    sorter = TopologicalSorter(graph)
    try:
        # static_order() raises CycleError if cycles exist
        list(sorter.static_order())
        return []
    except CycleError as e:
        # CycleError.args[1] contains the cycle as a tuple
        cycle = list(e.args[1])
        return [cycle]


def build_tree(graph: dict[str, set[str]], all_files: dict[str, Path]) -> str:
    """Build a tree showing folders with files and their dependencies nested."""
    output: list[str] = []
    displayed_files: set[str] = set()

    # Group files by directory
    dir_structure: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for file_path in sorted(all_files.keys()):
        path = Path(file_path)
        directory = str(path.parent) if path.parent != Path(".") else "."
        dir_structure[directory].append((path.name, file_path))

    # Find files that are never referenced (root files)
    all_referenced: set[str] = set()
    for refs in graph.values():
        all_referenced.update(refs)

    # For each directory
    for i, directory in enumerate(sorted(dir_structure.keys())):
        is_last_dir = i == len(dir_structure) - 1
        dir_prefix = "└── " if is_last_dir else "├── "

        if directory != ".":
            output.append(f"{dir_prefix}{directory}/")
            extension = "    " if is_last_dir else "│   "
        else:
            extension = ""

        files = dir_structure[directory]

        # Helper to add file and its dependencies recursively
        def add_file_tree(file_path: str, prefix: str, is_last: bool):
            if file_path in displayed_files:
                return

            filename = Path(file_path).name
            file_prefix = "└── " if is_last else "├── "
            output.append(f"{prefix}{file_prefix}{filename}")
            displayed_files.add(file_path)

            # Add dependencies
            refs = sorted(graph.get(file_path, set()))
            if refs:
                next_prefix = prefix + ("    " if is_last else "│   ")
                for j, ref in enumerate(refs):
                    is_last_ref = j == len(refs) - 1
                    add_file_tree(ref, next_prefix, is_last_ref)

        # Show only root files (not referenced by others) in this directory
        root_files = [(f, p) for f, p in files if p not in all_referenced]
        for j, (filename, full_path) in enumerate(root_files):
            is_last = j == len(root_files) - 1
            add_file_tree(full_path, extension, is_last)

    return "\n".join(output)


def main():
    if len(sys.argv) < 2:
        docs_dir = Path("docs")
    else:
        docs_dir = Path(sys.argv[1])

    if not docs_dir.is_dir():
        print(f"Error: Directory '{docs_dir}' not found")
        sys.exit(1)

    output_file = docs_dir / "STRUCTURE.md"

    # Find all markdown files
    files = find_markdown_files(docs_dir)
    if not files:
        print(f"No markdown files found in '{docs_dir}'")
        sys.exit(1)

    # Build dependency graph
    graph: dict[str, set[str]] = defaultdict(set)
    for file_path, abs_path in files.items():
        content = abs_path.read_text(encoding="utf-8")
        refs = extract_references(content, files)
        graph[file_path] = refs

    # Check for cycles
    cycles = find_cycles(dict(graph))

    # Find root files (files with no incoming references)
    all_referenced: set[str] = set()
    for refs in graph.values():
        all_referenced.update(refs)

    root_files = [f for f in files.keys() if f not in all_referenced]
    if not root_files:
        root_files = sorted(files.keys())[:1]

    # Build output
    output_lines = []

    output_lines.append("# Documentation Structure\n")
    output_lines.append("Auto-generated documentation map.\n")

    if cycles:
        output_lines.append("## ⚠️ Cyclic Dependencies\n")
        for cycle in cycles:
            output_lines.append(f"- {' → '.join(cycle)}\n")
        output_lines.append("\n")

    output_lines.append("## 📁 File Structure & Dependencies\n")
    output_lines.append("```\n")
    tree = build_tree(dict(graph), files)
    output_lines.append(tree + "\n")
    output_lines.append("```\n")

    output_lines.append("\n## 📊 Summary\n")
    output_lines.append(f"- Total files: {len(files)}\n")
    output_lines.append(f"- Root documents: {len(root_files)}\n")
    output_lines.append(
        f"- Total references: {sum(len(refs) for refs in graph.values())}\n"
    )

    if cycles:
        output_lines.append(f"- ⚠️ Cyclic dependencies: {len(cycles)}\n")

    output_text = "".join(output_lines)
    output_file.write_text(output_text, encoding="utf-8")

    print(output_text)
    print(f"📝 Report written to: {output_file}\n")

    if cycles:
        sys.exit(1)


if __name__ == "__main__":
    main()
