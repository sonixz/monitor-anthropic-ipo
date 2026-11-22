"""The scanner: closes, indicators by hand, the weekly list, signal files and their rules,
the track record, and the page."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ipo_monitor.config import Settings
from ipo_monitor.scan.bars import Bar, RecordedDaily, Series, read_daily
from ipo_monitor.scan.board import build, dossier, next_run
from ipo_monitor.scan.indicators import compute, pct, rsi, sma
from ipo_monitor.scan.render import render_scan
from ipo_monitor.scan.track import outcomes, summarize
from ipo_monitor.scan.universe import Candidates, rank, universe, week_ends
from ipo_monitor.scan.watch import Folder, GitHub, ScanWatcher, expected_session
from ipo_monitor.web import create_app

from .conftest import FACTS_DIR
from .test_web import Audit

ROOT = Path(__file__).resolve().parents[1]
BARS = ROOT / "tests" / "fixtures" / "scan" / "2026-11-20"
SIGNALS = ROOT / "tests" / "fixtures" / "signals"
CANDIDATES_FILE = ROOT / "tests" / "fixtures" / "scan" / "candidates-tsx60.json"
CANDIDATES = Candidates.load(CANDIDATES_FILE)
AFTER_CLOSE = 1795219200  # 2026-11-20 22:20 UTC, a Friday evening in Toronto
NOW = datetime.fromtimestamp(AFTER_CLOSE, UTC)


def series_all() -> dict[str, Series]:
    source = RecordedDaily(BARS)
    return {
        c.symbol: source.daily(c.symbol, c.source_symbol, AFTER_CLOSE)
        for c in CANDIDATES.candidates + CANDIDATES.pinned
    }


SERIES = series_all()


def signal_file() -> dict[str, Any]:
    return json.loads((SIGNALS / "2026-11-20.json").read_text("utf-8"))  # type: ignore[no-any-return]


def bars(closes: list[float], volumes: list[float] | None = None) -> list[Bar]:
    volumes = volumes or [1000.0] * len(closes)
    return [
        Bar(f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", c, c + 1, c - 1, c, v)
        for i, (c, v) in enumerate(zip(closes, volumes, strict=True))
    ]


# -- closes ---------------------------------------------------------------------


def test_daily_bars_read_from_the_recorded_answer() -> None:
    ry = SERIES["RY"]
    assert (ry.name, ry.currency, ry.source_symbol) == ("Royal Bank of Canada", "CAD", "RY.TO")
    assert len(ry.bars) == 252
    assert ry.bars[-1].date == "2026-11-20"
    assert ry.bars[-1].close == pytest.approx(263.05, abs=0.005)
    assert SERIES["CTC.A"].source_symbol == "CTC-A.TO"
    assert SERIES["ANT"].currency == "USD"
    assert len(SERIES["ANT"].bars) == 2


def test_a_session_still_trading_is_not_a_close() -> None:
    payload = json.loads((BARS / "RY.json").read_text("utf-8"))
    period = payload["chart"]["result"][0]["meta"]["currentTradingPeriod"]["regular"]
    last = payload["chart"]["result"][0]["timestamp"][-1]
    period["start"], period["end"] = last, last + 23400
    during = read_daily(payload, symbol="RY", source_symbol="RY.TO", now=last + 3600)
    after = read_daily(payload, symbol="RY", source_symbol="RY.TO", now=last + 23400)
    assert during.bars[-1].date == "2026-11-19"
    assert after.bars[-1].date == "2026-11-20"


# -- indicators, checked by hand ---------------------------------------------------


def test_averages_and_changes_by_hand() -> None:
    assert sma([1, 2, 3, 4], 2) == 3.5
    assert sma([1, 2], 3) is None
    assert pct(110, 100) == pytest.approx(10)
    found = compute(bars([10.0] * 20 + [12.0], [100.0] * 20 + [250.0]), "CAD")
    assert found["close"].value == 12
    assert found["change_1d"].value == pytest.approx(20)  # 12 / 10 - 1
    assert found["sma20"].value == pytest.approx((19 * 10 + 12) / 20)
    assert found["ret20"].value == pytest.approx(20)
    assert found["vol_ratio"].value == pytest.approx(2.5)  # 250 against 100 a day before
    assert found["dollar_vol20"].value == pytest.approx((19 * 10 * 100 + 12 * 250) / 20)
    assert "sma50" not in found
    assert "high52" not in found


def test_rsi_by_hand() -> None:
    # Changes +1, +1, −1 with n = 2: first averages gain 1, loss 0; then
    # gain (1 × 1 + 0) / 2 = 0.5 and loss (0 × 1 + 1) / 2 = 0.5, so RS = 1 and RSI = 50.
    assert rsi([1, 2, 3, 2], 2) == pytest.approx(50)
    assert rsi([1, 2, 3], 2) == 100  # no loss at all
    assert rsi([1, 2], 2) is None


def test_the_year_range_by_hand() -> None:
    closes = [50.0 + (i % 7) for i in range(70)] + [80.0]
    found = compute(bars(closes), "CAD")
    assert found["high52"].value == 81  # the bars' high is the close + 1
    assert found["low52"].value == 49
    assert found["from_high52"].value == pytest.approx((80 / 81 - 1) * 100)
    assert found["high52"].sessions == 71


# -- the weekly list --------------------------------------------------------------


def test_week_ends() -> None:
    days = ["2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17"]
    assert week_ends(days) == ["2026-11-13"]  # Nov 17 is a Tuesday: that week is not over
    assert week_ends([*days, "2026-11-20"]) == ["2026-11-13", "2026-11-20"]  # a Friday


def test_the_list_is_the_most_traded_in_dollars() -> None:
    listed = {k: v for k, v in SERIES.items() if k != "ANT"}
    week = universe(listed, CANDIDATES.size)
    assert week is not None
    assert week.date == "2026-11-20"
    assert week.symbols[:3] == ("RY", "ENB", "TD")
    assert len(week.symbols) == 25
    assert (week.previous_date, week.entered, week.left) == (
        "2026-11-13",
        ("SLF", "PPL"),
        ("FFH", "POW"),
    )
    # By hand for the first: RY's mean of close × volume over its last 20 sessions.
    ry = SERIES["RY"].bars[-20:]
    assert week.ranked[0].dollars == pytest.approx(sum(b.close * b.volume for b in ry) / 20)


def test_a_cheap_stock_is_left_out() -> None:
    listed = {k: v for k, v in SERIES.items() if k != "ANT"}
    cheap = listed["T"]  # about $16: still ranked
    penny = Series(
        "PENNY",
        "PENNY.TO",
        "Penny",
        "CAD",
        "TSX",
        tuple(Bar(b.date, 1, 1, 1, 1, 1e12) for b in cheap.bars),
        "test",
        "p",
        0,
    )
    ranked = rank({**listed, "PENNY": penny}, "2026-11-20", 60)
    assert "PENNY" not in [r.symbol for r in ranked]


# -- signal files -----------------------------------------------------------------


def checked(raw: object, name: str = "2026-11-20.json") -> list[str]:
    board_now = build(CANDIDATES, SERIES, {name: raw}, NOW)
    return list(board_now.checked[0].problems)


def test_the_test_signal_file_meets_every_rule() -> None:
    assert checked(signal_file()) == []


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (lambda f: f["signals"][0].update(summary="Up 5% this week."), "a number typed by hand"),
        (
            lambda f: f["signals"][0]["reasons"].__setitem__(0, {"text": "Trust me."}),
            "cites no indicator and no source",
        ),
        (lambda f: f["signals"][0].update(summary="RSI {rsi99}."), "unknown indicator"),
        (lambda f: f["signals"][0].update(symbol="SAP"), "not in the list"),
        (lambda f: f["signals"][0].update(level="moon"), "level"),
        (lambda f: f["signals"].append(copy.deepcopy(f["signals"][0])), "a second signal"),
        (lambda f: f.update(written_by="someone"), "written_by"),
    ],
)
def test_a_file_that_breaks_a_rule_is_refused(change: Any, problem: str) -> None:
    raw = signal_file()
    change(raw)
    problems = checked(raw)
    assert any(problem in p for p in problems), problems


def test_the_file_name_is_the_session() -> None:
    assert any("file name" in p for p in checked(signal_file(), "latest.json"))


def test_a_refused_file_leaves_the_last_good_signals() -> None:
    bad = signal_file()
    bad["session"] = "2026-11-19"
    bad["signals"][0]["summary"] = "Up 5%."
    files: dict[str, object] = {"2026-11-19.json": bad, "2026-11-20.json": signal_file()}
    board = build(CANDIDATES, SERIES, files, NOW)
    assert board.current is not None
    assert board.current.session == "2026-11-20"
    assert [c.name for c in board.refused] == ["2026-11-19.json"]
    html = render_scan(board).html
    assert "Refused: 2026-11-19.json" in html


def test_signals_from_an_earlier_session_are_named_as_such() -> None:
    old = signal_file()
    old["session"] = "2026-11-19"
    board = build(CANDIDATES, SERIES, {"2026-11-19.json": old}, NOW)
    assert board.stale
    assert "no signals yet for" in render_scan(board).html


# -- the track record --------------------------------------------------------------


def test_the_track_record_by_hand() -> None:
    closes = [100.0, 101, 102, 103, 104, 110, 90]  # session 0, then five later, then six
    series = Series("X", "X.TO", "X", "CAD", "TSX", tuple(bars(closes)), "test", "p", 0)
    raw = {
        "schema": "antipo.signals/1",
        "session": series.bars[0].date,
        "written_at": "2026-01-01T22:00:00Z",
        "written_by": "Claude, session",
        "model": "m",
        "signals": [
            {
                "symbol": "X",
                "level": "buy",
                "confidence": "high",
                "summary": "s",
                "reasons": [{"text": "{close}"}],
            }
        ],
    }
    from ipo_monitor.scan.signals import SignalFile

    found = outcomes([SignalFile.model_validate(raw)], {"X": series})
    assert found[0].close == 100
    assert found[0].after[5] == pytest.approx(10)  # 110 five sessions later
    assert found[0].after[20] is None  # not passed yet
    assert found[0].right(5) is True
    rows = {r.level: r for r in summarize(found)}
    assert (rows["buy"].count, rows["buy"].scored[5], rows["buy"].right[5]) == (1, 1, 1)


# -- the schedule ------------------------------------------------------------------


def test_next_run_and_expected_session() -> None:
    friday_evening = datetime(2026, 11, 20, 22, 30, tzinfo=UTC)  # 17:30 in Toronto
    assert next_run(friday_evening).isoformat().startswith("2026-11-23T16:45")
    monday_morning = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)  # 10:00 in Toronto
    assert next_run(monday_morning).isoformat().startswith("2026-11-23T16:45")
    assert expected_session(monday_morning) == "2026-11-20"
    assert expected_session(datetime(2026, 11, 23, 21, 30, tzinfo=UTC)) == "2026-11-23"


def test_signal_files_are_read_from_github_without_a_token() -> None:
    asked: list[str] = []
    content = json.dumps(signal_file()).encode()

    def get(url: str, accept: str) -> bytes:
        asked.append(url)
        if "api.github.com" in url:
            return json.dumps([{"name": "2026-11-20.json", "sha": "abc", "type": "file"}]).encode()
        return content

    source = GitHub(get=get)
    assert list(source.files()) == ["2026-11-20.json"]
    source.files()
    assert sum("raw.githubusercontent.com" in u for u in asked) == 1  # unchanged: read once


def test_the_watcher_fetches_closes_once_a_session_is_over() -> None:
    clock = [float(AFTER_CLOSE)]
    seen: list[object] = []
    watcher = ScanWatcher(
        CANDIDATES, RecordedDaily(BARS), [Folder(SIGNALS)], seen.append, clock=lambda: clock[0]
    )
    board = watcher.start()
    assert board.session == "2026-11-20"
    assert board.current is not None
    assert not watcher.due()  # Friday's closes are in
    clock[0] += 3 * 86400  # Monday evening: Monday's closes are expected, not in the recording
    assert watcher.due()
    watcher.step()
    assert not watcher.due()  # tried once for Monday: not again before Tuesday


# -- the page ----------------------------------------------------------------------


def test_the_page_names_every_source_and_types_no_number() -> None:
    board = build(CANDIDATES, SERIES, {"2026-11-20.json": signal_file()}, NOW)
    page = render_scan(board)
    parser = Audit()
    parser.feed(page.html)
    assert [t for t in parser.loose_text if any(ch.isdigit() for ch in t)] == []
    assert len(parser.buttons) >= 150
    for button in parser.buttons:
        assert button.get("popovertarget") in parser.popovers
    assert "not investment advice" in page.html
    assert 'href="/ant"' not in page.html  # the IPO page is kept but no longer linked
    assert "Royal Bank reported results on Nov. 20." in page.html  # the quoted source
    assert "https://example.org/test-article" in page.html


def test_the_dossier_gives_the_ai_the_page_s_figures() -> None:
    board = build(CANDIDATES, SERIES, {}, NOW)
    data = dossier(board, NOW)
    assert data["session"] == "2026-11-20"
    assert [s["symbol"] for s in data["stocks"]][:3] == ["RY", "ENB", "TD"]
    assert data["stocks"][-1]["symbol"] == "ANT"
    ry = data["stocks"][0]["indicators"]
    assert ry["close"]["value"] == pytest.approx(263.05, abs=0.005)
    assert "rsi14" in ry


def test_the_service_serves_the_scanner_and_keeps_the_ant_page() -> None:
    settings = Settings(
        "127.0.0.1",
        8000,
        FACTS_DIR,
        "test",
        "info",
        scan=f"file:{BARS}",
        signals=f"dir:{SIGNALS}",
        scan_candidates=CANDIDATES_FILE,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        app.state.scanner.start()
        app.state.scanner.on_change(app.state.scanner.board)
        home = client.get("/")
        assert "ANTIPO" in home.text
        assert "TODAY" in home.text
        assert "ANTHROPIC" in client.get("/ant").text
        health = client.get("/health").json()["scan"]
        assert health["session"] == "2026-11-20"
        assert health["signals_session"] == "2026-11-20"
        assert client.get("/scan/dossier.json").json()["session"] == "2026-11-20"


def test_the_composite_candidate_list() -> None:
    composite = Candidates.load(ROOT / "data" / "scan" / "candidates.json")
    assert composite.size == 50
    assert len(composite.candidates) == 220
    symbols = {c.symbol: c for c in composite.candidates}
    assert symbols["RY"].source_symbol == "RY.TO"
    assert symbols["BBD.B"].source_symbol == "BBD-B.TO"
    assert symbols["AP.UN"].source_symbol == "AP-UN.TO"
    assert all(c.currency == "CAD" and c.sector for c in composite.candidates)


# -- stops and targets -------------------------------------------------------------


def test_atr_by_hand() -> None:
    from ipo_monitor.scan.indicators import atr

    rows = [
        Bar("2026-01-01", 10, 11, 9, 10, 1),
        Bar("2026-01-02", 10, 12, 10, 11, 1),  # true range max(2, |12-10|, |10-10|) = 2
        Bar("2026-01-03", 11, 11, 8, 9, 1),  # max(3, |11-11|, |8-11|) = 3
        Bar("2026-01-04", 9, 13, 9, 12, 1),  # max(4, |13-9|, |9-9|) = 4
    ]
    # n = 2: first average (2 + 3) / 2 = 2.5, then (2.5 × 1 + 4) / 2 = 3.25.
    assert atr(rows, 2) == pytest.approx(3.25)
    assert atr(rows[:2], 2) is None


def test_stop_and_target_by_hand() -> None:
    from ipo_monitor.scan.indicators import Indicator
    from ipo_monitor.scan.levels import levels

    found = {
        "close": Indicator("close", "Close", 100.0, "CAD", "f", 1, "2026-01-02", "2026-01-02"),
        "atr14": Indicator("atr14", "ATR", 2.5, "CAD", "f", 15, "2026-01-01", "2026-01-02"),
    }
    buy = levels("buy", found)
    assert (buy["stop"].value, buy["target"].value) == (95.0, 107.5)  # 100 − 2 × 2.5, + 3 × 2.5
    assert (buy["risk"].value, buy["reward"].value) == (5.0, 7.5)
    sell = levels("strong_sell", found)
    assert (sell["stop"].value, sell["target"].value) == (105.0, 92.5)
    assert levels("neutral", found) == {}


def test_which_came_first_stop_or_target() -> None:
    from ipo_monitor.scan.track import follow

    def day(i: int, low: float, high: float) -> Bar:
        return Bar(f"2026-02-{i:02d}", 100, high, low, 100, 1)

    assert follow([day(1, 99, 101), day(2, 99, 108)], True, 95, 107.5) == ("target", "2026-02-02")
    assert follow([day(1, 94, 101)], True, 95, 107.5) == ("stop", "2026-02-01")
    assert follow([day(1, 94, 109)], True, 95, 107.5) == ("stop", "2026-02-01")  # both: worse
    assert follow([day(1, 99, 101)], True, 95, 107.5) == ("open", None)
    assert follow([day(i, 99, 101) for i in range(1, 4)], True, 95, 107.5, hold=3) == (
        "expired",
        "2026-02-03",
    )
    assert follow([day(1, 92, 101)], False, 105, 92.5) == ("target", "2026-02-01")  # a sell


def test_every_buy_and_sell_on_the_page_has_its_stop_and_target() -> None:
    board = build(CANDIDATES, SERIES, {"2026-11-20.json": signal_file()}, NOW)
    ry = next(s for s in board.stocks if s.symbol == "RY")
    atr14 = ry.indicators["atr14"].value
    assert ry.marks["stop"].value == pytest.approx(ry.indicators["close"].value - 2 * atr14)
    enb = next(s for s in board.stocks if s.symbol == "ENB")
    assert enb.marks == {}  # neutral
    html = render_scan(board).html
    assert "risk per share" in html
    assert "not advice to sell short" in html  # SHOP is a strong sell in the test file
