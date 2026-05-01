"""
Page Object: saucedemo login page.

Gold-standard manual reference. The `write-test` SKILL points at this file.
Generated specs must match this structure.
"""
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
