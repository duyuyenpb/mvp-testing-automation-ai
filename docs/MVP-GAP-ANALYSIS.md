# MVP Gap Analysis

Compared against `mvp-plan (1).md` from May 2, 2026.

## Summary

The repo is very close to the MVP plan. It implements the core loop:

- `qaforge plan`
- `qaforge generate`
- `qaforge run`
- `qaforge heal`

It also includes the Week 6 `qaforge init` scaffold command, docs, CI, a license, Claude-only LLM integration, and saucedemo-based Playwright + Python examples.

The main difference is language/runtime: the plan's architecture diagram is TypeScript-shaped, but the plan text and current project use Python + pytest-playwright. The repo's `knowledge.md` explicitly locks Python, so this analysis treats Python as the intended implementation.

## MVP Checklist

| Plan item | Repo status | Notes |
|---|---:|---|
| CLI command: `plan` | Done | Supports inline descriptions, `--file`, `--auto`, and approval/edit flow. |
| CLI command: `generate` | Done | Writes one spec plus page objects, validates paths, compiles, retries once, and can first-run pytest. |
| CLI command: `run` | Done | Wraps pytest, parses JUnit XML, and prints pass/fail summaries. |
| CLI command: `heal` | Done | Reads failures, asks Claude for minimal JSON patches, shows diffs, applies, and reruns. |
| Single LLM provider: Claude | Done | `qaforge/llm.py` is Anthropic-only. |
| Playwright + Python | Done | Uses `pytest-playwright` and synchronous Playwright API. |
| One demo e-commerce app | Done | Locked to saucedemo.com in docs and fixtures. |
| `knowledge.md` | Done | Contains project rules, stack, folder structure, boundaries. |
| `skills/test-design/SKILL.md` | Done | Defines exact plan format and quality bar. |
| `skills/write-test/SKILL.md` | Done | Defines JSON output and Playwright/POM conventions. |
| Healer prompt skill | Extra, useful | `skills/heal-test/SKILL.md` was added to support `heal`; this is aligned with Week 5. |
| Templates | Done | `templates/spec_template.py` and `templates/page_template.py`. |
| Generated tests folders | Done | `tests/specs/` and `tests/pages/` exist. |
| Generated plans folder | Fixed | Added `test-plans/.gitkeep` so the documented output folder exists after clone. |
| GitHub Actions template | Done | `.github/workflows/test.yml` exists. |
| README + Getting Started | Done | Both exist; Windows setup notes were added. |
| Basic terminal output | Done | Uses `click` and `rich`; no dashboard. |

## Gaps / Risks To Finish MVP Validation

| Priority | Gap | Recommended next step |
|---|---|---|
| P0 | Local verification blocked in this workspace because `python` / `py` are not installed or not on PATH. | Install Python 3.10+ / 3.11+, then run `.\scripts\setup-local.ps1`. |
| P1 | Success criteria 3 and 4 need measured evidence, not just implementation. | Generate 5 plans, run generated specs, then manually break 10 locators and measure healer fixes. Record results in `CHANGELOG.md`. |
| P1 | The plan says "stranger can follow README"; this has not been verified in a clean Windows setup. | Test the Getting Started flow in a fresh shell after installing Python and Playwright browsers. |
| P2 | `setup_clean.py` is large and not part of the lean MVP architecture. | Keep it only if it is still useful; otherwise remove or document its purpose after confirming no one depends on it. |

## Recommended Development Order

1. Install Python 3.10+ and run `.\scripts\setup-local.ps1`.
2. Run `.\scripts\verify-local.ps1` for no-API-key checks.
3. Add `ANTHROPIC_API_KEY` to `.env`, then run `python -m qaforge plan "User login with email and password" --auto`.
4. Run `python -m qaforge generate --plan test-plans/001-user-login.md --no-run` first to validate generation and compile.
5. Run `.\scripts\verify-local.ps1 -Full` for browser-backed checks.
6. Validate `heal` by breaking a locator in `tests/pages/login_page.py`, running `python -m qaforge heal`, and checking the diff.

## Local Setup Scripts

- `scripts/setup-local.ps1` creates `.venv`, installs QAForge with test dependencies, installs Chromium, creates `.env` if missing, and runs an offline smoke check.
- `scripts/verify-local.ps1` runs Python import, CLI, context, and smoke checks without needing an API key.
- `scripts/verify-local.ps1 -Full` additionally runs the full pytest suite and `qaforge run`.
