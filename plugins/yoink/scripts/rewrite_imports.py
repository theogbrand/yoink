"""
Rewrite imports in Python files from a real package to its yoink_<package> replacement.

Usage:
    uv run rewrite_imports.py --package litellm --target-dir yoink_litellm/tests/generated
    uv run rewrite_imports.py --package openai --target-dir yoink_litellm
"""

import argparse
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rewrite imports from a package to its yoink_ replacement"
    )
    parser.add_argument("--package", required=True, help="Package name to replace")
    parser.add_argument(
        "--target-dir", required=True, help="Directory to rewrite files in"
    )
    args = parser.parse_args()

    package_name = args.package.replace("-", "_").removeprefix("yoink_")
    yoink_package_name = f"yoink_{package_name}"
    target_dir = Path(args.target_dir)

    if not target_dir.is_dir():
        print(f"Error: {target_dir} does not exist")
        raise SystemExit(1)

    rewritten_file_count = 0
    for python_file in target_dir.rglob("*.py"):
        content = python_file.read_text(errors="replace")
        new_content = re.sub(
            rf"\bfrom {package_name}\b", f"from {yoink_package_name}", content
        )
        new_content = re.sub(
            rf"\bimport {package_name}\b",
            f"import {yoink_package_name}",
            new_content,
        )
        new_content = re.sub(
            rf"\b{package_name}\.", f"{yoink_package_name}.", new_content
        )
        if new_content != content:
            python_file.write_text(new_content)
            rewritten_file_count += 1

    print(
        f"Rewrote imports in {rewritten_file_count} files "
        f"({package_name} -> {yoink_package_name}) within {target_dir}/"
    )


if __name__ == "__main__":
    main()
