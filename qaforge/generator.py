"""
Test code generator — Week 3-4.

Takes a Markdown test plan, asks Claude (with the `write-test` SKILL +
gold-standard reference code) to produce one spec file plus any new Page
Objects, validates them with `python -m py_compile`, optionally runs a
single first-run check via pytest.

Public API:
    generate_from_plan(plan_path, ...) -> GenerateResult
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from qaforge.context import PROJECT_ROOT, build_system_prompt
from qaforge.llm import ask_claude

ALLOWED_PREFIXES = ("tests/specs/", "tests/pages/")
SPEC_FILE_RE = re.compile(r"^tests/specs/test_[a-z0-9_]+\.py$")
PAGE_FILE_RE = re.compile(r"^tests/pages/[a-z0-9_]+_page\.py$")


@dataclass(frozen=True)
class GeneratedFile:
    path: Path
    contents: str


@dataclass
class GenerateResult:
    files: list[GeneratedFile]
    compile_ok: bool
    compile_errors: list[str] = field(default_factory=list)
    first_run_ok: Optional[bool] = None
    first_run_summary: Optional[str] = None
    attempts: int = 1
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    plan_slug: str = ""


def generate_from_plan(
    plan_path: Path,
    *,
    root: Path = PROJECT_ROOT,
    retry_on_compile_error: bool = True,
    run_first: bool = True,
    model: Optional[str] = None,
) -> GenerateResult:
    """Generate spec + POMs from a saved plan markdown file."""
    plan_path = plan_path.resolve()
    if not plan_path.is_file():
        raise FileNotFoundError(f"plan file not found: {plan_path}")

    plan_md = plan_path.read_text(encoding="utf-8")
    slug = _slug_from_plan_filename(plan_path.name)

    existing_pages = _list_existing_pages(root)
    system = build_system_prompt(["write-test"])

    user = _build_user_prompt(plan_md=plan_md, slug=slug, existing_pages=existing_pages)

    total_in = 0
    total_out = 0
    chosen_model = ""
    attempts = 0
    compile_errors: list[str] = []
    files: list[GeneratedFile] = []

    last_user = user
    max_attempts = 2 if retry_on_compile_error else 1

    while attempts < max_attempts:
        attempts += 1
        result = ask_claude(
            user=last_user,
            system=system,
            model=model,
            assistant_prefill='{"files":',
            max_tokens=8192,
        )
        total_in += result.input_tokens
        total_out += result.output_tokens
        chosen_model = result.model

        try:
            files = _parse_files(result.text)
            _validate_paths(files, slug)
        except ValueError as exc:
            compile_errors = [f"parse/validate: {exc}"]
            if attempts < max_attempts:
                last_user = _build_retry_prompt(user, str(exc), result.text)
                continue
            return GenerateResult(
                files=[],
                compile_ok=False,
                compile_errors=compile_errors,
                attempts=attempts,
                input_tokens=total_in,
                output_tokens=total_out,
                model=chosen_model,
                plan_slug=slug,
            )

        _write_files(files, root)
        compile_ok, compile_errors = _compile_check(files, root)
        if compile_ok:
            break

        if attempts < max_attempts:
            last_user = _build_retry_prompt(user, "\n".join(compile_errors), result.text)

    first_run_ok: Optional[bool] = None
    first_run_summary: Optional[str] = None
    if compile_ok and run_first:
        spec_files = [f for f in files if SPEC_FILE_RE.match(str(f.path).replace("\\", "/"))]
        if spec_files:
            first_run_ok, first_run_summary = _first_run_check(spec_files[0], root)

    return GenerateResult(
        files=files,
        compile_ok=compile_ok,
        compile_errors=compile_errors,
        first_run_ok=first_run_ok,
        first_run_summary=first_run_summary,
        attempts=attempts,
        input_tokens=total_in,
        output_tokens=total_out,
        model=chosen_model,
        plan_slug=slug,
    )


# ----------------------- prompt building -----------------------


def _build_user_prompt(*, plan_md: str, slug: str, existing_pages: list[str]) -> str:
    pages_blob = (
        "\n".join(f"- tests/pages/{p}" for p in existing_pages) if existing_pages else "(none)"
    )
    return (
        "Generate Python + Playwright code for the following test plan.\n\n"
        f"TARGET SPEC FILENAME: tests/specs/test_{slug}.py\n"
        f"BASE_URL: https://www.saucedemo.com\n"
        f"EXISTING PAGE OBJECTS (reuse these — do NOT redefine):\n{pages_blob}\n\n"
        "Output a single JSON object as specified in the write-test SKILL. "
        "No prose, no fences. The first character of your reply must be `{`.\n\n"
        "TEST PLAN:\n"
        "```markdown\n"
        f"{plan_md.strip()}\n"
        "```"
    )


def _build_retry_prompt(original_user: str, error: str, prev_attempt: str) -> str:
    truncated = prev_attempt[:1500] + ("\n…[truncated]" if len(prev_attempt) > 1500 else "")
    return (
        f"{original_user}\n\n"
        "PREVIOUS ATTEMPT FAILED. Errors:\n"
        f"{error}\n\n"
        "Previous output (truncated):\n"
        f"{truncated}\n\n"
        "Re-emit the FULL JSON object with all files corrected. "
        "Pay attention to: missing imports, broken `from tests.pages...` paths, "
        "syntax errors, and forbidden patterns from the SKILL."
    )


# ----------------------- parsing & validation -----------------------


_FENCE_OPEN_RE = re.compile(r"^\s*```(?:json)?\s*\n", re.MULTILINE)
_FENCE_CLOSE_RE = re.compile(r"\n\s*```\s*$")


def _parse_files(raw: str) -> list[GeneratedFile]:
    text = raw.strip()
    text = _FENCE_OPEN_RE.sub("", text, count=1)
    text = _FENCE_CLOSE_RE.sub("", text, count=1)
    text = text.strip()

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("response did not contain a JSON object")
        try:
            obj = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"could not parse JSON: {exc}") from exc

    if not isinstance(obj, dict) or "files" not in obj:
        raise ValueError("JSON missing top-level 'files' key")
    raw_files = obj["files"]
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("'files' must be a non-empty list")

    files: list[GeneratedFile] = []
    for entry in raw_files:
        if not isinstance(entry, dict):
            raise ValueError("each file entry must be an object")
        path = entry.get("path")
        contents = entry.get("contents")
        if not isinstance(path, str) or not isinstance(contents, str):
            raise ValueError("each file needs string 'path' and 'contents'")
        files.append(GeneratedFile(path=Path(path), contents=contents))
    return files


def _validate_paths(files: list[GeneratedFile], slug: str) -> None:
    spec_count = 0
    for f in files:
        posix = str(f.path).replace("\\", "/")
        if not posix.startswith(ALLOWED_PREFIXES):
            raise ValueError(f"path {posix!r} outside allowed dirs ({ALLOWED_PREFIXES})")
        if posix.startswith("tests/specs/"):
            if not SPEC_FILE_RE.match(posix):
                raise ValueError(
                    f"spec path {posix!r} must match tests/specs/test_<snake>.py"
                )
            spec_count += 1
        elif posix.startswith("tests/pages/"):
            if not PAGE_FILE_RE.match(posix):
                raise ValueError(
                    f"page path {posix!r} must match tests/pages/<snake>_page.py"
                )
    if spec_count != 1:
        raise ValueError(f"expected exactly 1 spec file, got {spec_count}")


# ----------------------- writing & checking -----------------------


def _write_files(files: list[GeneratedFile], root: Path) -> None:
    for f in files:
        full = (root / f.path).resolve()
        full.parent.mkdir(parents=True, exist_ok=True)
        contents = f.contents if f.contents.endswith("\n") else f.contents + "\n"
        full.write_text(contents, encoding="utf-8")


def _compile_check(files: list[GeneratedFile], root: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for f in files:
        full = root / f.path
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(full)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            errors.append(f"{f.path}:\n{proc.stderr.strip() or proc.stdout.strip()}")
    return (not errors, errors)


def _first_run_check(spec: GeneratedFile, root: Path) -> tuple[bool, str]:
    """Run pytest --collect-only first; if that passes, run the spec once."""
    rel = str(spec.path).replace("\\", "/")
    collect = subprocess.run(
        [sys.executable, "-m", "pytest", rel, "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=60,
    )
    if collect.returncode != 0:
        return (
            False,
            "pytest --collect-only failed:\n"
            + (collect.stdout + "\n" + collect.stderr).strip(),
        )

    run = subprocess.run(
        [sys.executable, "-m", "pytest", rel, "-q", "--maxfail=1", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=180,
    )
    summary = (run.stdout + "\n" + run.stderr).strip()
    return (run.returncode == 0, summary[-3000:])  # cap to last 3KB


# ----------------------- helpers -----------------------


def _slug_from_plan_filename(name: str) -> str:
    """`001-user-login.md` -> `user_login`."""
    stem = Path(name).stem
    stem = re.sub(r"^\d{3}-", "", stem)
    return re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") or "feature"


def _list_existing_pages(root: Path) -> list[str]:
    pages_dir = root / "tests" / "pages"
    if not pages_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in pages_dir.iterdir()
        if p.is_file() and p.suffix == ".py" and p.name != "__init__.py"
    )
