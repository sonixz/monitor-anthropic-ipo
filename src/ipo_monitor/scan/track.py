"""The track record: every signal shown, and what the stock did next.

For each signal: the close of its session, then the change after 5 and after 20 sessions,
computed from the same bars. A buy is counted right when the stock rose, a sell when it fell;
neutral is not counted either way. Nothing is left out: losses stay with the wins.
"""

from __future__ import annotations

from dataclasses import dataclass

from ipo_monitor.scan.bars import Series
from ipo_monitor.scan.indicators import pct
from ipo_monitor.scan.signals import LEVELS, STRENGTH, SignalFile

HORIZONS = (5, 20)


@dataclass(frozen=True)
class Outcome:
    session: str
    symbol: str
    level: str
    confidence: str
    close: float | None
    currency: str
    after: dict[int, float | None]  # horizon → change in percent, None until it has passed

    def right(self, horizon: int) -> bool | None:
        change = self.after.get(horizon)
        strength = STRENGTH[self.level]
        if change is None or strength == 0:
            return None
        return change > 0 if strength > 0 else change < 0


@dataclass(frozen=True)
class Summary:
    level: str
    label: str
    count: int
    scored: dict[int, int]
    average: dict[int, float | None]
    right: dict[int, int]


def outcomes(files: list[SignalFile], series: dict[str, Series]) -> list[Outcome]:
    """Every signal of every good file, newest session first."""
    found = []
    for file in sorted(files, key=lambda f: f.session, reverse=True):
        for signal in file.signals:
            one = series.get(signal.symbol)
            close = None
            after: dict[int, float | None] = dict.fromkeys(HORIZONS)
            currency = one.currency if one else ""
            if one is not None:
                dates = [b.date for b in one.bars]
                if file.session in dates:
                    index = dates.index(file.session)
                    close = one.bars[index].close
                    for horizon in HORIZONS:
                        if index + horizon < len(one.bars):
                            after[horizon] = pct(one.bars[index + horizon].close, close)
            found.append(
                Outcome(
                    file.session,
                    signal.symbol,
                    signal.level,
                    signal.confidence,
                    close,
                    currency,
                    after,
                )
            )
    return found


def summarize(found: list[Outcome]) -> list[Summary]:
    out = []
    for level, label in LEVELS.items():
        mine = [o for o in found if o.level == level]
        scored: dict[int, int] = {}
        average: dict[int, float | None] = {}
        right: dict[int, int] = {}
        for horizon in HORIZONS:
            changes = [c for o in mine if (c := o.after.get(horizon)) is not None]
            scored[horizon] = len(changes)
            average[horizon] = sum(changes) / len(changes) if changes else None
            right[horizon] = sum(1 for o in mine if o.right(horizon))
        out.append(Summary(level, label, len(mine), scored, average, right))
    return out
