"""The visit counter: a number per day, nothing about the visitor."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ipo_monitor import visits
from ipo_monitor.config import Settings
from ipo_monitor.market import RecordedAnswer
from ipo_monitor.visits import Visits
from ipo_monitor.web import create_app

from .conftest import FACTS_DIR, MARKET

NOV_16_NOON = 1794848400  # 17:00 UTC = 12:00 in New York


class Clock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_visits_are_counted_by_new_york_day_and_kept_in_a_file(tmp_path: Path) -> None:
    clock = Clock(NOV_16_NOON)
    path = tmp_path / "visits.json"
    counter = Visits(path, clock)
    assert counter.add()
    assert counter.add()
    clock.now = NOV_16_NOON + 11 * 3600 + 60  # 23:01 in New York, 04:01 UTC the next day
    assert counter.add()
    clock.now += 3600  # 00:01 in New York: a new day
    assert counter.add()
    summary = counter.summary()
    assert (summary["today"], summary["total"], summary["since"]) == (1, 4, "2026-11-16")
    assert summary["days"] == [
        {"day": "2026-11-16", "visits": 3},
        {"day": "2026-11-17", "visits": 1},
    ]
    # The file holds the counts and nothing else; a restart picks them up.
    saved = json.loads(path.read_text("utf-8"))
    assert saved == {
        "since": "2026-11-16",
        "days": {"2026-11-16": 3, "2026-11-17": 1},
        "hours": {"2026-11-16T12": 2, "2026-11-16T23": 1, "2026-11-17T00": 1},
    }
    # The hours make a line: every hour since the first visit, those without one at zero.
    hours = summary["hours"]
    assert isinstance(hours, list)
    assert hours[0] == {"hour": "2026-11-16T00", "visits": 0}
    assert hours[-1] == {"hour": "2026-11-17T00", "visits": 1}
    assert len(hours) == 25
    again = Visits(path, clock)
    assert again.summary()["total"] == 4


def test_a_burst_is_capped_and_a_damaged_file_starts_again(tmp_path: Path) -> None:
    clock = Clock(NOV_16_NOON)
    counter = Visits(None, clock)
    counted = [counter.add() for _ in range(visits.PER_MINUTE + 5)]
    assert counted.count(True) == visits.PER_MINUTE
    clock.now += 60
    assert counter.add()
    broken = tmp_path / "visits.json"
    broken.write_text("{not json", "utf-8")
    assert Visits(broken, clock).summary()["total"] == 0
    broken.write_text(json.dumps({"days": {"2026-11-16": -3}}), "utf-8")
    assert Visits(broken, clock).summary()["total"] == 0


def test_the_service_counts_and_shows_visits(tmp_path: Path) -> None:
    settings = Settings(
        "127.0.0.1", 8000, FACTS_DIR, "test", "info", visits=tmp_path / "visits.json"
    )
    app = create_app(settings, RecordedAnswer(MARKET / "ant-awaiting.json"))
    with TestClient(app) as client:
        assert client.get("/stats").json()["total"] == 0
        response = client.post("/seen", headers={"X-Forwarded-For": "203.0.113.9"})
        assert response.status_code == 204
        assert response.headers["cache-control"] == "no-store"
        stats = client.get("/stats").json()
        assert stats["total"] == 1
        assert stats["kept"] == "a number per day and per hour; no cookie, no address"
        assert client.get("/health").json()["visits"]["total"] == 1
        page = client.get("/").text
    assert '<section class="panel" id="visits"' in page
    assert '<a href="#visits">' in page
    assert "no cookie and no address kept" in page
    # Nothing about the visitor reaches the file.
    assert "203.0.113.9" not in (tmp_path / "visits.json").read_text("utf-8")
    assert client.cookies == {} or not client.cookies


def test_the_file_setting_must_be_in_an_existing_directory(tmp_path: Path) -> None:
    import pytest

    from ipo_monitor.config import ConfigError

    base = {"IPO_FACTS_DIR": str(FACTS_DIR)}
    assert Settings.from_env(base).visits is None
    path = tmp_path / "visits.json"
    assert Settings.from_env({**base, "IPO_VISITS": str(path)}).visits == path
    with pytest.raises(ConfigError, match="IPO_VISITS"):
        Settings.from_env({**base, "IPO_VISITS": str(tmp_path / "missing" / "v.json")})


def test_days_without_visits_are_zeros_and_old_hours_are_dropped(tmp_path: Path) -> None:
    clock = Clock(NOV_16_NOON)
    counter = Visits(tmp_path / "v.json", clock)
    counter.add()
    clock.now += 3 * 86400  # three days later, nobody came in between
    counter.add()
    days = counter.summary()["days"]
    assert days == [
        {"day": "2026-11-16", "visits": 1},
        {"day": "2026-11-17", "visits": 0},
        {"day": "2026-11-18", "visits": 0},
        {"day": "2026-11-19", "visits": 1},
    ]
    for _ in range(60):
        clock.now += 3600
        counter.add()
    assert len(counter.hours) == visits.SHOWN_HOURS
