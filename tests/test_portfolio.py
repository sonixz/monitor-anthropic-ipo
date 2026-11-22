"""The guided portfolio: sizing by hand, fills at the next open, stops and targets, metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ipo_monitor.scan.bars import Bar, Series
from ipo_monitor.scan.portfolio import Rules, check_decisions, simulate, size
from ipo_monitor.scan.signals import SignalFile

ROOT = Path(__file__).resolve().parents[1]
RULES = Rules.load(ROOT / "data" / "portfolio" / "rules.json")


def rules(**change: Any) -> Rules:
    return RULES.model_copy(update={"start": "2026-01-01", **change})


def test_the_rules_file() -> None:
    assert (RULES.capital, RULES.max_positions, RULES.slot_fraction) == (4000, 5, 0.2)
    assert (RULES.max_loss_fraction, RULES.leverage, RULES.simulated) == (0.1, False, True)
    assert RULES.version == 2
    assert RULES.slot_by_confidence == {"high": 0.2, "medium": 0.1}


def test_sizing_by_hand() -> None:
    # FTS on Nov 20, medium confidence: close 84.87, stop 82.37. Slot 10% = 400 → 4 shares;
    # loss allowed 400 at 2.50 a share → 160; cash 4,000 → 47. The smallest: 4, $339.48.
    found = size(4000, 4000, 84.87, 82.37, RULES, "medium")
    assert (found.by_slot, found.by_loss, found.by_cash, found.shares) == (4, 160, 47, 4)
    assert found.cost == pytest.approx(339.48)
    assert found.risk == pytest.approx(10.0)
    # At high confidence the slot is 20%: 800 → 9 shares.
    assert size(4000, 4000, 84.87, 82.37, RULES, "high").shares == 9
    # A wide stop: the loss cap binds. Close 100, stop 50: 400 / 50 = 8 < slot's 8? use 40.
    wide = size(4000, 4000, 100, 40, RULES)
    assert (wide.by_slot, wide.by_loss, wide.shares) == (8, 6, 6)
    # Little cash left: the cash binds.
    assert size(4000, 150, 100, 95, RULES).shares == 1


def series(symbol: str, rows: list[tuple[float, float, float, float]]) -> Series:
    bars = tuple(
        Bar(f"2026-01-{i + 1:02d}", o, h, low, c, 1000) for i, (o, h, low, c) in enumerate(rows)
    )
    return Series(symbol, symbol, symbol, "CAD", "TSX", bars, "test", "p", 0)


def signal(symbol: str, level: str = "buy", confidence: str = "medium", day: str = "") -> Any:
    return SignalFile.model_validate(
        {
            "schema": "antipo.signals/1",
            "session": day,
            "written_at": f"{day}T22:00:00Z",
            "written_by": "Claude, session",
            "model": "m",
            "signals": [
                {
                    "symbol": symbol,
                    "level": level,
                    "confidence": confidence,
                    "summary": "s",
                    "reasons": [{"text": "{close}"}],
                }
            ],
        }
    )


def decision(day: str, entries: list[dict[str, str]], positions: Any = ()) -> dict[str, Any]:
    return {
        "schema": "antipo.decisions/1",
        "session": day,
        "written_at": f"{day}T22:30:00Z",
        "written_by": "Claude, session",
        "model": "m",
        "entries": entries,
        "positions": list(positions),
    }


def flat_then(
    rows: list[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    """Twenty quiet sessions (ATR = 2: high − low) then the rows given."""
    return [(100.0, 101.0, 99.0, 100.0)] * 20 + rows


def test_a_buy_fills_at_the_next_open_and_exits_at_the_target() -> None:
    # ATR(14) of the quiet sessions is 2: stop 96, target 106 from the close of 100.
    rows = flat_then([(101.0, 102.0, 100.0, 101.0), (102.0, 107.0, 101.0, 106.5)])
    x = series("X", rows)
    day = x.bars[19].date
    book, refused = simulate(
        rules(),
        {day: signal("X", day=day)},
        {f"{day}.json": decision(day, [{"symbol": "X", "action": "buy", "reason": "r"}])},
        {"X": x},
        {"X": "Tech"},
    )
    assert refused == []
    trade = book.positions[0]
    assert (trade.stop, trade.target) == (96.0, 106.0)
    assert (trade.entered, trade.entry, trade.shares) == (
        x.bars[20].date,
        101.0,
        4,
    )  # slot 400 at the close of 100
    assert (trade.why_exit, trade.exit, trade.exited) == ("target", 106.0, x.bars[21].date)
    assert trade.pnl == pytest.approx((106 - 101) * 4)
    assert trade.r == pytest.approx(5 / 5)  # gain 5 over a risk of 101 − 96
    metrics = book.metrics()
    assert metrics.equity == pytest.approx(4000 + 20)
    assert (metrics.closed, metrics.wins, metrics.win_rate) == (1, 1, 100)


def test_a_gap_below_the_stop_exits_at_the_open() -> None:
    rows = flat_then([(100.0, 101.0, 99.0, 100.0), (94.0, 95.0, 93.0, 94.0)])
    x = series("X", rows)
    day = x.bars[19].date
    book, _ = simulate(
        rules(),
        {day: signal("X", day=day)},
        {f"{day}.json": decision(day, [{"symbol": "X", "action": "buy", "reason": "r"}])},
        {"X": x},
        {},
    )
    trade = book.positions[0]
    assert (trade.why_exit, trade.exit) == ("stop", 94.0)  # opened under the stop of 96
    assert book.metrics().drawdown < 0


def test_decisions_that_break_a_rule_are_refused() -> None:
    allowed: set[str] = {"FTS"}
    held: set[str] = set()
    good = decision("2026-11-20", [{"symbol": "FTS", "action": "buy", "reason": "Strong."}])
    assert check_decisions(good, "2026-11-20.json", allowed=allowed, held=held)[1] == ()
    cases = [
        ([{"symbol": "RY", "action": "buy", "reason": "x"}], "do not allow"),
        ([{"symbol": "FTS", "action": "buy", "reason": "Buy 9 shares."}], "number typed"),
        ([{"symbol": "FTS", "action": "hold", "reason": "x"}], "buy, wait or pass"),
    ]
    for entries, problem in cases:
        _, problems = check_decisions(
            decision("2026-11-20", entries), "2026-11-20.json", allowed=allowed, held=held
        )
        assert any(problem in p for p in problems), problems


def test_slots_and_sectors_limit_the_orders() -> None:
    names = [f"S{i}" for i in range(7)]
    data = {n: series(n, flat_then([(100.0, 101.0, 99.0, 100.0)])) for n in names}
    day = data["S0"].bars[19].date
    file = SignalFile.model_validate(
        {
            **signal("S0", day=day).model_dump(by_alias=True),
            "signals": [
                {
                    "symbol": n,
                    "level": "buy",
                    "confidence": "high",
                    "summary": "s",
                    "reasons": [{"text": "{close}"}],
                }
                for n in names
            ],
        }
    )
    entries = [{"symbol": n, "action": "buy", "reason": "r"} for n in names]
    sectors = {n: ("Energy" if n in ("S0", "S1", "S2") else f"Other{n}") for n in names}
    book, _ = simulate(rules(), {day: file}, {f"{day}.json": decision(day, entries)}, data, sectors)
    bought = [p.symbol for p in book.positions]
    assert len(bought) == 5
    assert "S2" not in bought  # a third in Energy
    assert any("Energy" in why for _, why in book.skipped)


def test_the_real_first_decisions_size_as_shown_to_the_owner() -> None:
    from datetime import UTC, datetime

    from ipo_monitor.scan.bars import RecordedDaily
    from ipo_monitor.scan.board import build
    from ipo_monitor.scan.universe import Candidates

    candidates = Candidates.load(ROOT / "tests" / "fixtures" / "scan" / "candidates-tsx60.json")
    source = RecordedDaily(ROOT / "tests" / "fixtures" / "scan" / "2026-11-20")
    data = {
        c.symbol: source.daily(c.symbol, c.source_symbol, 1795219200)
        for c in candidates.candidates + candidates.pinned + candidates.benchmarks
    }
    signals = {
        "2026-11-20.json": json.loads((ROOT / "tests/fixtures/signals/2026-11-20.json").read_text())
    }
    decisions = {
        "2026-11-20.json": json.loads(
            (ROOT / "tests/fixtures/decisions/2026-11-20.json").read_text()
        )
    }
    board = build(
        candidates, data, signals, datetime(2026, 11, 21, tzinfo=UTC), (), decisions, RULES
    )
    assert board.book is not None
    order = board.book.pending[0]
    assert order.symbol == "RY"
    assert order.sizing.shares == 1  # medium confidence: 400 / 263.05
    assert board.refused_decisions == ()
