"""
Offline smoke test. Proves the Playwright + pytest-playwright pipeline is wired up.
No network, no demo app — runs in CI without any setup.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.smoke
def test_pipeline_is_alive(page: Page) -> None:
    page.set_content("<h1>QAForge</h1>")
    expect(page.get_by_role("heading", name="QAForge")).to_be_visible()
