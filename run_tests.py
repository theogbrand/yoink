"""
Run the extracted test suite against diy_<package>/ and compute score.

Auto-detects the test directory by looking for diy_*/tests/.

Usage:
    uv run run_tests.py > run.log 2>&1
    grep "^score:" run.log
"""

import re
import subprocess
import sys
from pathlib import Path


def find_test_dir():
    for d in sorted(Path(".").glob("diy_*/tests/generated")):
        if d.is_dir():
            return str(d)
    return "tests"


def main():
    test_dir = find_test_dir()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_dir, "-v", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=300,
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
        if stripped.endswith(" PASSED"):
            passed += 1
        elif stripped.endswith(" FAILED"):
            failed += 1
        elif stripped.endswith(" ERROR"):
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
