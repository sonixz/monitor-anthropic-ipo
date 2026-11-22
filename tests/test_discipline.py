"""Discipline mode: the checklist, the rows of trading days, streaks, assiduity, gaps."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from pathlib import Path

import pytest

from ipo_monitor.scan.discipline import (
    Entry,
    Store,
    editable_days,
    from_form,
    gaps_of,
    journal,
    trading_days,
)
from ipo_monitor.scan.portfolio import Book, Ledger, Position, Rules, size

ROOT = Path(__file__).resolve().parents[1]
RULES = Rules.load(ROOT / "data" / "portfolio" / "rules.json")
FULL = {
    "read_orders": True,
    "orders": "placed",
    "stops_set": True,
    "no_unplanned": True,
    "read_analysis": True,
}


def entry(day: str, **fields: object) -> Entry:
    return Entry.model_validate({"date": day, **fields})


def test_what_counts_as_checked() -> None:
    assert entry("2026-11-23", **FULL).checked == 5
    assert entry("2026-11-23", orders="skipped").morning == 0  # skipped without a reason
    assert entry("2026-11-23", orders="skipped", skip_reason="gap up at the open").morning == 1
    assert entry("2026-11-23", no_unplanned=True).evening == 1


def test_trading_days_and_holidays() -> None:
    fri = "2026-11-20"
    assert trading_days(fri, Date(2026, 11, 26), {fri}) == [
        "2026-11-23",
        "2026-11-24",
        "2026-11-25",
        "2026-11-26",
    ]
    # Sessions on the 23rd and 25th: the 24th had none, so it was a holiday.
    sessions = {fri, "2026-11-23", "2026-11-25"}
    assert trading_days(fri, Date(2026, 11, 26), sessions) == [
        "2026-11-23",
        "2026-11-25",
        "2026-11-26",
    ]


def test_statuses_streak_and_assiduity_by_hand() -> None:
    entries = {
        "2026-11-23": entry("2026-11-23", **FULL),
        "2026-11-24": entry("2026-11-24", read_orders=True),
    }
    found = journal(entries, "2026-11-20", Date(2026, 11, 26), {"2026-11-20"})
    statuses = {r.date: r.status for r in found.rows}
    assert statuses == {
        "2026-11-23": "complete",
        "2026-11-24": "partial",
        "2026-11-25": "missed",  # nothing saved, the day is over
        "2026-11-26": "today",
    }
    assert found.rows[0].date == "2026-11-26"  # newest first
    assert (found.streak, found.best) == (0, 1)
    assert found.assiduity_all == pytest.approx(100 / 3)  # one complete of three finished days
    full = {d: entry(d, **FULL) for d in ("2026-11-23", "2026-11-24", "2026-11-25")}
    found = journal(full, "2026-11-20", Date(2026, 11, 26), {"2026-11-20"})
    assert (found.streak, found.best) == (3, 3)  # today, empty, does not break it


def test_only_today_and_the_day_before_can_be_saved() -> None:
    monday = Date(2026, 11, 23)
    assert editable_days(monday) == ("2026-11-23", "2026-11-20")
    now = datetime(2026, 11, 23, 9, 15)
    form = {"date": ["2026-11-19"], "read_orders": ["1"]}
    assert isinstance(from_form(form, monday, now), str)
    saved = from_form({"date": ["2026-11-20"], "read_orders": ["1"], "mood": ["4"]}, monday, now)
    assert isinstance(saved, Entry)
    assert (saved.read_orders, saved.mood, saved.stops_set) == (True, 4, False)


def test_the_store(tmp_path: Path) -> None:
    store = Store(tmp_path / "discipline")
    store.save(entry("2026-11-23", **FULL, note="calm open"))
    assert store.load()["2026-11-23"].note == "calm open"


def test_gaps_from_the_plan() -> None:
    book = Book(RULES, cash=RULES.capital)
    plan = size(4000, 4000, 263.05, 252.69, RULES, "medium")  # 1 share at medium confidence
    book.pending.append(Position("RY", "2026-11-20", plan, 252.69, 278.58))
    ledger = Ledger.model_validate(
        {
            "schema": "antipo.ledger/1",
            "real": True,
            "fills": [
                {"date": "2026-11-23", "symbol": "RY", "side": "buy", "shares": 2, "price": 263.5},
                {"date": "2026-11-23", "symbol": "TD", "side": "buy", "shares": 1, "price": 162.1},
            ],
        }
    )
    orders, gaps = gaps_of("2026-11-23", ledger, book)
    assert orders == ("+2 RY", "+1 TD")
    assert {(g.symbol, g.what) for g in gaps} == {
        ("RY", "above the advised size"),
        ("TD", "outside the plan"),
    }
