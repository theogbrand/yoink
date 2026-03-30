#!/usr/bin/env python3
"""
Decomposition queue manager for dependency evaluation workflow.

Manages a queue of Python libraries to evaluate for decomposition.
Queue state lives in .claude/decomp-queue.json.

Usage:
  python scripts/decomp.py enqueue <library>    Discover deps, add to queue
  python scripts/decomp.py dequeue              Pop next lib, print instructions
  python scripts/decomp.py status               Print queue state
"""

import argparse
import json
import re
import subprocess
import sys
from importlib.metadata import requires, PackageNotFoundError
from pathlib import Path
from urllib.request import urlopen


QUEUE_FILE = Path(".claude/decomp-queue.json")


def ensure_queue_dir() -> None:
    """Ensure .claude directory exists."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)


def read_queue() -> dict:
    """Read queue file. Return empty state if file doesn't exist."""
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE) as f:
            return json.load(f)
    return {"root_library": None, "pending": []}


def write_queue(queue: dict) -> None:
    """Write queue file."""
    ensure_queue_dir()
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)


def get_dependencies(library: str) -> list[str]:
    """
    Discover direct dependencies of a library.

    Try importlib.metadata first, fall back to pip show, then PyPI API.
    Returns list of base package names (no version specifiers).
    """
    # Try importlib.metadata
    try:
        reqs = requires(library)
        if reqs:
            return _parse_requires(reqs)
    except PackageNotFoundError:
        pass

    # Try pip show
    try:
        result = subprocess.run(
            ["pip", "show", library],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            return _parse_pip_show(result.stdout)
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Try PyPI JSON API
    try:
        with urlopen(f"https://pypi.org/pypi/{library}/json", timeout=10) as response:
            data = json.loads(response.read().decode())
            requires_dist = data.get("info", {}).get("requires_dist") or []
            return _parse_requires(requires_dist)
    except (OSError, json.JSONDecodeError):
        pass

    # No deps found
    return []


def _parse_requires(requires_list: list[str]) -> list[str]:
    """
    Parse requires list from importlib.metadata or PyPI API.

    Each entry is like:
      'requests (>=2.0)'
      'urllib3>=1.26'
      'urllib3 ; extra == "security"'
      'certifi'

    Extract base package names only.
    """
    packages = []
    for req in requires_list:
        # Strip extras markers ('; ...')
        if ";" in req:
            req = req.split(";")[0]
        # Strip version specifiers like >=, <, ==, !=, ~=, etc.
        # Match the package name: everything before the first version operator
        match = re.match(r"^([a-zA-Z0-9._-]+)", req.strip())
        if match:
            package_name = match.group(1).strip()
            if package_name:
                packages.append(package_name)
    # Deduplicate and sort
    return sorted(set(packages))


def _parse_pip_show(output: str) -> list[str]:
    """Parse pip show output. Extract 'Requires:' line."""
    for line in output.split("\n"):
        if line.startswith("Requires:"):
            reqs_str = line[len("Requires:") :].strip()
            if not reqs_str:
                return []
            # Requires: lib1, lib2, lib3
            packages = [p.strip() for p in reqs_str.split(",")]
            return sorted(set(packages))
    return []


def enqueue(library: str) -> None:
    """Discover dependencies and add to queue."""
    ensure_queue_dir()
    queue = read_queue()

    # Initialize queue if this is the first enqueue
    if queue["root_library"] is None:
        queue["root_library"] = library
        queue["pending"] = []

    # Discover dependencies
    deps = get_dependencies(library)

    # Filter out deps already in pending
    new_deps = [dep for dep in deps if dep not in queue["pending"]]

    # Add to queue
    queue["pending"].extend(new_deps)

    write_queue(queue)

    if new_deps:
        print(f"Added {len(new_deps)} deps: {new_deps}")
    else:
        print(f"No new deps found for {library}")
    print(f"Queue: {len(queue['pending'])} pending")


def dequeue() -> None:
    """Pop next library from queue and print instructions."""
    queue = read_queue()

    if not queue["pending"]:
        print("Queue empty. Decomposition complete.")
        return

    # Pop first item
    next_lib = queue["pending"].pop(0)
    write_queue(queue)

    print(f"\nNEXT: {next_lib}\n")
    print(f"Queue: {len(queue['pending'])} remaining\n")
    print("Evaluate using docs/decomposition/decomposition-orchestrator.md")
    print("Then run:\n")
    print(f"  python scripts/decomp.py enqueue {next_lib}   # if decomposed (discovers subdeps)")
    print("  python scripts/decomp.py dequeue             # if kept (get next lib)\n")


def status() -> None:
    """Print queue state."""
    queue = read_queue()

    print(f"Root library: {queue['root_library']}")
    print(f"Pending: {len(queue['pending'])}")
    if queue["pending"]:
        for lib in queue["pending"]:
            print(f"  - {lib}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Decomposition queue manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/decomp.py enqueue requests
  python scripts/decomp.py dequeue
  python scripts/decomp.py status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # enqueue subcommand
    enqueue_parser = subparsers.add_parser(
        "enqueue", help="Discover and enqueue dependencies"
    )
    enqueue_parser.add_argument("library", help="Library name")

    # dequeue subcommand
    subparsers.add_parser("dequeue", help="Pop next library from queue")

    # status subcommand
    subparsers.add_parser("status", help="Print queue state")

    args = parser.parse_args()

    if args.command == "enqueue":
        enqueue(args.library)
    elif args.command == "dequeue":
        dequeue()
    elif args.command == "status":
        status()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
