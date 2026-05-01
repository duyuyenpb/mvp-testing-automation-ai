"""
Pytest configuration shared across all test directories.

The `pytest-playwright` plugin auto-registers `page`, `browser`, and `context`
fixtures. We only override what we need (defaults like base URL).
"""
from __future__ import annotations

import os
from typing import Any

import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("BASE_URL", "https://www.saucedemo.com")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any], base_url: str) -> dict[str, Any]:
    return {**browser_context_args, "base_url": base_url}
