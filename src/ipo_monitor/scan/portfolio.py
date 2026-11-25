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
import re
from dataclasses import dataclass, field, replace
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
    slot_by_confidence: dict[str, float] = Field(default_factory=dict)
    max_loss_fraction: float
    leverage: bool
    commission: float
    entry_levels: list[str]
    entry_confidence: list[str]
    max_per_sector: int
    exit_levels: list[str]
    benchmark: str
    history: list[dict[str, object]] = Field(default_factory=list)

    def slot_for(self, confidence: str) -> float:
        """The share of the envelope an entry may take, by the signal's confidence."""
        return self.slot_by_confidence.get(confidence, self.slot_fraction)

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
    fraction: float  # the slot's share of the envelope, by confidence
    slot: float  # equity × fraction
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


def size(
    equity: float, cash: float, close: float, stop: float, rules: Rules, confidence: str = "high"
) -> Sizing:
    fraction = rules.slot_for(confidence)
    slot = equity * fraction
    allowed = equity * rules.max_loss_fraction
    risk = close - stop
    by_slot = math.floor(slot / close) if close > 0 else 0
    by_loss = math.floor(allowed / risk) if risk > 0 else 0
    by_cash = math.floor(max(cash, 0.0) / close) if close > 0 else 0
    shares = max(0, min(by_slot, by_loss, by_cash))
    return Sizing(
        equity, cash, close, stop, fraction, slot, by_slot, allowed, risk, by_loss, by_cash, shares
    )


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
    reached: tuple[str, str] | None = None  # real envelope: (stop, target or time; the session)

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
    real: bool = False  # the owner's own money: positions come from the orders they report

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


def _plan_for(
    symbol: str, day: str, signals: dict[str, SignalFile], series: dict[str, Series]
) -> tuple[float, float, float] | None:
    """Reference close, stop and target of the last buy advice before `day`, for an order the
    owner placed without a pending order of the envelope."""
    one = series.get(symbol)
    if one is None:
        return None
    for session in sorted((s for s in signals if s < day), reverse=True):
        signal = next((x for x in signals[session].signals if x.symbol == symbol), None)
        if signal is None:
            continue
        at = one.upto(session)
        if not at or at[-1].date != session:
            continue
        marks = levels("buy", compute(at, one.currency))
        if "stop" in marks and "target" in marks:
            return marks["entry"].value, marks["stop"].value, marks["target"].value
    return None


def _apply_fill(
    book: Book,
    fill: Fill,
    signals: dict[str, SignalFile],
    series: dict[str, Series],
    advice: dict[str, Position],
) -> None:
    """One order the owner reported, applied to their envelope."""
    rules = book.rules
    held = next((p for p in book.open_positions if p.symbol == fill.symbol), None)
    if fill.side == "sell":
        book.cash += fill.price * fill.shares
        if held is None:
            book.skipped.append((fill.symbol, "a sale of shares not held"))
            return
        if fill.shares >= held.shares:
            held.exited, held.exit = fill.date, fill.price
            held.why_exit = held.reached[0] if held.reached else "sold"
        else:
            held.shares -= fill.shares
        return
    book.cash -= fill.price * fill.shares
    if held is not None:
        total = held.shares + fill.shares
        held.entry = ((held.entry or fill.price) * held.shares + fill.price * fill.shares) / total
        held.shares = total
        return
    order = advice.get(fill.symbol)
    if order is not None:
        stop, target, sizing = order.stop, order.target, order.sizing
        decided = order.decided
    else:
        plan = _plan_for(fill.symbol, fill.date, signals, series)
        close, stop, target = plan if plan else (fill.price, fill.price * 0.9, fill.price * 1.15)
        equity = book.days[-1].equity if book.days else rules.capital
        sizing = size(equity, book.cash + fill.price * fill.shares, close, stop, rules, "medium")
        decided = fill.date
    position = Position(fill.symbol, decided, sizing, stop, target)
    position.entered, position.entry, position.shares = fill.date, fill.price, fill.shares
    book.positions.append(position)


def simulate(
    rules: Rules,
    signals: dict[str, SignalFile],
    decisions: dict[str, object],
    series: dict[str, Series],
    sectors: dict[str, str],
    fills: list[Fill] | None = None,
) -> tuple[Book, list[tuple[str, tuple[str, ...]]]]:
    """Replay the envelope from its start. Returns the book and the refused decision files.

    With `fills` (the owner's ledger), the envelope is the owner's real money: positions open
    and close only with the orders they report, at the prices they got. The decisions become
    advice for the next open; a stop, target or holding period reached is flagged, not filled.
    """
    real = fills is not None
    book = Book(rules, cash=rules.capital, real=real)
    waiting = sorted(fills or [], key=lambda f: f.date)
    refused: list[tuple[str, tuple[str, ...]]] = []
    bench = series.get(rules.benchmark)
    calendar = sorted(
        {b.date for one in series.values() for b in one.bars if b.date >= rules.start}
    )
    bench_shares = 0
    bench_cash = rules.capital
    for day in calendar:
        if real:
            # 1. The owner's orders up to this session; the advice was for this open.
            advice = {p.symbol: p for p in book.pending}
            while waiting and waiting[0].date <= day:
                _apply_fill(book, waiting.pop(0), signals, series, advice)
            book.pending, book.exits = [], []
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
            if real:
                if position.reached is None:
                    if bar.low <= position.stop:
                        position.reached = ("stop", day)
                    elif bar.high >= position.target:
                        position.reached = ("target", day)
                    elif position.sessions >= HOLD:
                        position.reached = ("time", day)
                position.last = bar.close
                continue
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
        if real:  # a target or the holding period reached: the plan is to sell at the next open
            book.exits = [
                (p, p.reached[0])
                for p in book.open_positions
                if p.reached and p.reached[0] in ("target", "time")
            ]
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
            if choice.action == "exit" and position not in [q for q, _ in book.exits]:
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
            sizing = size(equity, cash, close, stop, rules, signal.confidence)
            if sizing.shares <= 0:
                book.skipped.append((choice.symbol, "the size rounds to zero shares"))
                continue
            book.pending.append(Position(choice.symbol, day, sizing, stop, marks["target"].value))
            cash -= sizing.cost
            count += 1
            per_sector[sector] = per_sector.get(sector, 0) + 1
    if real:  # orders reported after the last session read
        advice = {p.symbol: p for p in book.pending}
        for fill in waiting:
            _apply_fill(book, fill, signals, series, advice)
            book.pending = [p for p in book.pending if p.symbol != fill.symbol]
            for bought in book.positions:
                if bought.symbol == fill.symbol and bought.last is None:
                    bought.last = fill.price
    return book, refused


# -- the owner's real orders --------------------------------------------------------


class Fill(BaseModel):
    """One order the owner placed and reported: the price and shares they got."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    symbol: str = Field(min_length=1, max_length=12)
    side: Literal["buy", "sell"]
    shares: int = Field(gt=0)
    price: float = Field(gt=0)
    note: str | None = Field(default=None, max_length=200)


class Ledger(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_: Literal["antipo.ledger/1"] = Field(alias="schema")
    real: bool
    fills: list[Fill] = Field(default_factory=list)


class BrokerLevel(BaseModel):
    """The levels the owner says they entered at the broker for one real position. Typed by
    the owner: shown as theirs, never as a computed or market value, never read by the
    simulation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stop: float | None = Field(default=None, gt=0)  # the stop market order's price
    target: float | None = Field(default=None, gt=0)  # the price alert at the target
    near: float | None = Field(default=None, gt=0)  # the price alert just above the stop
    updated: str = ""


class LevelsFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_: Literal["antipo.levels/1"] = Field(default="antipo.levels/1", alias="schema")
    levels: dict[str, BrokerLevel] = Field(default_factory=dict)


def read_levels(path: Path | None) -> LevelsFile:
    """The owner's levels; none when the file is missing or unreadable."""
    if path is None or not path.is_file():
        return LevelsFile()
    try:
        return LevelsFile.model_validate(json.loads(path.read_text("utf-8")))
    except (OSError, ValueError, ValidationError):
        return LevelsFile()


def write_levels(path: Path, found: LevelsFile) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(found.model_dump_json(by_alias=True, indent=1), "utf-8")
    temporary.replace(path)


@dataclass
class Holding:
    """A real position, from the owner's fills; stop and target from the recommendation,
    unless the owner entered their own at the broker."""

    symbol: str
    shares: int
    cost: float  # average price paid
    last: float | None
    stop: float | None  # the plan's
    target: float | None  # the plan's
    recommended: float | None  # the reference close of the recommendation
    since: str
    mine: BrokerLevel | None = None

    @property
    def pnl(self) -> float | None:
        return None if self.last is None else (self.last - self.cost) * self.shares

    @property
    def slippage(self) -> float | None:
        """Price paid against the recommendation's reference close, in percent."""
        return None if self.recommended is None else (self.cost / self.recommended - 1) * 100

    @property
    def stop_used(self) -> float | None:
        return self.mine.stop if self.mine and self.mine.stop else self.stop

    @property
    def target_used(self) -> float | None:
        return self.mine.target if self.mine and self.mine.target else self.target

    @property
    def near_used(self) -> float | None:
        return self.mine.near if self.mine and self.mine.near else None


def holdings(
    ledger: Ledger,
    book: Book,
    series: dict[str, Series],
    mine: LevelsFile | None = None,
) -> tuple[list[Holding], float]:
    """The owner's open positions and the cash left in the envelope."""
    cash = book.rules.capital
    lots: dict[str, list[Fill]] = {}
    for fill in sorted(ledger.fills, key=lambda f: f.date):
        sign = -1 if fill.side == "buy" else 1
        cash += sign * fill.shares * fill.price - book.rules.commission
        lots.setdefault(fill.symbol, []).append(fill)
    found = []
    advice = {p.symbol: p for p in book.positions + book.pending}
    for symbol, fills in lots.items():
        bought = [f for f in fills if f.side == "buy"]
        shares = sum(f.shares for f in bought) - sum(f.shares for f in fills if f.side == "sell")
        if shares <= 0 or not bought:
            continue
        cost = sum(f.shares * f.price for f in bought) / sum(f.shares for f in bought)
        one = series.get(symbol)
        last = one.bars[-1].close if one and one.bars else None
        rec = advice.get(symbol)
        found.append(
            Holding(
                symbol,
                shares,
                cost,
                last,
                rec.stop if rec else None,
                rec.target if rec else None,
                rec.sizing.close if rec else None,
                bought[0].date,
                mine.levels.get(symbol) if mine else None,
            )
        )
    return found, cash


PRICE = re.compile(r"\d{1,6}(\.\d{1,4})?")
FAR = 0.5  # a level more than half the last close away is taken for a typo


def _price(text: str) -> float | str | None:
    """A price typed by the owner: '208.23', '208,23', '$208.23'. Empty is None."""
    cleaned = text.strip().replace("$", "").replace(" ", "").replace("\u00a0", "")
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", ".")
    if not PRICE.fullmatch(cleaned) or float(cleaned) <= 0:
        return f"{text.strip()[:20]!r} is not a price"
    return float(cleaned)


def levels_from_form(
    form: dict[str, list[str]], held: list[Holding], updated: str
) -> dict[str, BrokerLevel] | str:
    """The levels from the form, one set per real position, or the reason they are refused.
    An empty field means the plan's level applies."""
    found: dict[str, BrokerLevel] = {}
    for h in held:
        values: dict[str, float | None] = {}
        for key, name in (
            ("stop", "stop"),
            ("target", "target alert"),
            ("near", "near-stop alert"),
        ):
            raw = (form.get(f"{key}_{h.symbol}") or [""])[0]
            value = _price(raw)
            if isinstance(value, str):
                return f"{h.symbol} {name}: {value}"
            reference = h.last or h.cost
            if value is not None and abs(value / reference - 1) > FAR:
                far = f"{value:.2f} is too far from the last price, {reference:.2f}"
                return f"{h.symbol} {name}: {far}"
            values[key] = value
        stop = values["stop"] if values["stop"] is not None else h.stop
        target = values["target"] if values["target"] is not None else h.target
        near = values["near"]
        if stop is not None and target is not None and stop >= target:
            return f"{h.symbol}: the stop must be below the target alert"
        if near is not None and stop is not None and near <= stop:
            return f"{h.symbol}: the near-stop alert must be above the stop"
        if near is not None and target is not None and near >= target:
            return f"{h.symbol}: the near-stop alert must be below the target alert"
        if any(v is not None for v in values.values()):
            found[h.symbol] = BrokerLevel(
                stop=values["stop"], target=values["target"], near=near, updated=updated
            )
    return found


@dataclass(frozen=True)
class Held:
    """What is held of one stock, for the scanner and the orders."""

    symbol: str
    real_shares: int = 0
    real_cost: float | None = None
    sim_shares: int = 0
    stop: float | None = None  # in force: the owner's, else the plan's
    target: float | None = None
    yours: bool = False  # the stop or target is the owner's
    since: str = ""  # the session of the first buy
    sessions: int = 0  # sessions held, counting the entry


def held_of(book: Book | None, real: list[Holding]) -> dict[str, Held]:
    found: dict[str, Held] = {}
    for h in real:
        found[h.symbol] = Held(
            h.symbol,
            real_shares=h.shares,
            real_cost=h.cost,
            stop=h.stop_used,
            target=h.target_used,
            yours=bool(h.mine and (h.mine.stop or h.mine.target)),
        )
    if book is not None and book.real:
        for p in book.open_positions:
            one = found.get(p.symbol)
            if one is not None:
                found[p.symbol] = replace(one, since=p.entered or "", sessions=p.sessions)
        return found
    for p in book.open_positions if book else []:
        one = found.get(p.symbol)
        if one is None:
            found[p.symbol] = Held(p.symbol, sim_shares=p.shares, stop=p.stop, target=p.target)
        else:
            found[p.symbol] = Held(
                p.symbol, one.real_shares, one.real_cost, p.shares, one.stop, one.target, one.yours
            )
    return found
