"""Discipline mode: the owner's daily checklist and the journal of every trading day.

Each trading day the owner checks a morning list (read the orders; placed them, skipped them on
purpose with a reason, or none were planned; a stop entered for each position) and an evening
list (no trade outside the plan; read the evening analysis), with an optional mood and note.
Entries are kept on the server, one file a day. The journal has one row for every trading day
since the simulation started, saved or not: a day that is over with nothing saved is missed, and
only today and yesterday can be saved. Gaps between the plan and the owner's real orders come
from the ledger, by code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ipo_monitor.scan.portfolio import Book, Ledger

ITEMS = 5  # three in the morning, two in the evening
Orders = Literal["placed", "skipped", "none"]


class Entry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    read_orders: bool = False
    orders: Orders | None = None
    skip_reason: str = Field(default="", max_length=200)
    stops_set: bool = False
    no_unplanned: bool = False
    read_analysis: bool = False
    mood: int | None = Field(default=None, ge=1, le=5)
    note: str = Field(default="", max_length=200)
    saved_at: str = ""

    @property
    def morning(self) -> int:
        decided = self.orders in ("placed", "none") or (
            self.orders == "skipped" and bool(self.skip_reason.strip())
        )
        return int(self.read_orders) + int(decided) + int(self.stops_set)

    @property
    def evening(self) -> int:
        return int(self.no_unplanned) + int(self.read_analysis)

    @property
    def checked(self) -> int:
        return self.morning + self.evening


@dataclass(frozen=True)
class Gap:
    symbol: str
    what: str  # "outside the plan", "above the advised size"


@dataclass(frozen=True)
class Row:
    date: str
    entry: Entry | None
    status: str  # complete, partial, missed, today
    orders: tuple[str, ...]  # "+4 FTS", "−2 RY"
    gaps: tuple[Gap, ...]


@dataclass(frozen=True)
class Journal:
    rows: tuple[Row, ...]  # newest first
    streak: int
    best: int
    assiduity_30: float | None  # percent of finished days complete
    assiduity_all: float | None
    gaps: int
    today: str
    editable: tuple[str, ...] = field(default=())
    target: str = ""  # the day the TODAY form fills: today, or the last trading day on a weekend
    target_entry: Entry | None = None


class Store:
    """One JSON file a day in a folder on the server."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def load(self) -> dict[str, Entry]:
        found: dict[str, Entry] = {}
        if not self.folder.is_dir():
            return found
        for path in sorted(self.folder.glob("*.json")):
            try:
                entry = Entry.model_validate(json.loads(path.read_text("utf-8")))
            except (OSError, ValueError, ValidationError):
                continue
            found[entry.date] = entry
        return found

    def save(self, entry: Entry) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self.folder / f"{entry.date}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(entry.model_dump_json(indent=1), "utf-8")
        temporary.replace(target)


def editable_days(today: Date) -> tuple[str, str]:
    """Today and the trading day before it."""
    before = today - timedelta(days=1)
    while before.weekday() >= 5:
        before -= timedelta(days=1)
    return today.isoformat(), before.isoformat()


def trading_days(start: str, today: Date, sessions: set[str]) -> list[str]:
    """Weekdays after `start` up to today. A past weekday with no session, once a later session
    exists, was a market holiday and has no row."""
    last = max(sessions) if sessions else ""
    days = []
    day = Date.fromisoformat(start) + timedelta(days=1)
    while day <= today:
        iso = day.isoformat()
        if day.weekday() < 5 and (iso in sessions or iso > last):
            days.append(iso)
        day += timedelta(days=1)
    return days


def gaps_of(
    day: str, ledger: Ledger | None, book: Book | None
) -> tuple[tuple[str, ...], tuple[Gap, ...]]:
    """The owner's orders that day, and how they differ from the plan decided before it."""
    if ledger is None:
        return (), ()
    fills = [f for f in ledger.fills if f.date == day]
    orders = tuple(f"{'+' if f.side == 'buy' else '−'}{f.shares} {f.symbol}" for f in fills)
    if book is None:
        return orders, ()
    plans = book.positions + book.pending
    sessions = sorted({p.decided for p in plans if p.decided < day})
    decided = sessions[-1] if sessions else None
    advised = {p.symbol: p.sizing.shares for p in plans if p.decided == decided}
    held = {f.symbol for f in ledger.fills if f.side == "buy" and f.date < day}
    found = []
    for fill in fills:
        if fill.side == "buy":
            if fill.symbol not in advised:
                found.append(Gap(fill.symbol, "outside the plan"))
            elif fill.shares > advised[fill.symbol]:
                found.append(Gap(fill.symbol, "above the advised size"))
        elif fill.symbol not in held:
            found.append(Gap(fill.symbol, "a sale of shares not bought here"))
    return orders, tuple(found)


def journal(
    entries: dict[str, Entry],
    start: str,
    today: Date,
    sessions: set[str],
    ledger: Ledger | None = None,
    book: Book | None = None,
) -> Journal:
    days = trading_days(start, today, sessions)
    target = today.isoformat() if today.weekday() < 5 else editable_days(today)[1]
    rows = []
    for day in days:
        entry = entries.get(day)
        if entry is not None and entry.checked == ITEMS:
            status = "complete"
        elif day == today.isoformat():
            status = "today"
        elif entry is not None and entry.checked > 0:
            status = "partial"
        else:
            status = "missed"
        orders, gaps = gaps_of(day, ledger, book)
        rows.append(Row(day, entry, status, orders, gaps))
    finished = [r for r in rows if r.status != "today"]
    streak = 0
    for row in reversed(rows):
        if row.status == "today":
            continue  # today does not break the streak until it is over
        if row.status != "complete":
            break
        streak += 1
    best = run = 0
    for row in rows:
        if row.status == "complete":
            run += 1
            best = max(best, run)
        elif row.status != "today":
            run = 0

    def assiduity(chosen: list[Row]) -> float | None:
        if not chosen:
            return None
        return sum(1 for r in chosen if r.status == "complete") / len(chosen) * 100

    return Journal(
        rows=tuple(reversed(rows)),
        streak=streak,
        best=best,
        assiduity_30=assiduity(finished[-30:]),
        assiduity_all=assiduity(finished),
        gaps=sum(len(r.gaps) for r in rows),
        today=today.isoformat(),
        editable=editable_days(today),
        target=target,
        target_entry=entries.get(target),
    )


def from_form(form: dict[str, list[str]], today: Date, now: datetime) -> Entry | str:
    """The entry the TODAY form posted, or why it is refused."""

    def one(name: str) -> str:
        return (form.get(name) or [""])[0].strip()

    day = one("date") or today.isoformat()
    if day not in editable_days(today) or Date.fromisoformat(day).weekday() >= 5:
        return "Only today and the trading day before can be filled in."
    orders = one("orders") or None
    mood = one("mood")
    try:
        return Entry(
            date=day,
            read_orders=one("read_orders") == "1",
            orders=orders if orders in ("placed", "skipped", "none") else None,  # type: ignore[arg-type]
            skip_reason=one("skip_reason")[:200],
            stops_set=one("stops_set") == "1",
            no_unplanned=one("no_unplanned") == "1",
            read_analysis=one("read_analysis") == "1",
            mood=int(mood) if mood.isdigit() and 1 <= int(mood) <= 5 else None,
            note=one("note")[:200],
            saved_at=now.isoformat(timespec="seconds"),
        )
    except ValidationError:
        return "The checklist could not be read."
