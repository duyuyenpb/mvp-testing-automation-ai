"""
`qaforge init` — scaffold a new project from this repo's templates.

Copies: knowledge.md, skills/, templates/, conftest.py, .env.example,
the gold-standard tests/, and a basic .gitignore + README into a target
directory. Skips files that already exist unless --force.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from qaforge.context import PROJECT_ROOT

# Files/directories to copy from this repo's root into the target.
# Each entry is (src_relative_to_PROJECT_ROOT, dst_relative_to_target).
_SCAFFOLD = [
    ("knowledge.md", "knowledge.md"),
    ("skills/test-design/SKILL.md", "skills/test-design/SKILL.md"),
    ("skills/write-test/SKILL.md", "skills/write-test/SKILL.md"),
    ("skills/heal-test/SKILL.md", "skills/heal-test/SKILL.md"),
    ("templates/spec_template.py", "templates/spec_template.py"),
    ("templates/page_template.py", "templates/page_template.py"),
    ("conftest.py", "conftest.py"),
    (".env.example", ".env.example"),
    ("tests/__init__.py", "tests/__init__.py"),
    ("tests/pages/__init__.py", "tests/pages/__init__.py"),
    ("tests/specs/__init__.py", "tests/specs/__init__.py"),
    ("tests/pages/login_page.py", "tests/pages/login_page.py"),
    ("tests/pages/inventory_page.py", "tests/pages/inventory_page.py"),
    ("tests/specs/test_login_gold.py", "tests/specs/test_login_gold.py"),
    ("tests/specs/test_smoke.py", "tests/specs/test_smoke.py"),
    (".github/workflows/test.yml", ".github/workflows/test.yml"),
]

# Empty directories to ensure exist (for outputs).
_EMPTY_DIRS = ["test-plans"]

_GITIGNORE = """\
.venv/
__pycache__/
*.egg-info/
.env
test-results/
playwright-report/
"""

_INIT_README = """\
# {name}

Bootstrapped with [QAForge](https://github.com/duyuyenpb/mvp-testing-automation-ai).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install qaforge[test]   # or: pip install -e <path-to-qaforge> '[test]'
playwright install chromium
cp .env.example .env        # then put your ANTHROPIC_API_KEY in .env
```

## Use

```bash
qaforge plan "User login with email and password"
qaforge generate --plan test-plans/001-user-login.md
qaforge run
qaforge heal
```

`qaforge run` writes an HTML report to `test-results/qaforge-report.html`.

See `knowledge.md` and `skills/` for project rules — edit them to match
your app, then `qaforge plan/generate` will follow your conventions.
"""


@dataclass
class InitResult:
    target: Path
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def init_project(
    target: Path,
    *,
    name: str = "my-test-project",
    force: bool = False,
    source_root: Path = PROJECT_ROOT,
) -> InitResult:
    """Copy scaffold files from `source_root` into `target`."""
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    result = InitResult(target=target)

    for src_rel, dst_rel in _SCAFFOLD:
        src = source_root / src_rel
        dst = target / dst_rel
        if not src.is_file():
            # Source file missing — skip silently, scaffold should still be usable.
            continue
        if dst.exists() and not force:
            result.skipped.append(dst_rel)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        result.written.append(dst_rel)

    for d in _EMPTY_DIRS:
        (target / d).mkdir(parents=True, exist_ok=True)

    gi = target / ".gitignore"
    if not gi.exists() or force:
        gi.write_text(_GITIGNORE, encoding="utf-8")
        result.written.append(".gitignore")
    else:
        result.skipped.append(".gitignore")

    readme = target / "README.md"
    if not readme.exists() or force:
        readme.write_text(_INIT_README.format(name=name), encoding="utf-8")
        result.written.append("README.md")
    else:
        result.skipped.append("README.md")

    return result
