"""Market data: the share price, from a free and unofficial source.

Nothing here invents a value. A quote is shown only if the source returned a
price for the symbol, in dollars, and names the company as expected. Otherwise
the page says that the stock is awaiting its listing, or that the source is
unavailable. The source sits behind a small interface so it can be replaced.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from ipo_monitor import log
from ipo_monitor.facts import Fact

State = Literal["awaiting", "trading", "closed", "unavailable"]
# The source refuses clients that do not look like a browser. No personal detail goes in here.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
# Seconds between two questions to the source. It is free and limits how often one address may
# ask (it answered "too many requests" after about ten questions in a quarter of an hour).
EVERY = {"awaiting": 300, "trading": 120, "closed": 1800, "unavailable": 300}
LONGEST_WAIT = 1800


class SourceError(Exception):
    """The source could not be reached or did not answer as expected."""


@dataclass(frozen=True)
class Quote:
    """What the source said about the last trade."""

    symbol: str
    name: str
    exchange: str
    price: float
    time: int  # of the last trade, seconds since 1970 (UTC)
    zone: str  # the exchange's time zone as the source names it: "EST"
    offset: int  # of that zone from UTC, in seconds
    day_high: float | None = None
    day_low: float | None = None
    volume: float | None = None
    previous_close: float | None = None
    points: tuple[tuple[int, float], ...] = ()  # (time, price) through the day

    def when(self, moment: int | None = None) -> str:
        """A time in the exchange's zone: 'Nov 19, 2026, 11:32 EST'."""
        zone = timezone(timedelta(seconds=self.offset))
        local = datetime.fromtimestamp(self.time if moment is None else moment, zone)
        return f"{local:%b} {local.day}, {local.year}, {local.hour}:{local:%M} {self.zone}"


@dataclass(frozen=True)
class Snapshot:
    """The state of the market panel after one check."""

    state: State
    source: str
    page: str  # where a reader can see the same quote
    checked: int
    quote: Quote | None = None  # the last good quote; kept while the source fails
    detail: str = ""

    @property
    def shown(self) -> tuple[Any, ...]:
        """What the page displays. The page is rendered again only when this changes."""
        quote = self.quote
        if quote is None:
            return (self.state, self.detail)
        return (
            self.state,
            self.detail,
            quote.price,
            quote.time,
            quote.day_high,
            quote.day_low,
            quote.volume,
            len(quote.points),
        )


class Source(Protocol):
    """Anything that can answer for a symbol with the JSON of a chart request."""

    name: str

    def page(self, symbol: str) -> str: ...

    def fetch(self, symbol: str) -> dict[str, Any]: ...


# -- sources -------------------------------------------------------------------


class YahooChart:
    """Yahoo Finance chart data, the feed behind yfinance. Free, unofficial, delayed."""

    name = "Yahoo Finance"
    hosts = ("query2.finance.yahoo.com", "query1.finance.yahoo.com")

    def page(self, symbol: str) -> str:
        return f"https://finance.yahoo.com/quote/{symbol}/"

    def fetch(self, symbol: str) -> dict[str, Any]:
        problem = "no answer"
        for host in self.hosts:
            url = f"https://{host}/v8/finance/chart/{symbol}?range=1d&interval=5m&includePrePost=false"
            request = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
            )
            try:
                with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                    payload = json.loads(response.read(2_000_000))
            except urllib.error.HTTPError as error:
                if error.code == 404:  # the source's way of saying: unknown symbol
                    return {"chart": {"result": None, "error": {"code": "Not Found"}}}
                problem = f"HTTP {error.code}"
            except (OSError, ValueError) as error:
                problem = type(error).__name__
            else:
                if isinstance(payload, dict):
                    return payload
                problem = "unexpected answer"
        raise SourceError(problem)


class RecordedAnswer:
    """A saved answer, for tests. It names itself so it can never pass for a real quote."""

    name = "TEST DATA, not a real quote"

    def __init__(self, path: Path) -> None:
        self.path = path

    def page(self, symbol: str) -> str:
        return f"https://finance.yahoo.com/quote/{symbol}/"

    def fetch(self, symbol: str) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError) as error:
            raise SourceError(type(error).__name__) from error
        if not isinstance(payload, dict):
            raise SourceError("unexpected answer")
        return payload


def source_from(setting: str) -> Source | None:
    """`off`, `yahoo`, or `file:<path>` for a recorded answer."""
    if setting == "off":
        return None
    if setting == "yahoo":
        return YahooChart()
    if setting.startswith("file:"):
        return RecordedAnswer(Path(setting[5:]))
    raise ValueError(f"unknown market source: {setting}")


# -- reading an answer -----------------------------------------------------------


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def read(
    payload: dict[str, Any], *, symbol: str, company: str, source: Source, now: int
) -> Snapshot:
    """Turn the source's answer into a snapshot. Raises SourceError when it cannot be trusted."""

    def snapshot(state: State, quote: Quote | None = None, detail: str = "") -> Snapshot:
        return Snapshot(state, source.name, source.page(symbol), now, quote, detail)

    chart = payload.get("chart")
    if not isinstance(chart, dict):
        raise SourceError("unexpected answer")
    results = chart.get("result")
    if not results:
        if chart.get("error"):
            return snapshot("awaiting", detail=f"{source.name} does not list {symbol} yet")
        raise SourceError("unexpected answer")
    result = results[0]
    meta = result.get("meta") if isinstance(result, dict) else None
    if not isinstance(meta, dict) or meta.get("symbol") != symbol:
        raise SourceError("answer for another symbol")
    name = str(meta.get("longName") or meta.get("shortName") or "")
    if company.lower() not in name.lower():
        # The symbol belongs to someone else at this source: never show that price.
        raise SourceError(f"{symbol} is not {company} at this source")
    price, traded = _number(meta.get("regularMarketPrice")), _number(meta.get("regularMarketTime"))
    if price is None or traded is None:
        return snapshot(
            "awaiting", detail=f"{source.name} lists {symbol} as {name}, with no trade yet"
        )
    if price <= 0 or meta.get("currency") != "USD":
        raise SourceError("price not in dollars")

    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0] or {}).get("close") or []
    points = tuple(
        (int(moment), close)
        for moment, raw in zip(result.get("timestamp") or [], closes, strict=False)
        if (close := _number(raw)) is not None and _number(moment) is not None
    )
    quote = Quote(
        symbol=symbol,
        name=name,
        exchange=str(meta.get("fullExchangeName") or meta.get("exchangeName") or ""),
        price=price,
        time=int(traded),
        zone=str(meta.get("timezone") or "UTC"),
        offset=int(_number(meta.get("gmtoffset")) or 0),
        day_high=_number(meta.get("regularMarketDayHigh")),
        day_low=_number(meta.get("regularMarketDayLow")),
        volume=_number(meta.get("regularMarketVolume")),
        previous_close=_number(meta.get("previousClose")),
        points=points,
    )
    hours = ((meta.get("currentTradingPeriod") or {}).get("regular")) or {}
    start, end = _number(hours.get("start")), _number(hours.get("end"))
    is_open = start is not None and end is not None and start <= now < end
    return snapshot("trading" if is_open else "closed", quote)


def check(
    source: Source, symbol: str, company: str, previous: Snapshot | None, now: int
) -> Snapshot:
    """Ask the source once. A failure never raises: it becomes the `unavailable` state."""
    last = previous.quote if previous else None
    try:
        snapshot = read(
            source.fetch(symbol), symbol=symbol, company=company, source=source, now=now
        )
    except SourceError as error:
        problem = str(error)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as error:
        problem = f"unexpected answer ({type(error).__name__})"
    else:
        if snapshot.quote is None and last is not None:
            problem = "the source stopped giving a price"  # it traded before: do not go back
        else:
            return snapshot
    return Snapshot("unavailable", source.name, source.page(symbol), now, last, problem)


# -- facts for the page ------------------------------------------------------------


def facts(snapshot: Snapshot) -> list[Fact]:
    """The quote as facts labeled MARKET, each with its source and the time of the quote."""
    quote = snapshot.quote
    if quote is None:
        return []
    when = quote.when()
    read_at = quote.when(snapshot.checked)

    def fact(key: str, title: str, value: float | str, unit: str, shown: str, field: str) -> Fact:
        return Fact.model_validate(
            {
                "id": f"market.{key}",
                "title": title,
                "label": "MARKET",
                "value": value,
                "unit": unit,
                "as_filed": shown,
                "period": when,
                "quote": f"{field} for {quote.symbol} ({quote.name}, {quote.exchange})",
                "context": f"{snapshot.source}: delayed, unofficial",
                "outlet": snapshot.source,
                "url": snapshot.page,
                "accessed": read_at,
            }
        )

    out = [
        fact(
            "price",
            "Last share price",
            quote.price,
            "USD/share",
            f"${quote.price:,.2f}",
            f"regularMarketPrice: {quote.price}",
        ),
        fact(
            "time",
            "Time of the last trade",
            when,
            "text",
            when,
            f"regularMarketTime: {quote.time}",
        ),
    ]
    optional = (
        (
            "day_high",
            "Highest price of the day",
            quote.day_high,
            "USD/share",
            "regularMarketDayHigh",
        ),
        ("day_low", "Lowest price of the day", quote.day_low, "USD/share", "regularMarketDayLow"),
        ("previous_close", "Previous close", quote.previous_close, "USD/share", "previousClose"),
        ("volume", "Shares traded today", quote.volume, "count", "regularMarketVolume"),
    )
    for key, title, value, unit, field in optional:
        if value is not None:
            shown = f"{value:,.0f}" if unit == "count" else f"${value:,.2f}"
            out.append(fact(key, title, value, unit, shown, f"{field}: {value}"))
    return out


# -- keeping it current --------------------------------------------------------------


class Watcher:
    """Checks the source on a timer and tells the page when what it shows has changed."""

    def __init__(
        self,
        source: Source,
        symbol: str,
        company: str,
        on_change: Callable[[Snapshot], None],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.source = source
        self.symbol = symbol
        self.company = company
        self.on_change = on_change
        self.clock = clock
        self.failures = 0
        self.snapshot = self.ask(None)
        self.failures = int(self.snapshot.state == "unavailable")

    @property
    def wait(self) -> int:
        """Seconds until the next question: longer and longer while the source fails."""
        if self.snapshot.state != "unavailable":
            return EVERY[self.snapshot.state]
        doubling = 1 << min(max(0, self.failures - 1), 10)
        return min(LONGEST_WAIT, EVERY["unavailable"] * doubling)

    def ask(self, previous: Snapshot | None) -> Snapshot:
        return check(self.source, self.symbol, self.company, previous, int(self.clock()))

    async def step(self) -> None:
        new = await asyncio.to_thread(self.ask, self.snapshot)
        changed = new.shown != self.snapshot.shown
        self.failures = self.failures + 1 if new.state == "unavailable" else 0
        self.snapshot = new
        if changed:
            log.event("market_changed", state=new.state, detail=new.detail)
            await asyncio.to_thread(self.on_change, new)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.wait)
            try:
                await self.step()
            except Exception as error:  # keep watching whatever happens
                log.event("market_error", level="error", error=type(error).__name__)
