"""
Clone a target library and extract its test suite for DIY replacement.

Usage:
    uv run prepare.py --url https://github.com/BerriAI/litellm
"""

import argparse
import re
import shutil
import subprocess
from pathlib import Path

CLONE_DIR = Path(".clone")
TESTS_DIR = Path("tests")
REFERENCE_DIR = Path("reference")


def clone_repo(url: str) -> Path:
    if CLONE_DIR.exists():
        shutil.rmtree(CLONE_DIR)
    subprocess.run(["git", "clone", "--depth", "1", url, str(CLONE_DIR)], check=True)
    return CLONE_DIR


def detect_package_name(url: str) -> str:
    """Derive package name from the GitHub repo URL's last path segment."""
    # https://github.com/BerriAI/litellm → litellm
    # https://github.com/BerriAI/litellm.git → litellm
    name = url.rstrip("/").rsplit("/", 1)[-1]
    return name.removesuffix(".git")


def extract_tests(repo_dir: Path, package_name: str) -> int:
    """Copy test files, rewriting imports to point to library module."""
    if TESTS_DIR.exists():
        shutil.rmtree(TESTS_DIR)
    TESTS_DIR.mkdir()

    test_dir = None
    for name in ["tests", "test"]:
        candidate = repo_dir / name
        if candidate.exists() and candidate.is_dir():
            test_dir = candidate
            break

    if not test_dir:
        print("WARNING: No test directory found in repo")
        return 0

    count = 0
    for f in test_dir.rglob("*.py"):
        dest = TESTS_DIR / f.relative_to(test_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = f.read_text(errors="replace")
        content = re.sub(rf"\bfrom {package_name}\b", "from library", content)
        content = re.sub(rf"\bimport {package_name}\b", "import library", content)
        dest.write_text(content)
        count += 1

    return count


def copy_reference(repo_dir: Path, package_name: str):
    """Copy original source code for the agent to study."""
    if REFERENCE_DIR.exists():
        shutil.rmtree(REFERENCE_DIR)
    src = repo_dir / package_name
    if src.exists():
        shutil.copytree(src, REFERENCE_DIR / package_name)


def main():
    parser = argparse.ArgumentParser(description="Prepare DIY environment")
    parser.add_argument("--url", required=True, help="GitHub repo URL to clone")
    args = parser.parse_args()

    print(f"  Cloning {args.url}...")
    repo_dir = clone_repo(args.url)
    print(f"  ✓ Cloned to {CLONE_DIR}/")

    package_name = detect_package_name(args.url)
    print(f"  Detected package: {package_name}")

    print(f"  Extracting tests (rewriting imports: {package_name} → library)...")
    count = extract_tests(repo_dir, package_name)
    print(f"  ✓ {count} test files → {TESTS_DIR}/")

    print(f"  Copying reference source...")
    copy_reference(repo_dir, package_name)
    src_files = len(list((REFERENCE_DIR / package_name).rglob("*.py"))) if (REFERENCE_DIR / package_name).exists() else 0
    print(f"  ✓ {src_files} source files → {REFERENCE_DIR}/{package_name}/")

    shutil.rmtree(CLONE_DIR)
    print(f"  ✓ Cleaned up {CLONE_DIR}/")


if __name__ == "__main__":
    main()
