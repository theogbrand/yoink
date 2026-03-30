"""
Rewrite imports in curated test files from real package to diy_<package> module.

Usage:
    uv run rewrite_imports.py --package litellm
"""

import argparse
import re
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Rewrite imports in test files")
    parser.add_argument("--package", required=True, help="Package name to replace")
    args = parser.parse_args()

    target = f"diy_{args.package}".replace("-", "_")
    tests_dir = Path(target) / "tests"

    count = 0
    for f in tests_dir.rglob("*.py"):
        content = f.read_text(errors="replace")
        new_content = re.sub(rf"\bfrom {args.package}\b", f"from {target}", content)
        new_content = re.sub(rf"\bimport {args.package}\b", f"import {target}", new_content)
        if new_content != content:
            f.write_text(new_content)
            count += 1

    print(f"Rewrote imports in {count} files ({args.package} -> {target})")


if __name__ == "__main__":
    main()
