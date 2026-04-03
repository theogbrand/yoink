#!/usr/bin/env python3
"""
Decomposition queue manager for dependency evaluation workflow.

Manages a queue of libraries to evaluate for decomposition.
Queue state lives in .claude/decomp-queue.json.

Usage:
  python scripts/decomp.py enqueue <lib> [<lib> ...]  Add libraries to queue
  python scripts/decomp.py dequeue                    Pop next library
  python scripts/decomp.py deps <library>             Show pip deps (reference only)
  python scripts/decomp.py status                     Print queue state
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

QUEUE_FILE = Path(".claude/decomp-queue.json")


def ensure_queue_dir() -> None:
    """Ensure .claude directory exists."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)


def read_queue() -> dict:
    """Read queue file. Return empty state if file doesn't exist."""
    if QUEUE_FILE.exists():
        with QUEUE_FILE.open() as f:
            return json.load(f)
    return {"pending": []}


def write_queue(queue: dict) -> None:
    """Write queue file."""
    ensure_queue_dir()
    with QUEUE_FILE.open("w") as f:
        json.dump(queue, f, indent=2)


def get_dependencies(library: str) -> list[str]:
    """
    Discover direct dependencies of a library using uv pip compile.

    This is for REFERENCE ONLY — to help the agent understand what a library
    depends on. It does NOT automatically enqueue anything.

    Returns list of direct dependency package names (no version specifiers).
    """
    try:
        result = subprocess.run(
            ["uv", "pip", "compile", "--no-header", "-"],
            input=library,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        return _parse_uv_compile_output(result.stdout, library)
    except (subprocess.TimeoutExpired, OSError):
        return []


def _parse_uv_compile_output(output: str, library: str) -> list[str]:
    """
    Parse uv pip compile output to extract direct dependencies.

    Output lines look like:
        certifi==2026.2.25
            # via requests
        requests==2.33.1
            # via -r -

    Direct deps have '# via <library>'. The input package has '# via -r -'.
    """
    normalized_library = re.sub(r"[-_.]+", "-", library).lower()
    packages: list[str] = []
    current_package: str | None = None

    for line in output.splitlines():
        package_match = re.match(r"^([a-zA-Z0-9._-]+)==", line.strip())
        if package_match:
            current_package = package_match.group(1)
            continue

        via_match = re.match(r"^\s+# via (.+)$", line)
        if via_match and current_package:
            via_value = via_match.group(1).strip()
            normalized_current = re.sub(r"[-_.]+", "-", current_package).lower()
            if normalized_current == normalized_library:
                current_package = None
                continue
            normalized_via = re.sub(r"[-_.]+", "-", via_value).lower()
            if normalized_via == normalized_library:
                packages.append(current_package)
            current_package = None

    return sorted(set(packages))


def enqueue(items: list[str]) -> None:
    """Add one or more libraries to the queue, deduped against pending."""
    ensure_queue_dir()
    queue = read_queue()

    added = []
    for item in items:
        if item not in queue["pending"]:
            queue["pending"].append(item)
            added.append(item)

    write_queue(queue)

    if added:
        print(f"Enqueued: {', '.join(added)}")
    else:
        print("Nothing new to enqueue (all already pending)")
    print(f"Queue: {len(queue['pending'])} pending")


def dequeue() -> None:
    """Pop next library from queue."""
    queue = read_queue()

    if not queue["pending"]:
        print("Queue empty. Decomposition complete.")
        sys.exit(1)

    next_item = queue["pending"].pop(0)
    write_queue(queue)

    print(f"\nNEXT: {next_item}")
    print(f"Queue: {len(queue['pending'])} remaining")


def deps(library: str) -> None:
    """Show pip dependencies of a library (reference only, does not enqueue)."""
    discovered_deps = get_dependencies(library)
    if discovered_deps:
        print(f"Direct dependencies of {library}:")
        for dep in discovered_deps:
            print(f"  - {dep}")
    else:
        print(f"No dependencies found for {library}")


def status() -> None:
    """Print queue state."""
    queue = read_queue()

    print(f"Pending: {len(queue['pending'])}")
    if queue["pending"]:
        for item in queue["pending"]:
            print(f"  - {item}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Decomposition queue manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/decomp.py enqueue litellm
  python scripts/decomp.py enqueue openai httpx pydantic
  python scripts/decomp.py dequeue
  python scripts/decomp.py deps litellm
  python scripts/decomp.py status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    enqueue_parser = subparsers.add_parser("enqueue", help="Add libraries to queue")
    enqueue_parser.add_argument("items", nargs="+", help="Library names to enqueue")

    subparsers.add_parser("dequeue", help="Pop next library from queue")

    deps_parser = subparsers.add_parser(
        "deps", help="Show pip dependencies (reference only)"
    )
    deps_parser.add_argument("library", help="Library name to inspect")

    subparsers.add_parser("status", help="Print queue state")

    args = parser.parse_args()

    if args.command == "enqueue":
        enqueue(args.items)
    elif args.command == "dequeue":
        dequeue()
    elif args.command == "deps":
        deps(args.library)
    elif args.command == "status":
        status()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
