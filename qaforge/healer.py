"""
Auto-healer — Week 5.

Reads failures from runner.RunResult, asks the configured LLM for fixed code (using
the heal-test SKILL), shows a diff, optionally writes the patch, and
re-runs the failing spec. Loops up to `max_attempts` times.

Public API:
    heal(run_result, ...) -> HealResult
"""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from qaforge.context import PROJECT_ROOT, build_system_prompt
from qaforge.generator import (
    GeneratedFile,
    _parse_files,
    _validate_paths,
    _write_files,
    SPEC_FILE_RE,
)
from qaforge.llm import ask_llm
from qaforge.runner import RunResult, TestFailure, run_tests


_PAGE_IMPORT_RE = re.compile(
    r"^\s*from\s+tests\.pages\.([a-z0-9_]+)\s+import\s+",
    re.MULTILINE,
)


@dataclass
class HealAttempt:
    attempt: int
    failure: TestFailure
    diffs: dict[str, str] = field(default_factory=dict)  # path -> unified diff
    applied: bool = False
    skipped_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class HealResult:
    attempts: list[HealAttempt] = field(default_factory=list)
    final_run: Optional[RunResult] = None
    healed_count: int = 0
    remaining_failures: int = 0
    model: str = ""

    @property
    def succeeded(self) -> bool:
        return self.final_run is not None and self.final_run.all_passed


# A confirmation callback: (path, diff) -> bool. True = apply, False = skip.
ConfirmCallback = Callable[[str, str], bool]


def heal(
    run_result: RunResult,
    *,
    root: Path = PROJECT_ROOT,
    max_attempts: int = 3,
    auto: bool = False,
    confirm: Optional[ConfirmCallback] = None,
    model: Optional[str] = None,
) -> HealResult:
    """
    Loop up to `max_attempts` times: pick the first failure, ask the configured LLM to
    fix it, apply the patch (with confirmation unless `auto`), re-run only
    the affected spec. Stop when all pass or attempts are exhausted.
    """
    result = HealResult(final_run=run_result)
    if run_result.all_passed:
        return result

    system = build_system_prompt(["heal-test"])
    current_run = run_result

    for attempt_num in range(1, max_attempts + 1):
        if not current_run.failures:
            break
        failure = current_run.failures[0]
        attempt = HealAttempt(attempt=attempt_num, failure=failure)
        result.attempts.append(attempt)

        spec_path = root / failure.file
        if not spec_path.is_file():
            attempt.skipped_reason = f"spec file not found: {failure.file}"
            break

        spec_src = spec_path.read_text(encoding="utf-8")
        page_files = _collect_page_objects(spec_src, root)

        user_prompt = _build_user_prompt(
            failure=failure,
            spec_path=failure.file,
            spec_src=spec_src,
            page_files=page_files,
        )

        ask = ask_llm(
            user=user_prompt,
            system=system,
            model=model,
            assistant_prefill='{"files":',
            max_tokens=8192,
        )
        attempt.input_tokens = ask.input_tokens
        attempt.output_tokens = ask.output_tokens
        result.model = ask.model

        try:
            files = _parse_files(ask.text)
        except ValueError as exc:
            attempt.skipped_reason = f"could not parse healer response: {exc}"
            break

        if not files:
            attempt.skipped_reason = "healer returned empty files (not a heal target)"
            break

        try:
            _validate_paths_for_heal(files)
        except ValueError as exc:
            attempt.skipped_reason = f"healer produced invalid paths: {exc}"
            break

        # Compute diffs and confirm
        attempt.diffs = _compute_diffs(files, root)
        approve = True
        if not auto and confirm is not None:
            approve = all(confirm(p, d) for p, d in attempt.diffs.items())

        if not approve:
            attempt.skipped_reason = "user declined patch"
            break

        _write_files(files, root)
        attempt.applied = True

        # Re-run only the affected spec
        current_run = run_tests([failure.file], root=root)
        result.final_run = current_run
        if current_run.all_passed:
            break

    if result.final_run:
        result.remaining_failures = result.final_run.failed + result.final_run.errors
    result.healed_count = sum(1 for a in result.attempts if a.applied)
    return result


# ----------------------- prompt building -----------------------


def _build_user_prompt(
    *,
    failure: TestFailure,
    spec_path: str,
    spec_src: str,
    page_files: dict[str, str],
) -> str:
    """Assemble the heal request the LLM sees."""
    pages_block = ""
    for path, src in page_files.items():
        pages_block += f"\n### {path}\n```python\n{src}\n```\n"

    return (
        "A Playwright + Python test failed. Heal it per the heal-test SKILL.\n\n"
        f"FAILING TEST: {failure.classname}::{failure.name}\n"
        f"FAILURE TYPE: {failure.failure_type}\n"
        f"MESSAGE: {failure.message}\n\n"
        "TRACEBACK:\n"
        "```\n"
        f"{failure.traceback[:3000]}\n"
        "```\n\n"
        f"### {spec_path} (current source)\n"
        "```python\n"
        f"{spec_src}\n"
        "```\n"
        f"{pages_block}\n"
        "Output a single JSON object as specified in the heal-test SKILL. "
        "No prose, no fences. The first character of your reply must be `{`."
    )


def _collect_page_objects(spec_src: str, root: Path) -> dict[str, str]:
    """Find `from tests.pages.<name> import ...` and read those files."""
    page_files: dict[str, str] = {}
    for match in _PAGE_IMPORT_RE.finditer(spec_src):
        page_module = match.group(1)
        page_path = root / "tests" / "pages" / f"{page_module}.py"
        if page_path.is_file():
            rel = f"tests/pages/{page_module}.py"
            page_files[rel] = page_path.read_text(encoding="utf-8")
    return page_files


# ----------------------- patch utilities -----------------------


def _validate_paths_for_heal(files: list[GeneratedFile]) -> None:
    """Healer is allowed to touch only specs and pages."""
    for f in files:
        posix = str(f.path).replace("\\", "/")
        if not (posix.startswith("tests/specs/") or posix.startswith("tests/pages/")):
            raise ValueError(f"healer cannot write outside tests/: {posix!r}")


def _compute_diffs(files: list[GeneratedFile], root: Path) -> dict[str, str]:
    """Return unified diff per file (old → new). New files show as full add."""
    diffs: dict[str, str] = {}
    for f in files:
        posix = str(f.path).replace("\\", "/")
        full = root / f.path
        before = full.read_text(encoding="utf-8") if full.is_file() else ""
        after = f.contents if f.contents.endswith("\n") else f.contents + "\n"
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{posix}",
                tofile=f"b/{posix}",
                n=3,
            )
        )
        diffs[posix] = diff or "(no textual change)"
    return diffs


def format_failure_brief(failure: TestFailure) -> str:
    """One-line summary of a failure for terminal display."""
    label = "FAIL" if failure.failure_type == "failure" else "ERROR"
    return f"[{label}] {failure.file}::{failure.name} — {failure.message}"
