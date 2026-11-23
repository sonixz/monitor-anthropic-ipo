"""A price during the session for the open positions (Loop 015). Display only.

During regular hours (9:30 to 16:00 Toronto, weekdays) the watcher asks the source for a recent
price of each open position's symbol every `EVERY` seconds, and keeps the last good answer in
memory. Nothing is asked outside those hours. A price counts only when shares changed hands and
the answer names the symbol asked, in Canadian dollars.

`live` turns a price into what the portfolio page shows for one position: the price and its
time, the change since entry, how far the stop and the target are, and a flag when the
session's low has reached the stop, its high the target, or the price is within half an ATR of
the stop. The simulation and the track record never read these prices: they use daily closes.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ipo_monitor import log
from ipo_monitor.market import PLAIN_AGENT, SourceError, get_json
from ipo_monitor.scan.board import TORONTO

EVERY = 300  # seconds between two rounds during the session
OPEN = (9, 30)
CLOSE = (16, 0)
MAX_SYMBOLS = 10
LATE = 40 * 60  # seconds: an older price during the session is named as late
NEAR = 0.5  # ATRs from the stop that count as near it
SOURCE = "Yahoo Finance"


def in_session(now: datetime) -> bool:
    """Weekday regular hours in Toronto. Holidays are not known: the source's answer then
    carries an earlier day's time, and no price counts as today's."""
    local = now.astimezone(TORONTO)
    return local.weekday() < 5 and OPEN <= (local.hour, local.minute) < CLOSE


def session_day(now: datetime) -> str:
    return now.astimezone(TORONTO).date().isoformat()


@dataclass(frozen=True)
class Tick:
    """What the source said about one symbol."""

    symbol: str
    price: float
    time: int  # of the last trade, seconds since 1970 (UTC)
    high: float | None
    low: float | None
    volume: float
    source: str
    page: str

    @property
    def day(self) -> str:
        return datetime.fromtimestamp(self.time, UTC).astimezone(TORONTO).date().isoformat()


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def read_chart(payload: object, symbol: str, source: str = SOURCE) -> Tick | None:
    """The last trade in Yahoo's chart answer; None when no shares changed hands."""
    if not isinstance(payload, dict):
        raise SourceError("unexpected answer")
    chart = payload.get("chart")
    results = chart.get("result") if isinstance(chart, dict) else None
    if not results or not isinstance(results, list) or not isinstance(results[0], dict):
        raise SourceError("no result")
    meta = results[0].get("meta")
    if not isinstance(meta, dict) or meta.get("symbol") != symbol:
        raise SourceError("answer for another symbol")
    if meta.get("currency") != "CAD":
        raise SourceError("price not in Canadian dollars")
    price = _number(meta.get("regularMarketPrice"))
    traded = _number(meta.get("regularMarketTime"))
    volume = _number(meta.get("regularMarketVolume"))
    if price is None or traded is None or price <= 0:
        raise SourceError("no price")
    if volume is None or volume <= 0:
        return None  # a placeholder, not a trade
    return Tick(
        symbol=symbol,
        price=price,
        time=int(traded),
        high=_number(meta.get("regularMarketDayHigh")),
        low=_number(meta.get("regularMarketDayLow")),
        volume=volume,
        source=source,
        page=f"https://finance.yahoo.com/quote/{symbol}/",
    )


def yahoo(symbol: str) -> dict[str, Any]:
    """Yahoo Finance's 5-minute chart of the regular session, asked plainly."""
    problem = "no answer"
    for host in ("query2.finance.yahoo.com", "query1.finance.yahoo.com"):
        url = f"https://{host}/v8/finance/chart/{symbol}?range=1d&interval=5m&includePrePost=false"
        try:
            payload = get_json(url, PLAIN_AGENT)
        except SourceError as error:
            problem = str(error)
            continue
        if isinstance(payload, dict):
            return payload
        problem = "unexpected answer"
    raise SourceError(problem)


@dataclass
class Recorded:
    """Saved answers, one `<symbol>.json` a symbol, for tests. Folders of invented answers
    carry TEST in their name, and the source names itself as test data."""

    folder: Path
    name: str = "TEST DATA, not a real quote"

    def __call__(self, symbol: str) -> dict[str, Any]:
        try:
            payload = json.loads((self.folder / f"{symbol}.json").read_text("utf-8"))
        except (OSError, ValueError) as error:
            raise SourceError(type(error).__name__) from error
        if not isinstance(payload, dict):
            raise SourceError("unexpected answer")
        return payload


@dataclass
class SessionWatcher:
    fetch: Callable[[str], dict[str, Any]]
    symbols: Callable[[], list[str]]  # as the page names them: RY, CTC.A
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    source_of: Callable[[str], str] = field(default=lambda symbol: f"{symbol}.TO")
    source: str = SOURCE
    ticks: dict[str, Tick] = field(default_factory=dict)
    checked: datetime | None = None
    requests: int = 0
    failures: int = 0
    problem: str = ""

    def step(self) -> bool:
        """One round, only during the session. Whether anything was asked."""
        now = self.now()
        if not in_session(now):
            return False
        wanted = list(dict.fromkeys(self.symbols()))[:MAX_SYMBOLS]
        for symbol in wanted:
            self.requests += 1
            asked = self.source_of(symbol)
            try:
                tick = read_chart(self.fetch(asked), asked, self.source)
            except SourceError as error:
                self.failures += 1
                self.problem = str(error)
                log.event("session_price_failed", level="warning", symbol=symbol, error=str(error))
                continue
            if tick is not None:
                self.ticks[symbol] = tick  # kept under the page's name
        self.checked = now
        return bool(wanted)

    async def run(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.step)
            except Exception as error:  # keep watching whatever happens
                log.event("session_error", level="error", error=type(error).__name__)
            await asyncio.sleep(EVERY)

    def health(self) -> dict[str, Any]:
        now = self.now()
        return {
            "state": "watching" if in_session(now) else "closed",
            "symbols": sorted(self.ticks),
            "checked": self.checked.isoformat(timespec="seconds") if self.checked else None,
            "requests": self.requests,
            "failures": self.failures,
            "problem": self.problem or None,
        }


@dataclass(frozen=True)
class Live:
    """What the page shows for one open position."""

    symbol: str
    kind: str  # "simulated" or "real"
    state: str  # live, late, closed, unavailable
    price: float | None  # the session's price; outside the session, the last close
    time: int | None  # of that price, when it is the session's
    entry: float | None
    stop: float | None
    target: float | None
    change: float | None  # percent since entry
    r: float | None  # (price − entry) ÷ (entry − stop)
    to_stop: float | None  # percent from the price to the stop
    to_target: float | None  # percent from the price to the target
    flag: str  # "stop reached", "target reached", "near stop" or ""


def live(
    symbol: str,
    kind: str,
    *,
    tick: Tick | None,
    entry: float | None,
    stop: float | None,
    target: float | None,
    atr: float | None,
    last_close: float | None,
    now: datetime,
    near: float | None = None,
) -> Live:
    """One position's row. Outside the session, or without today's price, the last close.
    `near` is the owner's near-stop alert: at or below it counts as near the stop, in place of
    half an ATR."""
    today = tick if tick is not None and tick.day == session_day(now) else None
    if not in_session(now):
        state, price, time = "closed", last_close, None
    elif today is None:
        state, price, time = "unavailable", last_close, None
    else:
        late = now.timestamp() - today.time > LATE
        state, price, time = ("late" if late else "live"), today.price, today.time

    def pct(level: float | None) -> float | None:
        if level is None or price is None or price <= 0:
            return None
        return (level / price - 1) * 100

    change = None if entry is None or price is None else (price / entry - 1) * 100
    r = None
    if entry is not None and price is not None and stop is not None and entry > stop:
        r = (price - entry) / (entry - stop)
    flag = ""
    if state in ("live", "late") and today is not None:
        if stop is not None and today.low is not None and today.low <= stop:
            flag = "stop reached"  # both in one session counts as the stop, as in the simulation
        elif target is not None and today.high is not None and today.high >= target:
            flag = "target reached"
        elif near is not None:
            flag = "near stop" if today.price <= near else ""
        elif stop is not None and atr is not None and today.price - stop <= NEAR * atr:
            flag = "near stop"
    return Live(
        symbol, kind, state, price, time, entry, stop, target, change, r,
        pct(stop), pct(target), flag,
    )  # fmt: skip
