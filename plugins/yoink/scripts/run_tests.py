"""
Run the extracted test suite against yoink_<package>/ and compute score.

Auto-detects the test directory by looking for yoink_*/tests/.

Usage:
    uv run run_tests.py --project-dir /path/to/project
    uv run run_tests.py --project-dir /path/to/project --summary-only
"""

import argparse
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResults:
    passed: int
    failed: int
    errors: int

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors

    @property
    def score(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0


def parse_junit_xml(junit_xml_path: Path) -> TestResults:
    """Parse structured results from JUnit XML.

    pytest wraps <testsuite> inside a <testsuites> root, so we find the actual
    <testsuite> element(s) and sum their attributes.
    """
    tree = ET.parse(junit_xml_path)
    root = tree.getroot()

    testsuite_elements = (
        root.findall("testsuite") if root.tag == "testsuites" else [root]
    )
    total_tests = 0
    failed = 0
    errors = 0
    for testsuite in testsuite_elements:
        total_tests += int(testsuite.attrib.get("tests", 0))
        failed += int(testsuite.attrib.get("failures", 0))
        errors += int(testsuite.attrib.get("errors", 0))
    passed = total_tests - failed - errors

    return TestResults(passed=passed, failed=failed, errors=errors)


def find_test_dir(project_dir: Path) -> Path:
    for d in sorted(project_dir.glob("yoink_*/tests/generated")):
        if d.is_dir():
            return d
    return project_dir / "tests"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Suppress pytest output, print only the results summary",
    )
    args = parser.parse_args()
    project_dir = args.project_dir.resolve()

    test_dir = find_test_dir(project_dir)

    with tempfile.TemporaryDirectory() as tmp_dir:
        junit_xml_path = Path(tmp_dir) / "results.xml"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(test_dir),
                "-v",
                "--tb=short",
                f"--junitxml={junit_xml_path}",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=project_dir,
        )

        if not args.summary_only:
            print(result.stdout)
            print(result.stderr)

        results = parse_junit_xml(junit_xml_path)

    print("\n--- Results ---")
    print(f"score:          {results.score:.6f}")
    print(f"passed:         {results.passed}")
    print(f"failed:         {results.failed}")
    print(f"errors:         {results.errors}")
    print(f"total:          {results.total}")


if __name__ == "__main__":
    main()
