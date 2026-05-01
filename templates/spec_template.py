"""
Reference spec for the LLM. Mirrors the saucedemo gold-standard
`tests/specs/test_login_gold.py`. The `write-test` skill must produce
specs that look structurally like this file.

Rules baked in here:
    - one TestClass per feature, one test_tc_<NNN>_... per TC
    - autouse fixture navigates to start URL via base_url
    - all selectors live in Page Objects (imported from tests.pages.*)
    - web-first assertions only (to_have_url, to_be_visible, ...)
    - no time.sleep, no wait_for_timeout
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.pages.login_page import LoginPage


class TestUserLoginTemplate:
    """Template — reference only; real generated specs go to tests/specs/."""

    @pytest.fixture(autouse=True)
    def _goto_login(self, page: Page) -> None:
        page.goto("/")

    def test_tc_001_standard_user_can_log_in_with_valid_credentials(self, page: Page) -> None:
        login = LoginPage(page)

        login.login("standard_user", "secret_sauce")

        expect(page).to_have_url(re.compile(r"/inventory\.html$"))
        expect(page.get_by_text("Products", exact=True)).to_be_visible()

    def test_tc_002_invalid_password_shows_an_inline_error(self, page: Page) -> None:
        login = LoginPage(page)

        login.login("standard_user", "wrong_password")

        expect(login.error_message).to_contain_text("Username and password do not match")
