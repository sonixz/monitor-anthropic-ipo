"""The list of stocks scanned: the most traded of a sourced candidate list, ranked each week.

Rank: the average value traded a day over the 20 sessions to the ranking date (close × shares
traded), highest first; a close under $5 leaves a stock out. The ranking date is the last
session of the latest complete week, so the list changes once a week, and the entries and
exits against the week before are named.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ipo_monitor.scan.bars import Series
from ipo_monitor.scan.indicators import compute

SIZE = 50
LOWEST_PRICE = 5.0


class Candidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    name: str
    source_symbol: str
    exchange: str
    currency: str
    sector: str | None = None
    why: str | None = None


class Candidates(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    as_of: str
    source: str
    url: str
    accessed: str
    note: str
    size: int = SIZE  # how many of the candidates the list keeps
    candidates: list[Candidate]
    pinned: list[Candidate] = []

    @classmethod
    def load(cls, path: Path) -> Candidates:
        return cls.model_validate(json.loads(path.read_text("utf-8")))


@dataclass(frozen=True)
class Ranked:
    symbol: str
    rank: int
    dollars: float  # average value traded a day


@dataclass(frozen=True)
class Universe:
    date: str  # the ranking date
    ranked: tuple[Ranked, ...]  # the list, highest first
    previous_date: str | None
    entered: tuple[str, ...]
    left: tuple[str, ...]

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(r.symbol for r in self.ranked)


def _week(day: str) -> tuple[int, int]:
    iso = Date.fromisoformat(day).isocalendar()
    return iso.year, iso.week


def week_ends(sessions: list[str]) -> list[str]:
    """The last session of each complete week, oldest first.

    A week is complete when a later week has a session, or when its last session is a Friday.
    """
    ends = []
    for index, day in enumerate(sessions):
        later = sessions[index + 1] if index + 1 < len(sessions) else None
        if later is not None:
            if _week(later) != _week(day):
                ends.append(day)
        elif Date.fromisoformat(day).weekday() == 4:
            ends.append(day)
    return ends


def rank(series: dict[str, Series], day: str, size: int = SIZE) -> tuple[Ranked, ...]:
    scored = []
    for symbol, one in series.items():
        bars = one.upto(day)
        if not bars or bars[-1].date != day:
            continue  # no close that day: not ranked
        found = compute(bars, one.currency)
        dollars = found.get("dollar_vol20")
        if dollars is None or bars[-1].close < LOWEST_PRICE:
            continue
        scored.append((dollars.value, symbol))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return tuple(Ranked(s, i + 1, d) for i, (d, s) in enumerate(scored[:size]))


def universe(series: dict[str, Series], size: int = SIZE) -> Universe | None:
    """This week's list, from the candidates' bars."""
    sessions = sorted({b.date for one in series.values() for b in one.bars})
    ends = week_ends(sessions)
    if not ends:
        return None
    now = rank(series, ends[-1], size)
    before = rank(series, ends[-2], size) if len(ends) > 1 else ()
    old = {r.symbol for r in before}
    new = {r.symbol for r in now}
    return Universe(
        date=ends[-1],
        ranked=now,
        previous_date=ends[-2] if len(ends) > 1 else None,
        entered=tuple(r.symbol for r in now if r.symbol not in old) if before else (),
        left=tuple(r.symbol for r in before if r.symbol not in new),
    )
