"""
Reference Page Object for the LLM. The `write-test` skill must produce
Page Objects that look structurally like this file.

Pattern:
    - Locators are typed instance attributes, initialised in __init__
    - Actions are methods (no assertions inside)
    - Prefer get_by_role / get_by_label / get_by_placeholder / get_by_test_id
"""
from __future__ import annotations

from playwright.sync_api import Locator, Page


class LoginPage:
    def __init__(self, page: Page) -> None:
        self.page: Page = page
        self.username_input: Locator = page.get_by_placeholder("Username")
        self.password_input: Locator = page.get_by_placeholder("Password")
        self.login_button: Locator = page.get_by_role("button", name="Login")
        self.error_message: Locator = page.locator('[data-test="error"]')

    def goto(self) -> None:
        self.page.goto("/")

    def login(self, username: str, password: str) -> None:
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()
