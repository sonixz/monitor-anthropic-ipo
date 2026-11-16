"""Market data: the share price, from free and unofficial sources.

Nothing here invents a value. A quote is shown only if the source returned a
price for the symbol, in dollars, and names the company as expected. Otherwise
the page says that the stock is awaiting its listing, or that the source is
unavailable. The source sits behind a small interface so it can be replaced.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import re
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


def _when(moment: int, offset: int, zone: str) -> str:
    local = datetime.fromtimestamp(moment, timezone(timedelta(seconds=offset)))
    return f"{local:%b} {local.day}, {local.year}, {local.hour}:{local:%M} {zone}"


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
    # Outside regular hours the last trade is not the close. When the source says which side of
    # the session it is on, the page says it too: "before the open" or "after the close".
    outside: str = ""
    close: float | None = None  # of the last regular session, when the source gives it apart
    close_time: int | None = None

    def when(self, moment: int | None = None) -> str:
        """A time in the exchange's zone: 'Nov 19, 2026, 11:32 EST'."""
        return _when(self.time if moment is None else moment, self.offset, self.zone)

    @property
    def closed(self) -> str:
        """When the last regular session closed: 'Nov 19, 2026, 16:00 EST'. Empty if unknown."""
        if self.close_time is None:
            return ""
        return _when(self.close_time, *eastern_at(self.close_time))

    @property
    def close_day(self) -> str:
        """The day of that close: 'Nov 19'."""
        return self.closed.split(",")[0]

    @property
    def line(self) -> tuple[tuple[int, float], ...]:
        """The series of the day, ending at the last trade.

        The source's series lags its last price by a minute or two. A chart that ends on the
        series would put its last point beside the price it names, not on it.
        """
        earlier = tuple(point for point in self.points if point[0] < self.time)
        return (*earlier, (self.time, self.price)) if earlier else ()


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
            quote.outside,
            quote.close,
        )


class Source(Protocol):
    """Anything that can say what a symbol trades at. It raises SourceError when it cannot."""

    name: str

    def page(self, symbol: str) -> str: ...

    def ask(self, symbol: str, company: str, now: int) -> Snapshot: ...


def get_json(url: str) -> Any:
    """One HTTPS request for JSON. Raises SourceError with a short reason."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    request = urllib.request.Request(url, headers=headers)  # noqa: S310 - fixed https addresses
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return json.loads(response.read(2_000_000))
    except urllib.error.HTTPError as error:
        raise SourceError(f"HTTP {error.code}") from error
    except (OSError, ValueError) as error:
        raise SourceError(type(error).__name__) from error


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _named(name: str, company: str, symbol: str) -> None:
    """The symbol must belong to the expected company: never show someone else's price."""
    if company.lower() not in name.lower():
        raise SourceError(f"{symbol} is not {company} at this source")


# -- Nasdaq.com --------------------------------------------------------------------

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
STAMP = re.compile(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4}) (\d{1,2}):(\d{2}) (AM|PM) ET")
# How Nasdaq.com names the hours around the regular session, and how the page says it.
OUTSIDE = {"pre-market": "before the open", "after-hours": "after the close"}


def eastern(year: int, month: int, day: int) -> tuple[int, str]:
    """Offset from UTC and name of New York time on a date (the switch days count as whole)."""

    def sunday(month: int, nth: int) -> int:
        first = datetime(year, month, 1).weekday()  # Monday is 0
        return 1 + (6 - first) % 7 + 7 * (nth - 1)

    summer = (3, sunday(3, 2)) <= (month, day) < (11, sunday(11, 1))
    return (-14400, "EDT") if summer else (-18000, "EST")


def eastern_at(moment: int) -> tuple[int, str]:
    """New York's offset from UTC and its name at a moment given in seconds since 1970."""
    for offset, zone in ((-18000, "EST"), (-14400, "EDT")):
        local = datetime.fromtimestamp(moment, timezone(timedelta(seconds=offset)))
        if eastern(local.year, local.month, local.day) == (offset, zone):
            return offset, zone
    return -18000, "EST"


def _moment(text: object) -> tuple[int, int, str] | None:
    """'Nov 16, 2026 4:12 PM ET' as (seconds since 1970, offset from UTC, zone name)."""
    stamp = STAMP.search(str(text or ""))
    if stamp is None or stamp[1] not in MONTHS:
        return None
    month, day, year = MONTHS.index(stamp[1]) + 1, int(stamp[2]), int(stamp[3])
    hour, minute = int(stamp[4]), int(stamp[5])
    if not (1 <= hour <= 12 and minute <= 59):
        return None
    try:
        offset, zone = eastern(year, month, day)
        local = datetime(
            year,
            month,
            day,
            hour % 12 + (12 if stamp[6] == "PM" else 0),
            minute,
            tzinfo=timezone(timedelta(seconds=offset)),
        )
    except ValueError:
        return None
    return int(local.timestamp()), offset, zone


def _regular_close(secondary: object, traded: int) -> tuple[float, int] | None:
    """The close of the last regular session, which the service gives beside a later trade.

    Before the open and after the close its first figure is a trade outside regular hours, and a
    second one reads "Closed at Nov 16, 2026 4:00 PM ET". Anything else is left out, not guessed.
    """
    if not isinstance(secondary, dict):
        return None
    said = str(secondary.get("lastTradeTimestamp") or "").strip()
    moment = _moment(said) if said.startswith("Closed at ") else None
    try:
        price = _dollars(secondary.get("lastSalePrice"))
    except SourceError:
        return None
    if moment is None or price is None or price <= 0 or moment[0] > traded:
        return None
    return price, moment[0]


def _dollars(text: object) -> float | None:
    """'$357.70' as a number; None when the source gives no price."""
    if not isinstance(text, str) or text.strip() in {"", "N/A", "NA", "--"}:
        return None
    if not re.fullmatch(r"\$[\d,]+(\.\d+)?", text.strip()):
        raise SourceError("price not in dollars")
    return float(text.strip()[1:].replace(",", ""))


def read_nasdaq(
    payload: dict[str, Any], *, symbol: str, company: str, name: str, page: str, now: int
) -> Snapshot:
    """Read the answer of Nasdaq.com's quote service: {"info": ..., "chart": ...}."""
    info = payload.get("info")
    if not isinstance(info, dict):
        raise SourceError("unexpected answer")
    data = info.get("data")
    if not isinstance(data, dict):
        codes = ((info.get("status") or {}).get("bCodeMessage")) or []
        if any(isinstance(c, dict) and c.get("code") == 1001 for c in codes):
            return Snapshot("awaiting", name, page, now, None, f"{name} does not list {symbol} yet")
        raise SourceError("unexpected answer")
    if data.get("symbol") != symbol:
        raise SourceError("answer for another symbol")
    listed_as = str(data.get("companyName") or "")
    _named(listed_as, company, symbol)
    primary = data.get("primaryData")
    if not isinstance(primary, dict):
        raise SourceError("unexpected answer")
    price = _dollars(primary.get("lastSalePrice"))
    if price is None:
        detail = f"{name} lists {symbol} as {listed_as}, with no trade yet"
        return Snapshot("awaiting", name, page, now, None, detail)
    if price <= 0:
        raise SourceError("price not in dollars")
    stamp = _moment(primary.get("lastTradeTimestamp"))
    if stamp is None:
        raise SourceError("time of the trade not understood")
    traded, offset, zone = stamp
    status = str(data.get("marketStatus") or "").strip().lower()
    closed = _regular_close(data.get("secondaryData"), traded)

    span = re.fullmatch(
        r"\$?([\d,.]+)\s*[-/]\s*\$?([\d,.]+)",
        str(((data.get("keyStats") or {}).get("dayrange") or {}).get("value") or "").strip(),
    )
    ends = sorted(float(part.replace(",", "")) for part in span.groups()) if span else None
    volume_text = str(primary.get("volume") or "").replace(",", "")
    volume = float(volume_text) if re.fullmatch(r"\d+(\.\d+)?", volume_text) else None

    points = []
    chart = (
        (payload.get("chart") or {}).get("data") if isinstance(payload.get("chart"), dict) else None
    )
    for point in (chart or {}).get("chart") or [] if isinstance(chart, dict) else []:
        moment, value = _number(point.get("x")), _number(point.get("y"))
        if moment is not None and value is not None and value > 0:
            # The service stamps its points with New York wall-clock time written as if it were UTC.
            points.append((int(moment / 1000) - offset, value))
    # No previous close is read here. The service gives one with its chart only, and before the
    # open it was seen to be the close of the session before the last one (2026-11-16).
    quote = Quote(
        symbol=symbol,
        name=listed_as,
        exchange=str(data.get("exchange") or ""),
        price=price,
        time=traded,
        zone=zone,
        offset=offset,
        day_high=ends[1] if ends else None,
        day_low=ends[0] if ends else None,
        volume=round(volume) if volume is not None else None,
        points=tuple(points),
        outside=OUTSIDE.get(status, ""),
        close=closed[0] if closed else None,
        close_time=closed[1] if closed else None,
    )
    is_open = status in {"open", "market open"}
    return Snapshot("trading" if is_open else "closed", name, page, now, quote)


class NasdaqQuote:
    """The quote service behind nasdaq.com, the exchange where the stock lists. Unofficial use."""

    name = "Nasdaq.com"
    host = "https://api.nasdaq.com/api/quote"

    def page(self, symbol: str) -> str:
        return f"https://www.nasdaq.com/market-activity/stocks/{symbol.lower()}"

    def fetch(self, symbol: str) -> dict[str, Any]:
        info = get_json(f"{self.host}/{symbol}/info?assetclass=stocks")
        chart = None
        has_price = isinstance(info, dict) and isinstance(info.get("data"), dict)
        if has_price:
            with contextlib.suppress(SourceError):  # the page works without the line of the day
                chart = get_json(f"{self.host}/{symbol}/chart?assetclass=stocks")
        return {"info": info, "chart": chart}

    def ask(self, symbol: str, company: str, now: int) -> Snapshot:
        return read_nasdaq(
            self.fetch(symbol),
            symbol=symbol,
            company=company,
            name=self.name,
            page=self.page(symbol),
            now=now,
        )


# -- Yahoo Finance -------------------------------------------------------------------


def read_yahoo(
    payload: dict[str, Any], *, symbol: str, company: str, name: str, page: str, now: int
) -> Snapshot:
    """Read the answer of Yahoo Finance's chart data."""

    def snapshot(state: State, quote: Quote | None = None, detail: str = "") -> Snapshot:
        return Snapshot(state, name, page, now, quote, detail)

    chart = payload.get("chart")
    if not isinstance(chart, dict):
        raise SourceError("unexpected answer")
    results = chart.get("result")
    if not results:
        if chart.get("error"):
            return snapshot("awaiting", detail=f"{name} does not list {symbol} yet")
        raise SourceError("unexpected answer")
    result = results[0]
    meta = result.get("meta") if isinstance(result, dict) else None
    if not isinstance(meta, dict) or meta.get("symbol") != symbol:
        raise SourceError("answer for another symbol")
    listed_as = str(meta.get("longName") or meta.get("shortName") or "")
    _named(listed_as, company, symbol)
    price, traded = _number(meta.get("regularMarketPrice")), _number(meta.get("regularMarketTime"))
    if price is None or traded is None:
        return snapshot(
            "awaiting", detail=f"{name} lists {symbol} as {listed_as}, with no trade yet"
        )
    if price <= 0 or meta.get("currency") != "USD":
        raise SourceError("price not in dollars")

    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0] or {}).get("close") or []
    points = tuple(
        (int(moment), close)
        for moment, raw in zip(result.get("timestamp") or [], closes, strict=False)
        if (close := _number(raw)) is not None and _number(moment) is not None
    )
    offset = int(_number(meta.get("gmtoffset")) or 0)
    # A previous close needs a previous trading day. Without a first trading day before this
    # one, whatever the field holds is not shown.
    first = _number(meta.get("firstTradeDate"))
    seasoned = first is not None and (first + offset) // 86400 < (traded + offset) // 86400
    quote = Quote(
        symbol=symbol,
        name=listed_as,
        exchange=str(meta.get("fullExchangeName") or meta.get("exchangeName") or ""),
        price=price,
        time=int(traded),
        zone=str(meta.get("timezone") or "UTC"),
        offset=offset,
        day_high=_number(meta.get("regularMarketDayHigh")),
        day_low=_number(meta.get("regularMarketDayLow")),
        volume=_number(meta.get("regularMarketVolume")),
        previous_close=_number(meta.get("previousClose")) if seasoned else None,
        points=points,
    )
    hours = ((meta.get("currentTradingPeriod") or {}).get("regular")) or {}
    start, end = _number(hours.get("start")), _number(hours.get("end"))
    is_open = start is not None and end is not None and start <= now < end
    return snapshot("trading" if is_open else "closed", quote)


class YahooChart:
    """Yahoo Finance chart data, the feed behind yfinance. Free, unofficial, delayed.

    It answers "too many requests" to addresses that ask without a browser session, so it
    comes second.
    """

    name = "Yahoo Finance"
    hosts = ("query2.finance.yahoo.com", "query1.finance.yahoo.com")

    def page(self, symbol: str) -> str:
        return f"https://finance.yahoo.com/quote/{symbol}/"

    def fetch(self, symbol: str) -> dict[str, Any]:
        problem = "no answer"
        for host in self.hosts:
            url = f"https://{host}/v8/finance/chart/{symbol}?range=1d&interval=5m&includePrePost=false"
            try:
                payload = get_json(url)
            except SourceError as error:
                if str(error) == "HTTP 404":  # the source's way of saying: unknown symbol
                    return {"chart": {"result": None, "error": {"code": "Not Found"}}}
                problem = str(error)
            else:
                if isinstance(payload, dict):
                    return payload
                problem = "unexpected answer"
        raise SourceError(problem)

    def ask(self, symbol: str, company: str, now: int) -> Snapshot:
        return read_yahoo(
            self.fetch(symbol),
            symbol=symbol,
            company=company,
            name=self.name,
            page=self.page(symbol),
            now=now,
        )


# -- several sources, and recorded answers ----------------------------------------------


class Chain:
    """Ask the sources in order; the first that answers wins."""

    def __init__(self, sources: list[Source]) -> None:
        self.sources = sources
        self.name = " and ".join(source.name for source in sources)

    def page(self, symbol: str) -> str:
        return self.sources[0].page(symbol)

    def ask(self, symbol: str, company: str, now: int) -> Snapshot:
        problems = []
        for source in self.sources:
            try:
                return source.ask(symbol, company, now)
            except SourceError as error:
                problems.append(str(error))
            except (KeyError, TypeError, ValueError, AttributeError, IndexError) as error:
                problems.append(f"unexpected answer ({type(error).__name__})")
        raise SourceError(", ".join(problems))


class RecordedAnswer:
    """A saved answer, for tests. It names itself so it can never pass for a real quote."""

    name = "TEST DATA, not a real quote"

    def __init__(self, path: Path) -> None:
        self.path = path

    def page(self, symbol: str) -> str:
        return f"https://example.org/test-data/{symbol}"

    def fetch(self, symbol: str) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError) as error:
            raise SourceError(type(error).__name__) from error
        if not isinstance(payload, dict):
            raise SourceError("unexpected answer")
        return payload

    def ask(self, symbol: str, company: str, now: int) -> Snapshot:
        payload = self.fetch(symbol)
        reader = read_nasdaq if "info" in payload else read_yahoo
        return reader(
            payload, symbol=symbol, company=company, name=self.name, page=self.page(symbol), now=now
        )


def source_from(setting: str) -> Source | None:
    """`auto` (Nasdaq.com, then Yahoo Finance), `nasdaq`, `yahoo`, `off`, or `file:<path>`."""
    if setting == "off":
        return None
    if setting == "auto":
        return Chain([NasdaqQuote(), YahooChart()])
    if setting == "nasdaq":
        return NasdaqQuote()
    if setting == "yahoo":
        return YahooChart()
    if setting.startswith("file:"):
        return RecordedAnswer(Path(setting[5:]))
    raise ValueError(f"unknown market source: {setting}")


def check(
    source: Source, symbol: str, company: str, previous: Snapshot | None, now: int
) -> Snapshot:
    """Ask the source once. A failure never raises: it becomes the `unavailable` state."""
    last = previous.quote if previous else None
    try:
        snapshot = source.ask(symbol, company, now)
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

    def fact(
        key: str, title: str, value: float | str, unit: str, shown: str, period: str = when
    ) -> Fact:
        return Fact.model_validate(
            {
                "id": f"market.{key}",
                "title": title,
                "label": "MARKET",
                "value": value,
                "unit": unit,
                "as_filed": shown,
                "period": period,
                "quote": (
                    f"{title}: {shown}, as given by {snapshot.source} "
                    f"for {quote.symbol} ({quote.name}, {quote.exchange})"
                ),
                "context": f"{snapshot.source}: delayed, unofficial",
                "outlet": snapshot.source,
                "url": snapshot.page,
                "accessed": read_at,
            }
        )

    price = f"${quote.price:,.2f}"
    last = f"Last share price, {quote.outside}" if quote.outside else "Last share price"
    out = [
        fact("price", last, quote.price, "USD/share", price),
        fact("time", "Time of the last trade", when, "text", when),
    ]
    if quote.close is not None and quote.close_time is not None:
        closed = f"${quote.close:,.2f}"
        title = "Closing price of the last regular session"
        out.append(fact("close", title, quote.close, "USD/share", closed, quote.closed))
    optional = (
        ("day_high", "Highest price in regular trading hours", quote.day_high, "USD/share"),
        ("day_low", "Lowest price in regular trading hours", quote.day_low, "USD/share"),
        ("previous_close", "Previous close", quote.previous_close, "USD/share"),
        ("volume", "Shares traded today", quote.volume, "count"),
    )
    for key, title, value, unit in optional:
        if value is not None:
            shown = f"{value:,.0f}" if unit == "count" else f"${value:,.2f}"
            out.append(fact(key, title, value, unit, shown))
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
