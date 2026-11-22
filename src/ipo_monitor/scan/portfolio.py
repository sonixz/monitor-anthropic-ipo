"""The guided portfolio: rules, sizing, the AI's decisions, a repeatable simulation, metrics.

A dedicated envelope (`data/portfolio/rules.json`) follows the signals by fixed rules. Each
evening Claude writes a decision file (`data/portfolio/decisions/YYYY-MM-DD.json`): for each
signal the rules allow, buy, wait or pass; for each open position, hold or exit; each with a
reason that types no number. Code does everything with a number in it:

- **Sizing.** Shares = the smallest of: the slot (a fraction of the envelope's value at the
  close) divided by the close; the loss allowed at the stop divided by the risk per share
  (close − stop); the cash divided by the close. Whole shares, no leverage.
- **Fills.** An order decided after a session's close is filled at the next session's open,
  from the same daily bars. A stop or target reached during a later session closes the
  position at that price (or at the open if the session opened beyond it); a session that
  reaches both counts as the stop. After the holding period the position closes at the close.
- **Metrics.** Return against the benchmark bought with the whole envelope on the first day;
  for closed trades: count, win rate, average R (gain ÷ risk taken), worst drawdown.

The same files and bars always give the same portfolio.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date as Date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ipo_monitor.scan.bars import Bar, Series
from ipo_monitor.scan.indicators import compute
from ipo_monitor.scan.levels import HOLD, levels
from ipo_monitor.scan.signals import PLACEHOLDER, SignalFile


class Rules(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_: Literal["antipo.rules/1"] = Field(alias="schema")
    version: int
    approved: str
    approved_by: str
    simulated: bool
    capital: float
    currency: str
    start: str
    max_positions: int
    slot_fraction: float
    max_loss_fraction: float
    leverage: bool
    commission: float
    entry_levels: list[str]
    entry_confidence: list[str]
    max_per_sector: int
    exit_levels: list[str]
    benchmark: str

    @classmethod
    def load(cls, path: Path) -> Rules:
        return cls.model_validate(json.loads(path.read_text("utf-8")))


class Choice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1, max_length=12)
    action: Literal["buy", "wait", "pass", "hold", "exit"]
    reason: str = Field(min_length=1, max_length=320)


class DecisionFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_: Literal["antipo.decisions/1"] = Field(alias="schema")
    session: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    written_at: str
    written_by: Literal["Claude, scheduled run", "Claude, session"]
    model: str = Field(min_length=1, max_length=60)
    note: str | None = Field(default=None, max_length=400)
    entries: list[Choice] = Field(default_factory=list, max_length=60)
    positions: list[Choice] = Field(default_factory=list, max_length=20)


@dataclass(frozen=True)
class Sizing:
    """How the number of shares was found, step by step."""

    equity: float
    cash: float
    close: float
    stop: float
    slot: float  # equity × slot fraction
    by_slot: int
    allowed_loss: float  # equity × max loss fraction
    risk_per_share: float
    by_loss: int
    by_cash: int
    shares: int

    @property
    def cost(self) -> float:
        return self.shares * self.close

    @property
    def risk(self) -> float:
        return self.shares * self.risk_per_share


def size(equity: float, cash: float, close: float, stop: float, rules: Rules) -> Sizing:
    slot = equity * rules.slot_fraction
    allowed = equity * rules.max_loss_fraction
    risk = close - stop
    by_slot = math.floor(slot / close) if close > 0 else 0
    by_loss = math.floor(allowed / risk) if risk > 0 else 0
    by_cash = math.floor(max(cash, 0.0) / close) if close > 0 else 0
    shares = max(0, min(by_slot, by_loss, by_cash))
    return Sizing(equity, cash, close, stop, slot, by_slot, allowed, risk, by_loss, by_cash, shares)


@dataclass
class Position:
    symbol: str
    decided: str  # the session of the decision
    sizing: Sizing
    stop: float
    target: float
    entered: str | None = None  # the session of the fill
    entry: float | None = None
    shares: int = 0
    exited: str | None = None
    exit: float | None = None
    why_exit: str | None = None  # stop, target, time, signal, decision
    sessions: int = 0  # sessions held, counting the entry
    last: float | None = None  # the latest close while open

    @property
    def open(self) -> bool:
        return self.entered is not None and self.exited is None

    @property
    def pnl(self) -> float | None:
        price = self.exit if self.exit is not None else self.last
        if self.entry is None or price is None:
            return None
        return (price - self.entry) * self.shares

    @property
    def r(self) -> float | None:
        price = self.exit if self.exit is not None else self.last
        if self.entry is None or price is None or self.entry <= self.stop:
            return None
        return (price - self.entry) / (self.entry - self.stop)


@dataclass(frozen=True)
class Day:
    date: str
    equity: float
    cash: float
    invested: float
    benchmark: float | None


@dataclass(frozen=True)
class Metrics:
    days: int
    equity: float
    ret: float  # percent
    bench_ret: float | None
    closed: int
    wins: int
    win_rate: float | None
    avg_r: float | None
    avg_pnl: float | None
    drawdown: float  # worst, percent, negative or zero
    exposure: float | None  # average invested share of equity, percent


@dataclass
class Book:
    rules: Rules
    positions: list[Position] = field(default_factory=list)
    pending: list[Position] = field(default_factory=list)  # orders for the next open
    exits: list[tuple[Position, str]] = field(default_factory=list)  # exits at the next open
    days: list[Day] = field(default_factory=list)
    cash: float = 0.0
    last_decision: DecisionFile | None = None
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (symbol, why) not bought

    @property
    def open_positions(self) -> list[Position]:
        return [p for p in self.positions if p.open]

    @property
    def closed_positions(self) -> list[Position]:
        return [p for p in self.positions if p.exited is not None]

    def metrics(self) -> Metrics:
        start = self.rules.capital
        equity = self.days[-1].equity if self.days else start
        bench = self.days[-1].benchmark if self.days else None
        closed = self.closed_positions
        wins = [p for p in closed if (p.pnl or 0) > 0]
        rs = [p.r for p in closed if p.r is not None]
        pnls = [p.pnl for p in closed if p.pnl is not None]
        peak, worst = start, 0.0
        for day in self.days:
            peak = max(peak, day.equity)
            worst = min(worst, (day.equity / peak - 1) * 100)
        exposure = (
            sum(d.invested / d.equity for d in self.days if d.equity > 0) / len(self.days) * 100
            if self.days
            else None
        )
        return Metrics(
            days=len(self.days),
            equity=equity,
            ret=(equity / start - 1) * 100,
            bench_ret=(bench / start - 1) * 100 if bench is not None else None,
            closed=len(closed),
            wins=len(wins),
            win_rate=len(wins) / len(closed) * 100 if closed else None,
            avg_r=sum(rs) / len(rs) if rs else None,
            avg_pnl=sum(pnls) / len(pnls) if pnls else None,
            drawdown=worst,
            exposure=exposure,
        )


def _digits(text: str) -> bool:
    return any(ch.isdigit() for ch in PLACEHOLDER.sub("", text))


def eligible(rules: Rules, signals: SignalFile | None, held: set[str]) -> list[str]:
    """The symbols the rules allow to buy after this session, in the signal file's order."""
    if signals is None:
        return []
    return [
        s.symbol
        for s in signals.signals
        if s.level in rules.entry_levels
        and s.confidence in rules.entry_confidence
        and s.symbol not in held
    ]


def check_decisions(
    raw: object, name: str, *, allowed: set[str], held: set[str]
) -> tuple[DecisionFile | None, tuple[str, ...]]:
    """The rules a decision file must meet. `allowed`: the symbols eligible that session."""
    try:
        file = DecisionFile.model_validate(raw)
    except ValidationError as error:
        return None, tuple(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()[:20]
        )
    problems = []
    if name.removesuffix(".json") != file.session:
        problems.append(f"the file name must be the session date, {file.session}.json")
    try:
        Date.fromisoformat(file.session)
    except ValueError:
        problems.append("session is not a date")
    for index, choice in enumerate(file.entries):
        where = f"entries.{index} ({choice.symbol})"
        if choice.action not in ("buy", "wait", "pass"):
            problems.append(f"{where}: an entry is buy, wait or pass")
        if choice.symbol not in allowed:
            problems.append(f"{where}: the rules do not allow buying it after this session")
        if _digits(choice.reason):
            problems.append(f"{where}: a number typed by hand")
    for index, choice in enumerate(file.positions):
        where = f"positions.{index} ({choice.symbol})"
        if choice.action not in ("hold", "exit"):
            problems.append(f"{where}: a position is hold or exit")
        if choice.symbol not in held:
            problems.append(f"{where}: not an open position")
        if _digits(choice.reason):
            problems.append(f"{where}: a number typed by hand")
    if len({c.symbol for c in file.entries}) != len(file.entries):
        problems.append("a symbol is decided twice")
    return (file if not problems else None), tuple(problems)


def _bar(series: Series | None, day: str) -> Bar | None:
    if series is None:
        return None
    for bar in series.bars:
        if bar.date == day:
            return bar
    return None


def simulate(
    rules: Rules,
    signals: dict[str, SignalFile],
    decisions: dict[str, object],
    series: dict[str, Series],
    sectors: dict[str, str],
) -> tuple[Book, list[tuple[str, tuple[str, ...]]]]:
    """Replay the envelope from its start. Returns the book and the refused decision files."""
    book = Book(rules, cash=rules.capital)
    refused: list[tuple[str, tuple[str, ...]]] = []
    bench = series.get(rules.benchmark)
    calendar = sorted(
        {b.date for one in series.values() for b in one.bars if b.date >= rules.start}
    )
    bench_shares = 0
    bench_cash = rules.capital
    for day in calendar:
        # 1. Orders decided after the previous session fill at this open.
        for position, reason in book.exits:
            bar = _bar(series.get(position.symbol), day)
            if bar is not None and position.open:
                position.exited, position.exit, position.why_exit = day, bar.open, reason
                book.cash += bar.open * position.shares - rules.commission
        book.exits = []
        for order in book.pending:
            bar = _bar(series.get(order.symbol), day)
            if bar is None:
                book.skipped.append((order.symbol, f"no session on {day}"))
                continue
            shares = min(order.sizing.shares, math.floor(book.cash / bar.open))
            if shares <= 0:
                book.skipped.append((order.symbol, "not enough cash at the open"))
                continue
            order.entered, order.entry, order.shares = day, bar.open, shares
            book.cash -= bar.open * shares + rules.commission
            book.positions.append(order)
        book.pending = []
        if bench is not None and bench_shares == 0 and day > rules.start:
            first = _bar(bench, day)
            if first is not None:
                bench_shares = math.floor(rules.capital / first.open)
                bench_cash = rules.capital - bench_shares * first.open
        # 2. Stops, targets and time during this session.
        for position in book.open_positions:
            bar = _bar(series.get(position.symbol), day)
            if bar is None:
                continue
            position.sessions += 1
            price: float | None = None
            why: str | None = None
            if bar.low <= position.stop:
                price, why = min(bar.open, position.stop), "stop"
            elif bar.high >= position.target:
                price, why = max(bar.open, position.target), "target"
            elif position.sessions >= HOLD:
                price, why = bar.close, "time"
            if price is not None and why is not None:
                position.exited, position.exit, position.why_exit = day, price, why
                book.cash += price * position.shares - rules.commission
            position.last = bar.close
        # 3. The value at the close.
        invested = 0.0
        for position in book.open_positions:
            bar = _bar(series.get(position.symbol), day)
            if bar is not None:
                position.last = bar.close
            invested += (position.last or position.entry or 0.0) * position.shares
        bench_bar = _bar(bench, day)
        if day <= rules.start:
            bench_value: float | None = rules.capital  # the fund is bought at the first open after
        else:
            bench_value = bench_cash + bench_shares * bench_bar.close if bench_bar else None
        book.days.append(Day(day, book.cash + invested, book.cash, invested, bench_value))
        # 4. The decisions written after this close: orders for the next open.
        signal_file = signals.get(day)
        held = {p.symbol for p in book.open_positions}
        name = f"{day}.json"
        if name not in decisions:
            continue
        file, problems = check_decisions(
            decisions[name], name, allowed=set(eligible(rules, signal_file, held)), held=held
        )
        if file is None:
            refused.append((name, problems))
            continue
        book.last_decision = file
        by_symbol = {s.symbol: s for s in signal_file.signals} if signal_file else {}
        for choice in file.positions:
            position = next(p for p in book.open_positions if p.symbol == choice.symbol)
            if choice.action == "exit":
                book.exits.append((position, "decision"))
        for position in book.open_positions:
            signal = by_symbol.get(position.symbol)
            leaving = {p.symbol for p, _ in book.exits}
            if signal and signal.level in rules.exit_levels and position.symbol not in leaving:
                book.exits.append((position, "signal"))
        equity = book.days[-1].equity
        cash = book.cash + sum(
            (p.last or 0.0) * p.shares for p, _ in book.exits
        )  # exits free their cash at the same open
        count = len(book.open_positions) - len(book.exits)
        per_sector: dict[str, int] = {}
        for position in book.open_positions:
            sector = sectors.get(position.symbol, "")
            per_sector[sector] = per_sector.get(sector, 0) + 1
        for choice in file.entries:
            if choice.action != "buy":
                continue
            signal = by_symbol[choice.symbol]
            one = series.get(choice.symbol)
            if one is None:
                continue
            at = one.upto(day)
            marks = levels(signal.level, compute(at, one.currency))
            sector = sectors.get(choice.symbol, "")
            if count >= rules.max_positions:
                book.skipped.append((choice.symbol, "no free slot"))
                continue
            if per_sector.get(sector, 0) >= rules.max_per_sector:
                book.skipped.append((choice.symbol, f"already {rules.max_per_sector} in {sector}"))
                continue
            close, stop = marks["entry"].value, marks["stop"].value
            sizing = size(equity, cash, close, stop, rules)
            if sizing.shares <= 0:
                book.skipped.append((choice.symbol, "the size rounds to zero shares"))
                continue
            book.pending.append(Position(choice.symbol, day, sizing, stop, marks["target"].value))
            cash -= sizing.cost
            count += 1
            per_sector[sector] = per_sector.get(sector, 0) + 1
    return book, refused
