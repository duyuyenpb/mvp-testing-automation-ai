from __future__ import annotations

from qaforge.runner import RunResult, TestCaseResult, TestFailure, _write_html_report


def test_write_html_report_includes_summary_cases_and_failures(tmp_path) -> None:
    report_path = tmp_path / "qaforge-report.html"
    result = RunResult(
        total=2,
        passed=1,
        failed=1,
        duration_s=1.25,
        return_code=1,
        cases=[
            TestCaseResult(
                classname="tests.specs.test_login.TestLogin",
                name="test_tc_001_login",
                file="tests/specs/test_login.py",
                status="passed",
                duration_s=0.25,
            ),
            TestCaseResult(
                classname="tests.specs.test_login.TestLogin",
                name="test_tc_002_bad_password",
                file="tests/specs/test_login.py",
                status="failed",
                duration_s=1.0,
                message="expected error message",
            ),
        ],
        failures=[
            TestFailure(
                classname="tests.specs.test_login.TestLogin",
                name="test_tc_002_bad_password",
                file="tests/specs/test_login.py",
                message="expected error message",
                traceback="<script>alert('escaped')</script>",
                failure_type="failure",
            )
        ],
        raw_stdout="1 failed, 1 passed",
        raw_stderr="",
    )

    _write_html_report(result, report_path, ["tests/specs/test_login.py"])

    html = report_path.read_text(encoding="utf-8")
    assert "QAForge Test Report" in html
    assert "Needs attention" in html
    assert "test_tc_001_login" in html
    assert "test_tc_002_bad_password" in html
    assert "&lt;script&gt;alert(&#x27;escaped&#x27;)&lt;/script&gt;" in html
