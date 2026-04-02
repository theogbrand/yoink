"""
Run the extracted test suite against diy_<package>/ and compute score.

Auto-detects the test directory by looking for diy_*/tests/.

Usage:
    uv run run_tests.py --project-dir /path/to/project > run.log 2>&1
    grep "^score:" run.log
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def find_test_dir(project_dir: Path) -> str:
    for d in sorted(project_dir.glob("diy_*/tests/generated")):
        if d.is_dir():
            return str(d)
    return str(project_dir / "tests")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    args = parser.parse_args()
    project_dir = args.project_dir.resolve()

    test_dir = find_test_dir(project_dir)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_dir, "-v", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=project_dir,
    )

    output = result.stdout + result.stderr
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    # Count individual test results from verbose output lines
    # Format: "path/test_file.py::test_name PASSED" / "FAILED" / "ERROR"
    passed = failed = errors = 0
    for line in output.splitlines():
        stripped = line.strip()
        if " PASSED" in stripped:
            passed += 1
        elif " FAILED" in stripped:
            failed += 1
        elif " ERROR" in stripped:
            errors += 1

    # Also count collection errors (files that couldn't even be imported)
    # These show as "ERROR path/file.py" in the summary section
    collection_errors = 0
    m = re.search(r"(\d+) error", output)
    if m:
        collection_errors = int(m.group(1)) - errors

    total = passed + failed + errors
    score = passed / total if total > 0 else 0.0

    print("\n--- Results ---")
    print(f"score:          {score:.6f}")
    print(f"passed:         {passed}")
    print(f"failed:         {failed}")
    print(f"errors:         {errors}")
    print(f"total:          {total}")
    if collection_errors > 0:
        print(f"collection_errors: {collection_errors} (files that failed to import)")


if __name__ == "__main__":
    main()
