"""Fixtures shared by the browser tests: the services under test and the browser."""

from .test_dashboard import (
    base_url,
    browser,
    final_url,
    levels_url,
    private_url,
    session_url,
    trading_url,
)

__all__ = [
    "base_url",
    "browser",
    "final_url",
    "levels_url",
    "private_url",
    "session_url",
    "trading_url",
]
