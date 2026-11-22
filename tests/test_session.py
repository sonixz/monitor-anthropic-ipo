"""Prices during the session for open positions (Loop 015): reading, hours, rows, the page."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ipo_monitor.config import ConfigError, Settings
from ipo_monitor.market import SourceError
from ipo_monitor.scan.board import TORONTO
from ipo_monitor.scan.session import (
    MAX_SYMBOLS,
    Recorded,
    SessionWatcher,
    Tick,
    in_session,
    live,
    read_chart,
)
from ipo_monitor.web import create_app

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
REAL = FIX / "session" / "FTS.TO-2026-11-20.json"  # a real answer, after the Nov 20 close
TEST = FIX / "session" / "2026-11-23-TEST"  # invented answers, named as test data
USER, PASSWORD = "owner", "a long test passphrase"


def at(text: str) -> datetime:
    """A moment in Toronto: '2026-11-23 11:20'."""
    return datetime.fromisoformat(text).replace(tzinfo=TORONTO)


def payload() -> dict[str, Any]:
    return dict(json.loads(REAL.read_text("utf-8")))


# -- reading the source -----------------------------------------------------------


def test_a_real_answer_is_read() -> None:
    tick = read_chart(payload(), "FTS.TO")
    assert tick is not None
    assert tick.price == 84.87
    assert tick.time == 1795208400  # Nov 20, 16:00 EST
    assert (tick.high, tick.low) == (85.69, 83.98)
    assert tick.day == "2026-11-20"


def test_a_price_without_shares_traded_is_not_a_price() -> None:
    answer = payload()
    answer["chart"]["result"][0]["meta"]["regularMarketVolume"] = 0
    assert read_chart(answer, "FTS.TO") is None


@pytest.mark.parametrize(
    ("field", "value", "problem"),
    [
        ("symbol", "FTS", "another symbol"),
        ("currency", "USD", "Canadian dollars"),
        ("regularMarketPrice", None, "no price"),
    ],
)
def test_answers_that_are_refused(field: str, value: object, problem: str) -> None:
    answer = payload()
    answer["chart"]["result"][0]["meta"][field] = value
    with pytest.raises(SourceError, match=problem):
        read_chart(answer, "FTS.TO")


# -- hours -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("moment", "open_"),
    [
        ("2026-11-23 09:29", False),
        ("2026-11-23 09:30", True),
        ("2026-11-23 15:59", True),
        ("2026-11-23 16:00", False),
        ("2026-11-21 11:00", False),  # a Saturday
        ("2026-07-06 10:00", True),  # summer time
    ],
)
def test_regular_hours_in_toronto(moment: str, open_: bool) -> None:
    assert in_session(at(moment)) is open_


def test_nothing_is_asked_outside_the_session() -> None:
    asked: list[str] = []

    def fetch(symbol: str) -> dict[str, Any]:
        asked.append(symbol)
        return payload()

    clock = [at("2026-11-23 08:00")]
    watcher = SessionWatcher(fetch, lambda: ["FTS"], lambda: clock[0])
    for moment in ("2026-11-23 08:00", "2026-11-23 16:00", "2026-11-23 22:00", "2026-11-22 12:00"):
        clock[0] = at(moment)
        assert watcher.step() is False
    assert asked == []
    assert watcher.requests == 0


def test_a_round_in_session() -> None:
    asked: list[str] = []

    def fetch(symbol: str) -> dict[str, Any]:
        asked.append(symbol)
        if symbol == "BAD.TO":
            raise SourceError("HTTP 429")
        answer = payload()
        answer["chart"]["result"][0]["meta"]["symbol"] = symbol
        return answer

    many = ["FTS", "FTS", "BAD"] + [f"S{i}" for i in range(20)]
    watcher = SessionWatcher(fetch, lambda: many, lambda: at("2026-11-23 11:20"))
    assert watcher.step() is True
    assert len(asked) == MAX_SYMBOLS
    assert asked[:2] == ["FTS.TO", "BAD.TO"]
    assert watcher.failures == 1
    assert watcher.problem == "HTTP 429"
    assert "FTS" in watcher.ticks
    assert "BAD" not in watcher.ticks
    health = watcher.health()
    assert health["state"] == "watching"
    assert health["failures"] == 1


def test_recorded_answers_name_themselves() -> None:
    recorded = Recorded(TEST)
    assert "TEST" in recorded.name
    tick = read_chart(recorded("RY.TO"), "RY.TO")
    assert tick is not None
    assert tick.day == "2026-11-23"
    with pytest.raises(SourceError):
        recorded("NOPE.TO")


# -- one position's row ------------------------------------------------------------


def tick(price: float, high: float, low: float, moment: str = "2026-11-23 11:15") -> Tick:
    return Tick("FTS.TO", price, int(at(moment).timestamp()), high, low, 1000, "test", "")


def row(t: Tick | None, now: str, *, atr: float | None = 1.2) -> Any:
    return live(
        "FTS", "simulated", tick=t, entry=80.0, stop=76.0, target=86.0, atr=atr,
        last_close=83.5, now=at(now),
    )  # fmt: skip


def test_a_row_matches_arithmetic_by_hand() -> None:
    shown = row(tick(84.87, 85.69, 83.98), "2026-11-23 11:20")
    assert shown.state == "live"
    assert shown.price == 84.87
    # 84.87 / 80 − 1 = 6.0875 %; (84.87 − 80) / (80 − 76) = 1.2175 R
    assert shown.change == pytest.approx(6.0875)
    assert shown.r == pytest.approx(1.2175)
    # 76 / 84.87 − 1 = −10.4513 %; 86 / 84.87 − 1 = +1.3314 %
    assert shown.to_stop == pytest.approx(-10.4513, abs=1e-4)
    assert shown.to_target == pytest.approx(1.3314, abs=1e-4)
    assert shown.flag == ""


def test_flags() -> None:
    assert row(tick(86.2, 86.4, 84.0), "2026-11-23 11:20").flag == "target reached"
    assert row(tick(75.8, 80.0, 75.5), "2026-11-23 11:20").flag == "stop reached"
    # Both in one session: the stop, as the simulation counts it.
    assert row(tick(80.0, 86.5, 75.9), "2026-11-23 11:20").flag == "stop reached"
    # 76.5 − 76 = 0.5, within half an ATR (0.6) of the stop.
    assert row(tick(76.5, 77.0, 76.3), "2026-11-23 11:20").flag == "near stop"
    assert row(tick(76.7, 77.0, 76.3), "2026-11-23 11:20").flag == ""
    assert row(tick(76.5, 77.0, 76.3), "2026-11-23 11:20", atr=None).flag == ""


def test_outside_the_session_the_last_close() -> None:
    shown = row(tick(86.2, 86.4, 84.0), "2026-11-23 17:00")
    assert (shown.state, shown.price, shown.time, shown.flag) == ("closed", 83.5, None, "")


def test_an_earlier_day_is_never_shown_as_today() -> None:
    shown = row(tick(86.2, 86.4, 84.0, "2026-11-20 15:55"), "2026-11-23 11:20")
    assert (shown.state, shown.price, shown.flag) == ("unavailable", 83.5, "")
    assert row(None, "2026-11-23 11:20").state == "unavailable"


def test_an_old_price_in_session_is_named_late() -> None:
    assert row(tick(84.0, 84.5, 83.0, "2026-11-23 10:30"), "2026-11-23 11:20").state == "late"


# -- settings and the page ---------------------------------------------------------


def test_settings() -> None:
    base = {"IPO_SCAN": "off"}
    assert Settings.from_env(base).session == "auto"
    assert Settings.from_env({**base, "IPO_SESSION": "off"}).session == "off"
    with pytest.raises(ConfigError):
        Settings.from_env({**base, "IPO_SESSION": "sometimes"})
    with pytest.raises(ConfigError):
        Settings.from_env({**base, "IPO_NOW": "2026-11-23T11:20"})  # no time zone


def portal(tmp_path: Path, now: str) -> TestClient:
    ledger = {
        "schema": "antipo.ledger/1",
        "real": True,
        "fills": [
            {"date": "2026-11-23", "symbol": "RY", "side": "buy", "shares": 1, "price": 264.1}
        ],
    }
    (tmp_path / "ledger.json").write_text(json.dumps(ledger), "utf-8")
    settings = Settings(
        "127.0.0.1",
        8000,
        ROOT / "data" / "facts",
        "test",
        "info",
        scan=f"file:{FIX / 'scan' / '2026-11-20'}",
        signals=f"dir:{FIX / 'signals'}",
        scan_candidates=FIX / "scan" / "candidates-tsx60.json",
        site_user=USER,
        site_password=PASSWORD,
        data_dir=tmp_path,
        ledger=tmp_path / "ledger.json",
        today="2026-11-23",
        session=f"file:{TEST}",
        now=now,
    )
    app = create_app(settings)
    client = TestClient(app, base_url="https://testserver")
    app.state.scanner.start()
    app.state.scanner.on_change(app.state.scanner.board)
    app.state.session.step()
    client.post(
        "/login",
        content=f"username={USER}&password=a+long+test+passphrase&next=/portfolio",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return client


def test_the_page_in_session(tmp_path: Path) -> None:
    client = portal(tmp_path, "2026-11-23T11:20:00-05:00")
    page = client.get("/portfolio").text
    assert "IN SESSION" in page
    assert "TEST DATA, not a real quote" in page  # the source names itself
    assert "$279.10" in page
    assert "11:15 ET" in page
    assert "▲ target reached" in page  # the session's high passed the target
    session = client.get("/health").json()["session"]
    assert session["state"] == "watching"
    assert session["symbols"] == ["RY"]


def test_the_page_after_the_close(tmp_path: Path) -> None:
    client = portal(tmp_path, "2026-11-23T18:00:00-05:00")
    page = client.get("/portfolio").text
    assert "session closed · last close" in page
    assert "$279.10" not in page
    assert "target reached" not in page
