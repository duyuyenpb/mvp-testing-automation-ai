# Changelog

## v0.1.0-alpha — 2026-05-02

First public alpha. The full **plan → generate → run → heal** loop works end-to-end against [saucedemo.com](https://www.saucedemo.com).

### Commands

- **`qaforge plan "<feature>"`** — Claude turns a plain-English description into a Markdown test plan (TC-001, TC-002, ...) with happy paths, negatives, edge cases, and a UI/API/Hybrid label per case. Interactive y/n/edit approval, or `--auto` to skip the prompt. Reads from `--file requirements.txt` for longer specs.
- **`qaforge generate --plan <file>`** — Claude reads the plan + the `write-test` SKILL + the gold-standard saucedemo examples, then emits one spec at `tests/specs/test_<slug>.py` plus any new page objects under `tests/pages/`. Validates paths (regex), `python -m py_compile`s every file (1 retry on syntax errors), then runs `pytest --collect-only` + the spec once. Strict path validation — Claude can never write outside `tests/`.
- **`qaforge run [paths...]`** — Wraps `pytest --junit-xml`, parses results into a structured `RunResult`. Prints `N passed, M failed in T s` plus per-failure brief, and writes `test-results/qaforge-report.html`. Detects environmental issues (missing Playwright browser, missing `anthropic` package) and emits an actionable hint.
- **`qaforge heal [--auto] [--max-attempts N]`** — Reads the first failure, sends Claude the full spec + every page object the spec imports + the traceback. Claude returns a JSON patch (using the `heal-test` SKILL). Default flow shows a unified diff and asks before applying; `--auto` skips the prompt. Loops until green or attempts exhausted. Returns `{"files": []}` when the failure is a real bug instead of inverting the assertion.
- **`qaforge init <dir>`** — Scaffolds a fresh project: `knowledge.md`, all 3 SKILLs, templates, `conftest.py`, `.env.example`, gold-standard tests, `.github/workflows/test.yml`, `.gitignore`, `README.md`. Skips existing files unless `--force`.

### Foundation

- Single LLM provider: Claude (`claude-sonnet-4-6` by default; configurable via `QAFORGE_MODEL` env var).
- Runtime: Python ≥3.10, Playwright via `pytest-playwright`.
- System prompt = `knowledge.md` + selected SKILLs, wrapped in XML delimiters.
- `assistant_prefill` trick (`'{"files":'`) on every structured-output call → near-guaranteed JSON.
- Path validation rejects anything outside `tests/specs/` and `tests/pages/`. Spec must match `tests/specs/test_<snake>.py`; page must match `tests/pages/<snake>_page.py`.
- Exactly one spec per generation; page objects reused (existing list passed to Claude in user prompt so it imports instead of redefines).

### Tested against

- **saucedemo.com** — login (3 TCs: standard / wrong password / locked-out), inventory page object, gold-standard spec at `tests/specs/test_login_gold.py`.

### Known limitations (v0.2 backlog)

- No multi-LLM (OpenAI / Gemini) — `qaforge/llm.py` is single-provider on purpose.
- No visual regression (`toHaveScreenshot()`).
- No Swagger/OpenAPI import.
- HTML reporting is intentionally simple: one self-contained latest-run report at `test-results/qaforge-report.html`.
- No npm publish — install with `pip install -e '.[test]'` from the repo.
- Generated tests pass-rate against saucedemo: target ≥50% on first run, expect ~70% after 1 heal pass.

### MVP success criteria

| # | Criterion | Status |
|---|---|---|
| 1 | `plan` → ≥3 TCs incl. happy/negative/edge | ✅ |
| 2 | `generate` compile rate ≥70% | ✅ (py_compile + 1 retry) |
| 3 | Generated tests pass against saucedemo ≥50% | ⏳ user-validated on real run |
| 4 | `heal` fixes ≥50% of locator failures | ⏳ user-validated (break 10 locators, run heal) |
| 5 | Full flow plan→generate→run→heal works | ✅ |
| 6 | Stranger follows README → plan in 10 min | ✅ (GETTING-STARTED.md) |
| 7 | Repo has README + LICENSE + GETTING-STARTED + CI | ✅ |

### Install

```bash
git clone https://github.com/duyuyenpb/mvp-testing-automation-ai.git
cd mvp-testing-automation-ai
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[test]'
playwright install chromium
cp .env.example .env  # add ANTHROPIC_API_KEY
```

See [GETTING-STARTED.md](GETTING-STARTED.md) for the full walkthrough.
