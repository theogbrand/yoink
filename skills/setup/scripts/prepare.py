"""
Clone a target library and copy reference source + raw tests for DIY replacement.

Usage:
    uv run prepare.py --url https://github.com/BerriAI/litellm
"""

import argparse
import shutil
import subprocess
from pathlib import Path

CLONE_DIR = Path(".clone")
REFERENCE_DIR = Path(".slash_diy/reference")


def clone_repo(url: str, package_name: str) -> Path:
    """Clone repo fetching only the package source and test directories."""
    if CLONE_DIR.exists():
        shutil.rmtree(CLONE_DIR)
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--no-tags",
            "--no-checkout",
            url,
            str(CLONE_DIR),
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(CLONE_DIR),
            "sparse-checkout",
            "set",
            "--no-cone",
            f"/{package_name}/",
            "/tests/",
            "/test/",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(CLONE_DIR), "checkout"],
        check=True,
    )
    return CLONE_DIR


def detect_package_name(url: str) -> str:
    """Derive package name from the GitHub repo URL's last path segment."""
    # https://github.com/BerriAI/litellm → litellm
    # https://github.com/BerriAI/litellm.git → litellm
    name = url.rstrip("/").rsplit("/", 1)[-1]
    return name.removesuffix(".git")


def copy_raw_tests(repo_dir: Path) -> int:
    """Copy raw test files to reference/tests/ for subagent discovery (no import rewriting)."""
    ref_tests = REFERENCE_DIR / "tests"
    if ref_tests.exists():
        shutil.rmtree(ref_tests)

    test_dir = None
    for name in ["tests", "test"]:
        candidate = repo_dir / name
        if candidate.exists() and candidate.is_dir():
            test_dir = candidate
            break

    if not test_dir:
        print("WARNING: No test directory found in repo")
        return 0

    shutil.copytree(test_dir, ref_tests, copy_function=_skip_missing)
    count = len(list(ref_tests.rglob("*.py")))
    return count


def _skip_missing(_src: str, _dst: str):
    """shutil copy_function that silently skips files missing on disk (sparse checkout stubs)."""
    src_path = Path(_src)
    if not src_path.exists():
        return
    shutil.copy2(_src, _dst)


def copy_reference(repo_dir: Path, package_name: str):
    """Copy original source code for the agent to study."""
    dest = REFERENCE_DIR / package_name
    if dest.exists():
        shutil.rmtree(dest)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    src = repo_dir / package_name
    if src.exists():
        shutil.copytree(src, dest, copy_function=_skip_missing)


def main():
    parser = argparse.ArgumentParser(description="Prepare DIY environment")
    parser.add_argument("--url", required=True, help="GitHub repo URL to clone")
    args = parser.parse_args()

    package_name = detect_package_name(args.url)
    print(f"  Detected package: {package_name}")

    print(f"  Cloning {args.url} (sparse: {package_name}/, tests/)...")
    repo_dir = clone_repo(args.url, package_name)
    print(f"  ✓ Cloned to {CLONE_DIR}/")

    print("  Copying reference source...")
    copy_reference(repo_dir, package_name)
    src_files = (
        len(list((REFERENCE_DIR / package_name).rglob("*.py")))
        if (REFERENCE_DIR / package_name).exists()
        else 0
    )
    print(f"  ✓ {src_files} source files → {REFERENCE_DIR}/{package_name}/")

    print(f"  Copying raw tests to {REFERENCE_DIR}/tests/ for subagent discovery...")
    count = copy_raw_tests(repo_dir)
    print(f"  ✓ {count} test files → {REFERENCE_DIR}/tests/")

    shutil.rmtree(CLONE_DIR)
    print(f"  ✓ Cleaned up {CLONE_DIR}/")


if __name__ == "__main__":
    main()
