"""
Page Object: saucedemo product inventory page (post-login landing).
"""
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
        # saucedemo encodes the add button id as add-to-cart-<slug>
        slug = item_name.lower().replace(" ", "-")
        self.page.locator(f'[data-test="add-to-cart-{slug}"]').click()
