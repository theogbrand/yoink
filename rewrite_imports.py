"""
Rewrite imports in curated test files from real package to library module.

Usage:
    uv run rewrite_imports.py --package litellm
"""

import argparse
import re
from pathlib import Path

TESTS_DIR = Path("tests")


def main():
    parser = argparse.ArgumentParser(description="Rewrite imports in test files")
    parser.add_argument("--package", required=True, help="Package name to replace with 'library'")
    args = parser.parse_args()

    count = 0
    for f in TESTS_DIR.rglob("*.py"):
        content = f.read_text(errors="replace")
        new_content = re.sub(rf"\bfrom {args.package}\b", "from library", content)
        new_content = re.sub(rf"\bimport {args.package}\b", "import library", new_content)
        if new_content != content:
            f.write_text(new_content)
            count += 1

    print(f"Rewrote imports in {count} files ({args.package} -> library)")


if __name__ == "__main__":
    main()
