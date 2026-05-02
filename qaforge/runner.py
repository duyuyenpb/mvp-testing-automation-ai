"""
Test runner — Week 5.

Wraps `pytest` and parses its JUnit XML output into structured results
the healer can consume. Uses pytest's built-in --junit-xml (no extra deps).

Public API:
    run_tests(paths=None, ...) -> RunResult
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from qaforge.context import PROJECT_ROOT


@dataclass
class TestFailure:
    """One failing or erroring test case."""
    classname: str          # e.g. "tests.specs.test_login.TestLogin"
    name: str               # e.g. "test_tc_001_standard_user"
    file: str               # spec file path relative to project root
    message: str            # short failure message (first line of traceback)
    traceback: str          # full failure text
    failure_type: str       # "failure" or "error"


@dataclass
class RunResult:
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_s: float = 0.0
    return_code: int = 0
    failures: list[TestFailure] = field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""

    @property
    def all_passed(self) -> bool:
        return self.return_code == 0 and self.failed == 0 and self.errors == 0


def run_tests(
    paths: Optional[list[str]] = None,
    *,
    root: Path = PROJECT_ROOT,
    extra_args: Optional[list[str]] = None,
    timeout: int = 300,
) -> RunResult:
    """Run pytest on the given paths (or all of tests/specs/) and parse results."""
    targets = paths if paths else ["tests/specs"]
    extra_args = extra_args or []

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".xml", delete=False, dir=str(root)
    ) as tmp:
        xml_path = Path(tmp.name)

    try:
        cmd = [
            sys.executable, "-m", "pytest",
            *targets,
            f"--junit-xml={xml_path.name}",
            "--tb=short",
            "-q",
            *extra_args,
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        result = _parse_junit_xml(xml_path, root)
        result.return_code = proc.returncode
        result.raw_stdout = proc.stdout
        result.raw_stderr = proc.stderr
        return result
    finally:
        if xml_path.exists():
            xml_path.unlink()


def _parse_junit_xml(xml_path: Path, root: Path) -> RunResult:
    """Parse pytest's JUnit XML report into a RunResult."""
    if not xml_path.is_file() or xml_path.stat().st_size == 0:
        return RunResult()

    tree = ET.parse(str(xml_path))
    suite = tree.getroot()
    if suite.tag == "testsuites":
        # pytest >= 8 wraps in <testsuites>
        suite = suite.find("testsuite") or suite

    total = int(suite.get("tests", 0))
    failed = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    duration = float(suite.get("time", 0.0))
    passed = total - failed - errors - skipped

    failures: list[TestFailure] = []
    for case in suite.findall("testcase"):
        for kind in ("failure", "error"):
            node = case.find(kind)
            if node is None:
                continue
            classname = case.get("classname", "")
            name = case.get("name", "")
            spec_file = _classname_to_file(classname, root)
            message = (node.get("message") or "").strip().splitlines()[0:1]
            failures.append(TestFailure(
                classname=classname,
                name=name,
                file=spec_file,
                message=message[0] if message else "",
                traceback=(node.text or "").strip(),
                failure_type=kind,
            ))
            break

    return RunResult(
        total=total,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        duration_s=duration,
        failures=failures,
    )


def _classname_to_file(classname: str, root: Path) -> str:
    """`tests.specs.test_login.TestLogin` -> `tests/specs/test_login.py`."""
    if not classname:
        return ""
    parts = classname.split(".")
    while parts and not parts[-1].startswith("test_"):
        parts.pop()
    if not parts:
        return ""
    rel = "/".join(parts) + ".py"
    if (root / rel).is_file():
        return rel
    return rel


def format_summary(result: RunResult) -> str:
    """One-line human summary."""
    parts = [f"{result.passed} passed"]
    if result.failed:
        parts.append(f"{result.failed} failed")
    if result.errors:
        parts.append(f"{result.errors} errored")
    if result.skipped:
        parts.append(f"{result.skipped} skipped")
    return f"{', '.join(parts)} in {result.duration_s:.2f}s"


def diagnose_environment(result: RunResult) -> Optional[str]:
    """Return an actionable hint when failures point to a setup problem."""
    blob = " ".join(f.traceback for f in result.failures) + " " + result.raw_stderr
    if "Executable doesn't exist" in blob or "playwright install" in blob:
        return (
            "Playwright browser is not installed.\n"
            "  Run: python -m playwright install chromium"
        )
    if "ModuleNotFoundError: No module named 'playwright'" in blob:
        return (
            "pytest-playwright / playwright is not installed.\n"
            "  Run: pip install -e '.[test]'"
        )
    return None
