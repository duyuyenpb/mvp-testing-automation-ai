# QAForge Project Knowledge

> Loaded into every LLM prompt. Treat as authoritative project rules.
> If a SKILL contradicts this file, this file wins.

## What QAForge is

An AI-driven test automation CLI. Given a feature description, it produces a Markdown test plan, generates Playwright + Python tests, runs them, and heals failures. MVP target app: https://www.saucedemo.com.

## Tech stack — locked

- **Language:** Python 3.10+. No JavaScript, no TypeScript, no other languages.
- **Test framework:** Playwright via the `pytest-playwright` plugin. No Selenium, no unittest, no Cucumber. Use synchronous Playwright API (`Page`, `Locator`).
- **LLM:** Configurable through `QAFORGE_LLM_PROVIDER`. Supported providers: Anthropic, OpenAI/Codex, Gemini, and OpenAI-compatible APIs.
- **CLI:** `click`.
- **Browser:** Chromium only for MVP.
- **Type hints:** required on every public function. `from __future__ import annotations` at the top of every module.

## Folder structure (you must follow this exactly)

```
qaforge/
├── knowledge.md
├── skills/<skill-name>/SKILL.md
├── templates/*_template.py            ← reference code for the LLM
├── qaforge/                           ← Python package (CLI source)
│   ├── __init__.py
│   ├── cli.py        click entry
│   ├── llm.py        configurable LLM client
│   ├── context.py    loads knowledge + skills
│   ├── planner.py    feature → test plan
│   ├── generator.py  plan → spec + page
│   ├── runner.py     run pytest, capture results
│   └── healer.py     failures → fixes → re-run
├── tests/
│   ├── pages/<feature>_page.py        ← Page Objects
│   └── specs/test_<feature>.py        ← Test specs (pytest discovers test_*.py)
├── test-plans/<NNN>-<slug>.md         ← Generated test plans
├── conftest.py                        ← shared pytest fixtures
└── pyproject.toml
```

When generating files: place specs in `tests/specs/` (filename `test_<feature>.py`), POMs in `tests/pages/` (filename `<feature>_page.py`), plans in `test-plans/` (`NNN-<slug>.md` where NNN is a 3-digit zero-padded counter).

## Coding standards (Python)

- `from __future__ import annotations` at the top of every `.py` file (forward refs work cleanly).
- Type hints on every public function and class field. No untyped `def f(x):`.
- Use **Page Object Model**. A spec must not contain raw selectors directly — it instantiates a Page Object.
- Locators: prefer **role/label/text-based** APIs (`page.get_by_role`, `page.get_by_label`, `page.get_by_placeholder`, `page.get_by_test_id`). CSS selectors only as a last resort. **Never** use XPath.
- **Auto-waiting:** rely on Playwright's built-in waiting. **Never** use `time.sleep()` or `page.wait_for_timeout()`. If you need a wait, use `expect(...).to_be_visible()`, `page.wait_for_url(...)`, `page.wait_for_response(...)`.
- Assertions use `expect()` from `playwright.sync_api` with web-first matchers (`to_have_text`, `to_be_visible`, `to_have_url`).
- Test data and credentials come from environment variables or fixtures — never hard-coded user passwords in committed code, except for known public demo creds (e.g., `standard_user / secret_sauce` on saucedemo).

## Anti-patterns — NEVER do these

| ❌ Don't | ✅ Do instead |
|---|---|
| `time.sleep(2)` or `page.wait_for_timeout(2000)` | `expect(page.get_by_role("button", name="Login")).to_be_visible()` |
| `page.click("div.btn-primary > span:nth-child(2)")` | `page.get_by_role("button", name="Add to cart").click()` |
| `page.locator("xpath=//div[@class='x']")` | `page.get_by_test_id("x")` or `page.get_by_role(...)` |
| Inline selectors inside `test_*.py` | Define them in the matching `*_page.py` |
| Sharing state across tests via module globals | Use pytest fixtures or API setup |
| `print(...)` in committed tests | Remove before commit; use Playwright trace viewer instead |
| Hard-coded sleeps to "fix" flakiness | Fix the locator or use a web-first assertion |
| `assert page.is_visible(...)` (returns bool) | `expect(loc).to_be_visible()` (web-first, retries) |

## Test plan output format (Markdown)

Every generated plan must have these sections, in this order:

```
# Test Plan: <feature name>

## Feature Summary
<1–3 sentences>

## Preconditions
- <bulleted list>

## Test Cases

### TC-001: <happy path name>
- **Type:** UI | API | Hybrid
- **Priority:** P0 | P1 | P2
- **Preconditions:** <if any>
- **Steps:**
  1. <action>
  2. <action>
- **Expected Result:** <observable outcome>

### TC-002: <negative case name>
...

### TC-003: <edge case name>
...

## Out of Scope
- <bulleted list of things explicitly not covered>
```

A plan must include **at least one happy path, one negative case, and one edge case**.

## Generated test file rules

- One spec file per feature, named `test_<feature>.py` (snake_case).
- One Page Object per page/screen, named `<page>_page.py` (snake_case).
- Each test function maps to a TC ID from the plan, e.g., `def test_tc_001_user_can_log_in_with_valid_credentials(page): ...`.
- Group related tests in a `class TestLogin:` if there are 3+ tests for one feature.
- API setup (creating users, seeding data) goes in pytest fixtures using Playwright's `APIRequestContext`, not UI clicks.

## CLI behavior

- All commands read `.env` (via `python-dotenv`) at startup.
- If the selected provider's API key is missing, exit with code 1 and a friendly message telling the user to copy `.env.example` and configure the matching key.
- All commands print structured progress: `[plan]`, `[generate]`, `[run]`, `[heal]` prefixes.
- Long LLM calls show a `… thinking` indicator (use `rich.status` or simple stderr).
- Use `rich` for nicely formatted Markdown output in the terminal.

## Boundaries (out of scope for MVP — refuse if asked)

The LLM should refuse and explain when asked to:
- Generate tests in any language other than Python.
- Use any test framework other than Playwright via `pytest-playwright`.
- Use any locator strategy that violates the rules above.
- Add visual regression, accessibility, performance, or contract tests (these are v2).
- Generate code that runs against any target other than `BASE_URL` from `.env`.
