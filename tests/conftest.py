"""Shared fixtures."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ipo_monitor.calc import Calc, compute
from ipo_monitor.config import Settings
from ipo_monitor.facts import FactFile, Facts
from ipo_monitor.render import Page, render_page
from ipo_monitor.web import create_app

ROOT = Path(__file__).resolve().parent.parent
FACTS_DIR = ROOT / "data" / "facts"
RAW_FILING = ROOT / "data" / "raw" / "sec" / "Anthropic, PBC - S-1_A-2.html"

Tamper = Callable[[dict[str, float | str]], Facts]


@pytest.fixture(scope="session")
def facts() -> Facts:
    return Facts.load(FACTS_DIR)


@pytest.fixture(scope="session")
def calcs(facts: Facts) -> dict[str, Calc]:
    return compute(facts)


@pytest.fixture(scope="session")
def page(facts: Facts) -> Page:
    return render_page(facts, release="test")


@pytest.fixture(scope="session")
def client() -> TestClient:
    settings = Settings(
        host="127.0.0.1", port=8000, facts_dir=FACTS_DIR, release="test", log_level="info"
    )
    return TestClient(create_app(settings))


def load_raw() -> list[dict[str, Any]]:
    return [json.loads(p.read_text("utf-8")) for p in sorted(FACTS_DIR.glob("*.json"))]


@pytest.fixture
def tampered() -> Tamper:
    """Build a fact set where some values were changed."""

    def build(changes: dict[str, float | str]) -> Facts:
        files = load_raw()
        seen = set()
        for file in files:
            for fact in file["facts"]:
                if fact["id"] in changes:
                    fact["value"] = changes[fact["id"]]
                    seen.add(fact["id"])
        assert seen == set(changes), f"unknown ids: {set(changes) - seen}"
        return Facts([FactFile.model_validate(f) for f in files])

    return build
