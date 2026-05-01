# SKILL: write-test

> Loaded by `qaforge generate`. Read `knowledge.md` first; this skill never overrides it.

## Purpose

Convert a Markdown test plan into compilable, runnable Playwright + Python code (using `pytest-playwright`) that follows the QAForge project structure. Specs live in `tests/specs/` (filenames `test_<feature>.py`); Page Objects live in `tests/pages/` (filenames `<feature>_page.py`).

The repo already contains gold-standard reference code at `tests/pages/login_page.py`, `tests/pages/inventory_page.py`, and `tests/specs/test_login_gold.py`. **Your output must look structurally identical to those files.** Reuse existing Page Objects when the plan touches the same screens.

## When you are invoked

Input you will receive (in the user message):
- A test plan in QAForge Markdown format (TC-001, TC-002, ...).
- A target slug for the spec filename (e.g. `login`, so the file is `tests/specs/test_login.py`).
- The `BASE_URL` (default https://www.saucedemo.com).
- A list of Page Objects that already exist in `tests/pages/`. **Reuse them; do not redefine.**

Output you must produce:
- **One spec file** at `tests/specs/test_<slug>.py`.
- **Page Object files** at `tests/pages/<page>_page.py`, one per logical screen the spec touches *and* not already in the existing list.
- Nothing outside those paths.

## Process — follow in order

1. **Read the plan.** Identify which screens the test touches. Each new screen → one Page Object.
2. **Reuse existing Page Objects.** If `login_page.py` already exists, import `LoginPage` from `tests.pages.login_page`. Do not re-emit it.
3. **Design new Page Objects.** Each exposes:
   - A constructor taking a `Page`.
   - **Locators as instance attributes** (`get_by_role`, `get_by_label`, `get_by_placeholder`, `get_by_test_id`, or `locator('[data-test="..."]')` for saucedemo).
   - **Actions** as methods (`login(user, pass)`, `add_item_to_cart(name)`).
   - No assertions. Pages do; specs verify.
4. **Write the spec.** One test function per TC. Function name `test_tc_<NNN>_<snake_case_title>`. Group with `class TestFeature:` if 2+ tests.
5. **Use an autouse fixture** to navigate: `page.goto("/")`. The `base_url` from `conftest.py` resolves it to `https://www.saucedemo.com/`.
6. **Web-first assertions only.** Import `expect` from `playwright.sync_api`. Use `expect(loc).to_have_text(...)`, `to_be_visible()`, `to_have_url(...)`, etc.
7. **API setup (Hybrid TCs only).** When a TC is marked `Hybrid` and needs API-side seeding, use `playwright.sync_api.APIRequestContext` inside a fixture. saucedemo has no API, so for that target keep it pure UI.
8. **No sleeps. Ever.**
9. **Self-check `python -m py_compile`** mentally before returning. Imports must resolve from project root (i.e. `from tests.pages.login_page import LoginPage`).

## Output format — required

Return a single JSON object (no prose, no Markdown fences, no leading text) with this shape:

```json
{
  "files": [
    {
      "path": "tests/pages/checkout_page.py",
      "contents": "<full Python source>"
    },
    {
      "path": "tests/specs/test_checkout.py",
      "contents": "<full Python source>"
    }
  ]
}
```

Paths are relative to project root. The generator writes them verbatim. **If you emit anything before the opening `{` or after the closing `}`, the generator will fail to parse and discard your work.**

## Locator priority — pick the FIRST that works

1. `page.get_by_role("button", name="Login")`
2. `page.get_by_label("Password")`
3. `page.get_by_placeholder("Username")`
4. `page.get_by_text("Products", exact=True)` — only for static text labels
5. `page.get_by_test_id("error")` — when the app exposes `data-testid`
6. `page.locator('[data-test="error"]')` — when app exposes `data-test` (saucedemo does)
7. CSS selector — last resort, must be stable
8. **Never** XPath. **Never** `nth-child` chains.

## Reference code — follow these EXACTLY

### `tests/pages/login_page.py` (already in repo — reuse, don't re-emit)

```python
from __future__ import annotations

from playwright.sync_api import Locator, Page


class LoginPage:
    URL_PATH = "/"

    def __init__(self, page: Page) -> None:
        self.page: Page = page
        self.username_input: Locator = page.get_by_placeholder("Username")
        self.password_input: Locator = page.get_by_placeholder("Password")
        self.login_button: Locator = page.get_by_role("button", name="Login")
        self.error_message: Locator = page.locator('[data-test="error"]')

    def goto(self) -> None:
        self.page.goto(self.URL_PATH)

    def login(self, username: str, password: str) -> None:
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()
```

### `tests/pages/inventory_page.py` (already in repo — reuse, don't re-emit)

```python
from __future__ import annotations

from playwright.sync_api import Locator, Page


class InventoryPage:
    URL_PATH = "/inventory.html"

    def __init__(self, page: Page) -> None:
        self.page: Page = page
        self.title: Locator = page.locator('[data-test="title"]')
        self.cart_link: Locator = page.locator('[data-test="shopping-cart-link"]')
        self.cart_badge: Locator = page.locator('[data-test="shopping-cart-badge"]')

    def add_item_to_cart(self, item_name: str) -> None:
        slug = item_name.lower().replace(" ", "-")
        self.page.locator(f'[data-test="add-to-cart-{slug}"]').click()
```

### `tests/specs/test_login_gold.py` (real, passing — pattern your specs after this)

```python
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.pages.inventory_page import InventoryPage
from tests.pages.login_page import LoginPage


@pytest.mark.ui
class TestLoginGold:
    @pytest.fixture(autouse=True)
    def _goto_login(self, page: Page) -> None:
        page.goto("/")

    def test_tc_001_standard_user_logs_in_with_valid_credentials(self, page: Page) -> None:
        login = LoginPage(page)
        inventory = InventoryPage(page)

        login.login("standard_user", "secret_sauce")

        expect(page).to_have_url(re.compile(r"/inventory\.html$"))
        expect(inventory.title).to_have_text("Products")

    def test_tc_002_invalid_password_shows_inline_error(self, page: Page) -> None:
        login = LoginPage(page)

        login.login("standard_user", "wrong_password")

        expect(login.error_message).to_contain_text(
            "Username and password do not match"
        )
        expect(page).to_have_url(re.compile(r"/$"))

    def test_tc_003_locked_out_user_is_rejected(self, page: Page) -> None:
        login = LoginPage(page)

        login.login("locked_out_user", "secret_sauce")

        expect(login.error_message).to_contain_text(
            "Sorry, this user has been locked out"
        )
```

## Common mistakes — NEVER do these

| ❌ Don't | ✅ Do |
|---|---|
| `import time; time.sleep(1)` | `expect(loc).to_be_visible()` |
| `page.wait_for_timeout(1000)` | `expect(loc).to_be_visible()` |
| `page.locator("xpath=//button[@id='login']").click()` | `page.get_by_role("button", name="Login").click()` |
| Selectors directly inside `test_*.py` | Define them on a Page Object, expose actions |
| `assert loc.is_visible()` | `expect(loc).to_be_visible()` (web-first, retries) |
| `assert page.url == "..."` | `expect(page).to_have_url("...")` |
| Sharing state across tests via module globals | Use pytest fixtures or API setup |
| Hard-coding `https://www.saucedemo.com/inventory.html` | Use `page.goto("/")` and rely on `base_url` from conftest |
| Re-emitting `LoginPage` when it already exists in `tests/pages/login_page.py` | Import it: `from tests.pages.login_page import LoginPage` |
| Returning Markdown explanation alongside the JSON | Return JSON only — generator parses it strictly |
| ` ```json ... ``` ` fences around the JSON | Output raw JSON — generator strips fences but errors are noisier |
| Wrapping `contents` strings with `\\n` JS-style instead of real `\n` | Use real newlines inside the JSON string value |
| `print(...)` in committed test code | Remove it. Use Playwright trace viewer instead. |
| Forgetting `from __future__ import annotations` | Always include it as the first import |
| Mixing Python 2-style print statements | Python 3.10+ only, use type hints |

## Quality bar — self-check before returning

- [ ] Output starts with `{` and ends with `}`. No prose, no fences, no preamble.
- [ ] All file paths start with `tests/specs/test_` or `tests/pages/` and end with `.py`.
- [ ] Spec uses `from tests.pages.<name>_page import <Class>`.
- [ ] No `time.sleep`, no `wait_for_timeout`, no `page.url ==`.
- [ ] No XPath. No `nth-child`. No deep CSS chains.
- [ ] Every test function name is `test_tc_<NNN>_<snake_case>`.
- [ ] Every assertion uses `expect(locator).to_X(...)`.
- [ ] `python -m py_compile` would pass: every import resolves, syntax is valid, type hints are well-formed.
