"""The scanner's state: the list, each stock's indicators, the signals, the track record.

Built from the candidates, the bars read from the market source and the signal files. The
page and the dossier (the JSON the AI reads before it writes) both come from here, so the AI
judges exactly the figures the page shows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ipo_monitor.scan.bars import Series
from ipo_monitor.scan.indicators import Indicator, compute
from ipo_monitor.scan.levels import levels
from ipo_monitor.scan.signals import Checked, Signal, SignalFile, check
from ipo_monitor.scan.track import Outcome, Summary, outcomes, summarize
from ipo_monitor.scan.universe import Candidate, Candidates, Universe, rank, universe, week_ends

TORONTO = ZoneInfo("America/Toronto")
RUN_AT = (16, 45)  # the scheduled run, Toronto time, on weekdays


@dataclass(frozen=True)
class Stock:
    candidate: Candidate
    series: Series | None
    indicators: dict[str, Indicator]
    rank: int | None
    signal: Signal | None
    marks: dict[str, Indicator] = field(default_factory=dict)  # entry, stop, target, risk, reward

    @property
    def symbol(self) -> str:
        return self.candidate.symbol


@dataclass(frozen=True)
class Board:
    candidates: Candidates
    session: str | None  # the latest session with closes
    universe: Universe | None
    stocks: tuple[Stock, ...]  # the list, in rank order, then the pinned stocks
    current: SignalFile | None  # the signals shown: the latest good file
    checked: tuple[Checked, ...]
    outcomes: tuple[Outcome, ...]
    summary: tuple[Summary, ...]
    next_run: datetime
    problems: tuple[str, ...] = field(default=())  # bars that could not be read

    @property
    def stale(self) -> bool:
        """The signals shown are from an earlier session than the latest close."""
        return (
            self.current is not None
            and self.session is not None
            and (self.current.session < self.session)
        )

    @property
    def refused(self) -> tuple[Checked, ...]:
        return tuple(c for c in self.checked if not c.ok)

    def ranked_signals(self) -> list[Stock]:
        """The stocks with a signal, strongest first (buys and sells alike), then by rank."""
        weight = {"high": 3, "medium": 2, "low": 1}
        with_signal = [s for s in self.stocks if s.signal is not None]
        return sorted(
            with_signal,
            key=lambda s: (
                -abs(s.signal.strength) if s.signal else 0,
                -weight[s.signal.confidence] if s.signal else 0,
                s.rank or 99,
            ),
        )


def next_run(now: datetime) -> datetime:
    """The next weekday at the run time, Toronto time. Market holidays are not known here."""
    local = now.astimezone(TORONTO)
    day = local.replace(hour=RUN_AT[0], minute=RUN_AT[1], second=0, microsecond=0)
    if day <= local:
        day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def allowed(candidates: Candidates, series: dict[str, Series], session: str) -> set[str]:
    """The stocks a signal file for `session` may name: the list in force, the one before, and
    the pinned stocks."""
    listed = {k: v for k, v in series.items() if k in {c.symbol for c in candidates.candidates}}
    sessions = sorted({b.date for one in listed.values() for b in one.bars if b.date <= session})
    ends = week_ends(sessions)
    names: set[str] = {c.symbol for c in candidates.pinned}
    for end in ends[-2:]:
        names |= {r.symbol for r in rank(listed, end, candidates.size)}
    return names


def indicators_at(series: dict[str, Series], session: str) -> dict[str, dict[str, Indicator]]:
    out = {}
    for symbol, one in series.items():
        bars = one.upto(session)
        if bars and bars[-1].date == session:
            out[symbol] = compute(bars, one.currency)
    return out


def build(
    candidates: Candidates,
    series: dict[str, Series],
    files: dict[str, object],
    now: datetime,
    problems: tuple[str, ...] = (),
) -> Board:
    """The board from what was read. `files` maps a signal file's name to its parsed JSON."""
    listed = {c.symbol for c in candidates.candidates}
    week = universe({k: v for k, v in series.items() if k in listed}, candidates.size)
    sessions = [one.bars[-1].date for k, one in series.items() if k in listed and one.bars]
    session = max(sessions) if sessions else None

    checked = []
    for name in sorted(files):
        raw = files[name]
        day = name.removesuffix(".json")
        result = check(
            raw,
            name,
            allowed=allowed(candidates, series, day),
            indicators=indicators_at(series, day),
        )
        checked.append(result)
    good = [c.file for c in checked if c.ok and c.file is not None]
    current = max(good, key=lambda f: f.session) if good else None
    by_symbol = {s.symbol: s for s in current.signals} if current else {}

    stocks = []
    everyone = {c.symbol: c for c in candidates.candidates + candidates.pinned}
    order = list(week.symbols if week else ()) + [c.symbol for c in candidates.pinned]
    ranks = {r.symbol: r.rank for r in week.ranked} if week else {}
    for symbol in order:
        one = series.get(symbol)
        found = compute(one.bars, one.currency) if one and one.bars else {}
        signal = by_symbol.get(symbol)
        marks: dict[str, Indicator] = {}
        if signal is not None and one is not None and current is not None:
            at = one.upto(current.session)
            if at and at[-1].date == current.session:
                marks = levels(signal.level, compute(at, one.currency))
        stocks.append(Stock(everyone[symbol], one, found, ranks.get(symbol), signal, marks))

    found_outcomes = outcomes(good, series)
    return Board(
        candidates=candidates,
        session=session,
        universe=week,
        stocks=tuple(stocks),
        current=current,
        checked=tuple(checked),
        outcomes=tuple(found_outcomes),
        summary=tuple(summarize(found_outcomes)),
        next_run=next_run(now),
        problems=problems,
    )


def dossier(board: Board, now: datetime) -> dict[str, Any]:
    """What the AI reads before it writes a signal file: the list and each stock's figures."""
    stocks = []
    for stock in board.stocks:
        one = stock.series
        stocks.append(
            {
                "symbol": stock.symbol,
                "name": stock.candidate.name,
                "exchange": stock.candidate.exchange,
                "currency": stock.candidate.currency,
                "rank": stock.rank,
                "pinned": stock.rank is None,
                "last_session": one.last.date if one and one.last else None,
                "source": {"name": one.source, "page": one.page} if one else None,
                "indicators": {
                    key: {
                        "title": ind.title,
                        "value": round(ind.value, 4),
                        "shown": ind.shown,
                        "formula": ind.formula,
                        "sessions": f"{ind.first} to {ind.last}",
                    }
                    for key, ind in stock.indicators.items()
                },
                "recent_closes": [
                    {"date": b.date, "close": b.close, "volume": b.volume}
                    for b in (one.bars[-10:] if one else ())
                ],
            }
        )
    return {
        "schema": "antipo.dossier/1",
        "made_at": now.astimezone(UTC).isoformat(timespec="seconds"),
        "session": board.session,
        "list": {
            "ranked_on": board.universe.date if board.universe else None,
            "rule": (
                f"top {board.candidates.size} by average value traded a day over 20 sessions, "
                "close at least $5"
            ),
            "candidates": board.candidates.title,
            "entered": list(board.universe.entered) if board.universe else [],
            "left": list(board.universe.left) if board.universe else [],
        },
        "signal_file": {
            "path": f"data/signals/{board.session}.json" if board.session else None,
            "schema": "antipo.signals/1",
            "levels": ["strong_buy", "buy", "neutral", "sell", "strong_sell"],
            "confidence": ["low", "medium", "high"],
            "stops_and_targets": (
                "Code adds to each buy and sell a stop at 2 × ATR(14) and a target at 3 × ATR(14) "
                "from the entry close, followed for up to 20 sessions. A sell means exit or avoid."
            ),
            "rules": [
                "No digit anywhere in summary or reason text: name an indicator as {key}.",
                "Every reason names at least one {indicator} or has a source with url and quote.",
                "One signal per stock, only for the stocks in this dossier.",
            ],
        },
        "stocks": stocks,
    }
