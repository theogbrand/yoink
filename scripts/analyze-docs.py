#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.9"
# ///
"""
Analyze markdown documentation structure and dependencies.
Detects cross-references between docs and reports cyclic dependencies.

Run with: uv run scripts/analyze-docs.py docs
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict


def find_markdown_files(root_dir: str) -> dict[str, str]:
    """Find all markdown files and map relative paths to absolute paths."""
    files = {}
    for root, dirs, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.md') and filename != 'STRUCTURE.md':
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, root_dir)
                files[rel_path] = abs_path
    return files


def extract_references(content: str, available_files: dict[str, str]) -> set[str]:
    """Extract markdown file references from content."""
    references = set()

    # Pattern 1: Markdown links [text](path.md)
    markdown_links = re.findall(r'\[.*?\]\((.*?\.md)\)', content)
    for link in markdown_links:
        if link in available_files:
            references.add(link)

    # Pattern 2: Code fence references `filename.md`
    code_refs = re.findall(r'`([^`]*\.md)`', content)
    for ref in code_refs:
        # Try to find the file in available files
        for available in available_files.keys():
            if available.endswith(ref) or ref.endswith(available):
                references.add(available)
                break

    return references


def detect_cycles(graph: dict[str, set[str]], start: str, visited: set[str], rec_stack: set[str]) -> list[str]:
    """Detect cycles using DFS. Returns the cycle path if found."""
    visited.add(start)
    rec_stack.add(start)

    for neighbor in graph.get(start, set()):
        if neighbor not in visited:
            cycle = detect_cycles(graph, neighbor, visited, rec_stack)
            if cycle:
                return cycle
        elif neighbor in rec_stack:
            return [neighbor, start]

    rec_stack.remove(start)
    return []


def find_all_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Find all cyclic dependencies in the graph."""
    visited = set()
    cycles = []

    for node in graph:
        if node not in visited:
            cycle = detect_cycles(graph, node, visited, set())
            if cycle:
                cycles.append(cycle)

    return cycles


def build_tree(graph: dict[str, set[str]], all_files: dict[str, str]) -> str:
    """Build a tree showing folders with files and their dependencies nested."""
    output = []
    displayed_files = set()

    # Group files by directory
    dir_structure = defaultdict(list)
    for file_path in sorted(all_files.keys()):
        if '/' in file_path:
            directory = file_path.rsplit('/', 1)[0]
            filename = file_path.rsplit('/', 1)[1]
        else:
            directory = '.'
            filename = file_path
        dir_structure[directory].append((filename, file_path))

    # Find files that are never referenced (root files)
    all_referenced = set()
    for refs in graph.values():
        all_referenced.update(refs)

    # For each directory
    for i, directory in enumerate(sorted(dir_structure.keys())):
        is_last_dir = i == len(dir_structure) - 1
        dir_prefix = "└── " if is_last_dir else "├── "

        if directory != '.':
            output.append(f"{dir_prefix}{directory}/")
            extension = "    " if is_last_dir else "│   "
        else:
            extension = ""

        files = dir_structure[directory]

        # Helper to add file and its dependencies recursively
        def add_file_tree(file_path: str, prefix: str, is_last: bool):
            if file_path in displayed_files:
                return

            filename = file_path.rsplit('/', 1)[1] if '/' in file_path else file_path
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
        docs_dir = "docs"
    else:
        docs_dir = sys.argv[1]

    if not os.path.isdir(docs_dir):
        print(f"Error: Directory '{docs_dir}' not found")
        sys.exit(1)

    # Output file for the report
    output_file = os.path.join(docs_dir, "STRUCTURE.md")

    # Find all markdown files
    files = find_markdown_files(docs_dir)
    if not files:
        print(f"No markdown files found in '{docs_dir}'")
        sys.exit(1)

    # Build dependency graph
    graph = defaultdict(set)
    for file_path, abs_path in files.items():
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        refs = extract_references(content, files)
        graph[file_path] = refs

    # Check for cycles
    cycles = find_all_cycles(dict(graph))

    # Find root files (files with no incoming references)
    all_referenced = set()
    for refs in graph.values():
        all_referenced.update(refs)

    root_files = [f for f in files.keys() if f not in all_referenced]
    if not root_files:
        # If all files reference something, just pick files with minimal incoming references
        root_files = sorted(files.keys())[:1]

    # Build output
    output_lines = []

    # Title
    output_lines.append("# Documentation Structure\n")
    output_lines.append("Auto-generated documentation map.\n")

    # Cycles section
    if cycles:
        output_lines.append("## ⚠️ Cyclic Dependencies\n")
        for cycle in cycles:
            output_lines.append(f"- {' → '.join(cycle)}\n")
        output_lines.append()

    # Dependency tree
    output_lines.append("## 📁 File Structure & Dependencies\n")
    output_lines.append("```\n")
    tree = build_tree(dict(graph), files)
    output_lines.append(tree + "\n")
    output_lines.append("```\n")

    # Summary section
    output_lines.append(f"\n## 📊 Summary\n")
    output_lines.append(f"- Total files: {len(files)}\n")
    output_lines.append(f"- Root documents: {len(root_files)}\n")
    output_lines.append(f"- Total references: {sum(len(refs) for refs in graph.values())}\n")

    if cycles:
        output_lines.append(f"- ⚠️ Cyclic dependencies: {len(cycles)}\n")
    else:
        output_lines.append(f"- ✓ No cyclic dependencies\n")

    # Write to file
    output_text = "".join(output_lines)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output_text)

    # Print to stdout
    print(output_text)
    print(f"📝 Report written to: {output_file}\n")

    # Exit with error if cycles found
    if cycles:
        sys.exit(1)


if __name__ == "__main__":
    main()
