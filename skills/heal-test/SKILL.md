# SKILL: heal-test

> Loaded by `qaforge heal`. Read `knowledge.md` first; this skill never overrides it.

## Purpose

Take a failing Playwright + Python test, its current code, the failure traceback, and produce a **minimal patch** that makes it pass. Heal **locator drift, timing flakes, and small selector mistakes** — do NOT rewrite tests, change assertions, or alter test intent.

## When you are invoked

Input you will receive (in the user message):
- The failing test's spec file path and full source.
- Any Page Object files the spec imports, with full source.
- Pytest failure output: error message, traceback, the line that threw.
- Optional: a list of locators that exist on the live page (when supplied).

Output you must produce:
- A single JSON object listing only the files that need to change. Same schema as the `write-test` skill:
```json
{ "files": [ { "path": "tests/pages/login_page.py", "contents": "<full new source>" } ] }
```
- The path and class structure must stay identical. Only locators / wait calls / minimal logic change.
- Files that don't need changes must NOT appear in the output.

**No prose, no fences. The first character of your reply must be `{`.**

## What you MAY change

| Allowed | Example |
|---|---|
| Swap a broken locator for a more stable one | `get_by_role("button", name="Login")` → `locator('[data-test="login-button"]')` |
| Replace a failing CSS chain with `get_by_test_id` / `get_by_role` | `.btn.primary > span` → `get_by_role("button", name="Buy")` |
| Add a web-first wait if the page is not ready | `expect(page).to_have_url(...)` before reading the URL |
| Fix a typo in a string locator | `get_by_role("buttn", ...)` → `get_by_role("button", ...)` |
| Add `data-test` selector when role/label has duplicates | use `[data-test="error"]` |

## What you MUST NOT change

| Forbidden | Why |
|---|---|
| Test function names (`test_tc_NNN_*`) | Plan IDs must stay traceable |
| Assertion intent (e.g. `to_have_text("Products")` → `to_have_text("Inventory")`) | That hides real bugs |
| Adding `time.sleep` or `wait_for_timeout` | Forbidden by `knowledge.md` |
| Changing `BASE_URL`, `conftest.py`, `pyproject.toml` | Out of scope |
| Adding new test cases or removing existing ones | Healer ≠ generator |
| `try/except` around assertions to swallow failures | That's cheating |

## Process

1. **Read the traceback first.** Identify exactly which line raised. The failure message tells you what kind of failure (locator strict mode, timeout, assertion mismatch).
2. **Decide if it's healable.** If the assertion is checking the wrong thing — that's a real bug, not a heal target. Return an empty `{"files": []}` (the runner will treat this as "give up").
3. **Choose the smallest fix.** One locator change is better than rewriting the page object. Prefer changing the page object over the spec.
4. **Output FULL file source.** The healer writes files verbatim. A truncated file = broken test. Always emit the entire file, not a diff.

## Locator priority — same as write-test

1. `page.get_by_role("button", name="Login")`
2. `page.get_by_label("Password")`
3. `page.get_by_placeholder("Username")`
4. `page.get_by_test_id("error")`
5. `page.locator('[data-test="error"]')` — saucedemo uses `data-test`, not `data-testid`
6. CSS — last resort, must be stable
7. **Never** XPath. **Never** `nth-child` chains.

## Failure pattern → fix cheatsheet

| Symptom | Likely fix |
|---|---|
| `Locator.click: Timeout 30000ms exceeded` | Locator no longer matches anything; switch strategy (role → data-test) |
| `strict mode violation: ... resolved to 2 elements` | Selector is too broad; narrow with `data-test` or `.first()` is wrong — use unique attr |
| `expect(locator).to_have_text(...)` mismatch | Real text changed: read the actual text from the traceback, update assertion ONLY if it's clearly a UI copy change (e.g. trailing punctuation), not an assertion-inverting change |
| `Page.goto: net::ERR_*` | Not a heal target — environmental |
| `AssertionError: assert page.url == "..."` | Spec is using forbidden `==` instead of `expect(page).to_have_url(...)` — fix the pattern |

## Output format reminder

Single JSON object, no prose. Example for fixing a locator:

```json
{
  "files": [
    {
      "path": "tests/pages/login_page.py",
      "contents": "from __future__ import annotations\n\nfrom playwright.sync_api import Locator, Page\n\n\nclass LoginPage:\n    URL_PATH = \"/\"\n\n    def __init__(self, page: Page) -> None:\n        self.page: Page = page\n        self.username_input: Locator = page.locator('[data-test=\"username\"]')\n        ...\n"
    }
  ]
}
```

If nothing should change (real bug, not a heal target):
```json
{ "files": [] }
```

## Quality bar

- [ ] Output starts with `{`, ends with `}`. No prose.
- [ ] Every file path matches `tests/specs/test_*.py` or `tests/pages/*_page.py`.
- [ ] Every file has its FULL new source — never partial.
- [ ] No `time.sleep`, no `wait_for_timeout`, no XPath, no nth-child.
- [ ] Function names and assertion intent unchanged.
- [ ] If the failure is a real bug (assertion mismatch on substantive text), return `{"files": []}` instead of inverting the assertion.
