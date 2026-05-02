"""
Test runner — Week 5.

Wraps `pytest` and parses its JUnit XML output into structured results
the healer can consume. Uses pytest's built-in --junit-xml (no extra deps).

Public API:
    run_tests(paths=None, ...) -> RunResult
"""
from __future__ import annotations

import html
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Optional

from qaforge.context import PROJECT_ROOT


@dataclass
class TestFailure:
    """One failing or erroring test case."""
    __test__: ClassVar[bool] = False

    classname: str          # e.g. "tests.specs.test_login.TestLogin"
    name: str               # e.g. "test_tc_001_standard_user"
    file: str               # spec file path relative to project root
    message: str            # short failure message (first line of traceback)
    traceback: str          # full failure text
    failure_type: str       # "failure" or "error"


@dataclass
class TestCaseResult:
    """One pytest test case result, normalized from JUnit XML."""
    __test__: ClassVar[bool] = False

    classname: str
    name: str
    file: str
    status: str             # "passed", "failed", "error", or "skipped"
    duration_s: float = 0.0
    message: str = ""


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
    cases: list[TestCaseResult] = field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""
    report_path: Optional[Path] = None

    @property
    def all_passed(self) -> bool:
        return self.return_code == 0 and self.failed == 0 and self.errors == 0


def run_tests(
    paths: Optional[list[str]] = None,
    *,
    root: Path = PROJECT_ROOT,
    extra_args: Optional[list[str]] = None,
    report_path: Optional[Path] = None,
    write_report: bool = True,
    timeout: int = 300,
) -> RunResult:
    """Run pytest on the given paths (or all of tests/specs/) and parse results."""
    targets = paths if paths else ["tests/specs"]
    extra_args = extra_args or []
    report_path = report_path or root / "test-results" / "qaforge-report.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_root = root / ".tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    basetemp = tmp_root / f"qaforge-pytest-{uuid.uuid4().hex}"
    has_basetemp = any(arg == "--basetemp" or arg.startswith("--basetemp=") for arg in extra_args)

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
            *( [] if has_basetemp else [f"--basetemp={basetemp}"] ),
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
        if write_report:
            _write_html_report(result, report_path, targets)
            result.report_path = report_path
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
    cases: list[TestCaseResult] = []
    for case in suite.findall("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        spec_file = _classname_to_file(classname, root)
        duration_s = float(case.get("time", 0.0))
        status = "passed"
        message = ""

        for kind in ("failure", "error"):
            node = case.find(kind)
            if node is None:
                continue
            status = "failed" if kind == "failure" else "error"
            message_lines = (node.get("message") or "").strip().splitlines()[0:1]
            message = message_lines[0] if message_lines else ""
            failures.append(TestFailure(
                classname=classname,
                name=name,
                file=spec_file,
                message=message,
                traceback=(node.text or "").strip(),
                failure_type=kind,
            ))
            break
        else:
            skipped_node = case.find("skipped")
            if skipped_node is not None:
                status = "skipped"
                message = (skipped_node.get("message") or "").strip()

        cases.append(TestCaseResult(
            classname=classname,
            name=name,
            file=spec_file,
            status=status,
            duration_s=duration_s,
            message=message,
        ))

    return RunResult(
        total=total,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        duration_s=duration,
        failures=failures,
        cases=cases,
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


def _write_html_report(result: RunResult, path: Path, targets: list[str]) -> None:
    """Write a self-contained HTML report for the latest pytest run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    status_label = "Passed" if result.all_passed else "Needs attention"
    status_class = "passed" if result.all_passed else "failed"
    target_text = ", ".join(targets)

    rows = "\n".join(_case_row(case) for case in result.cases)
    if not rows:
        rows = (
            '<tr><td colspan="5" class="empty">'
            "No test cases were reported. Check pytest output below."
            "</td></tr>"
        )

    failures = "\n".join(_failure_block(failure) for failure in result.failures)
    if not failures:
        failures = '<p class="empty">No failures or errors.</p>'

    stdout = html.escape(result.raw_stdout.strip() or "(empty)")
    stderr = html.escape(result.raw_stderr.strip() or "(empty)")

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QAForge Test Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8f3;
      --panel: #ffffff;
      --ink: #1d2320;
      --muted: #647067;
      --line: #dfe5dd;
      --pass: #16794c;
      --fail: #b42318;
      --skip: #8a5a00;
      --info: #235789;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", Tahoma, sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(1120px, calc(100% - 32px));
      margin: 32px auto;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      margin-bottom: 24px;
      padding-bottom: 18px;
    }}
    h1, h2 {{ margin: 0; }}
    h1 {{ font-size: 32px; }}
    h2 {{ font-size: 20px; margin-top: 28px; margin-bottom: 12px; }}
    .meta {{ color: var(--muted); margin-top: 8px; }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      color: #fff;
      font-weight: 700;
      padding: 4px 10px;
      margin-left: 8px;
      vertical-align: middle;
    }}
    .badge.passed {{ background: var(--pass); }}
    .badge.failed {{ background: var(--fail); }}
    .summary {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      margin: 24px 0;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .card strong {{ display: block; font-size: 28px; line-height: 1; }}
    .card span {{ color: var(--muted); font-size: 13px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #eef3eb; font-size: 13px; }}
    tr:last-child td {{ border-bottom: 0; }}
    code, pre {{
      font-family: Consolas, "Liberation Mono", monospace;
      font-size: 13px;
    }}
    pre {{
      background: #17201b;
      color: #f3fbf6;
      border-radius: 8px;
      overflow: auto;
      padding: 14px;
      white-space: pre-wrap;
    }}
    .status {{
      border-radius: 999px;
      color: #fff;
      display: inline-block;
      font-size: 12px;
      font-weight: 700;
      padding: 2px 8px;
      text-transform: uppercase;
    }}
    .status.passed {{ background: var(--pass); }}
    .status.failed, .status.error {{ background: var(--fail); }}
    .status.skipped {{ background: var(--skip); }}
    .failure {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-left: 4px solid var(--fail);
      border-radius: 8px;
      margin-bottom: 12px;
      padding: 14px;
    }}
    .failure p {{ margin: 4px 0 12px; color: var(--muted); }}
    .empty {{ color: var(--muted); }}
    @media (max-width: 720px) {{
      main {{ width: min(100% - 20px, 1120px); margin: 20px auto; }}
      table {{ display: block; overflow-x: auto; }}
      h1 {{ font-size: 26px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>QAForge Test Report <span class="badge {status_class}">{status_label}</span></h1>
      <div class="meta">Generated {html.escape(generated_at)} for <code>{html.escape(target_text)}</code></div>
    </header>

    <section class="summary" aria-label="Test summary">
      {_summary_card("Total", result.total)}
      {_summary_card("Passed", result.passed)}
      {_summary_card("Failed", result.failed)}
      {_summary_card("Errored", result.errors)}
      {_summary_card("Skipped", result.skipped)}
      {_summary_card("Duration", f"{result.duration_s:.2f}s")}
    </section>

    <section>
      <h2>Test Cases</h2>
      <table>
        <thead>
          <tr>
            <th>Status</th>
            <th>Test</th>
            <th>File</th>
            <th>Duration</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Failures</h2>
      {failures}
    </section>

    <section>
      <h2>Pytest Output</h2>
      <h3>stdout</h3>
      <pre>{stdout}</pre>
      <h3>stderr</h3>
      <pre>{stderr}</pre>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _summary_card(label: str, value: object) -> str:
    return f'<div class="card"><strong>{html.escape(str(value))}</strong><span>{html.escape(label)}</span></div>'


def _case_row(case: TestCaseResult) -> str:
    return (
        "<tr>"
        f'<td><span class="status {html.escape(case.status)}">{html.escape(case.status)}</span></td>'
        f"<td><code>{html.escape(case.classname)}::{html.escape(case.name)}</code></td>"
        f"<td><code>{html.escape(case.file)}</code></td>"
        f"<td>{case.duration_s:.2f}s</td>"
        f"<td>{html.escape(case.message)}</td>"
        "</tr>"
    )


def _failure_block(failure: TestFailure) -> str:
    title = f"{failure.classname}::{failure.name}"
    return (
        '<article class="failure">'
        f"<strong>{html.escape(title)}</strong>"
        f"<p>{html.escape(failure.file)} | {html.escape(failure.failure_type)} | {html.escape(failure.message)}</p>"
        f"<pre>{html.escape(failure.traceback)}</pre>"
        "</article>"
    )


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
