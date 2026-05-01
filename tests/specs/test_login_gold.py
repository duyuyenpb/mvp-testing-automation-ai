"""
Gold-standard manual specs against https://www.saucedemo.com.

Two purposes:
1. Real, runnable tests that verify our locator + POM choices work.
2. Reference code for the `write-test` SKILL — generated specs must look
   structurally identical.

Run:
    pytest tests/specs/test_login_gold.py -m ui
"""
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
