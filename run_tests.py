"""
Run the extracted test suite against library.py and compute score.

Analogous to backtest.py in auto-researchtrading.

Usage:
    uv run run_tests.py > run.log 2>&1
    grep "^score:" run.log
"""

import re
import subprocess
import sys


def main():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-q"],
        capture_output=True,
        text=True,
        timeout=300,
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    # Parse pytest summary line for pass/fail counts
    passed = failed = errors = 0
    for line in (result.stdout + result.stderr).splitlines():
        if any(w in line for w in ["passed", "failed", "error"]):
            m = re.search(r"(\d+) passed", line)
            if m:
                passed = int(m.group(1))
            m = re.search(r"(\d+) failed", line)
            if m:
                failed = int(m.group(1))
            m = re.search(r"(\d+) error", line)
            if m:
                errors = int(m.group(1))

    total = passed + failed + errors
    score = passed / total if total > 0 else 0.0

    print(f"\n--- Results ---")
    print(f"score:          {score:.6f}")
    print(f"passed:         {passed}")
    print(f"failed:         {failed}")
    print(f"errors:         {errors}")
    print(f"total:          {total}")


if __name__ == "__main__":
    main()
