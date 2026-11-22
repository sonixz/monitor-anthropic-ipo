"""Daily bars: one row per trading session, as the market source gives them.

The source is Yahoo Finance's chart data: free, unofficial and delayed. Every series names its
source and when it was read. A session still trading when the answer was read is left out:
the scanner works on closes only.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from ipo_monitor.market import SourceError

SOURCE = "Yahoo Finance"
# A plain name for this client. The source answers "too many requests" to a request that claims
# to be a desktop browser without behaving like one (seen on 2026-11-22), not to this.
USER_AGENT = "antipo.watch/1.0 (+https://antipo.watch)"


def get_json(url: str) -> Any:
    """One HTTPS request for JSON. Raises SourceError with a short reason."""
    request = urllib.request.Request(  # noqa: S310 - fixed https addresses
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return json.loads(response.read(3_000_000))
    except urllib.error.HTTPError as error:
        raise SourceError(f"HTTP {error.code}") from error
    except (OSError, ValueError) as error:
        raise SourceError(type(error).__name__) from error


@dataclass(frozen=True)
class Bar:
    """One session: its date in the exchange's own time zone, and the day's prices."""

    date: str  # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Series:
    """The completed sessions of one symbol, oldest first."""

    symbol: str  # as the page names it: RY, CTC.A, ANT
    source_symbol: str  # as the source names it: RY.TO, CTC-A.TO, ANT
    name: str
    currency: str
    exchange: str
    bars: tuple[Bar, ...]
    source: str
    page: str  # the source's page for this symbol
    read_at: int  # when the answer was read, epoch seconds

    def upto(self, date: str) -> tuple[Bar, ...]:
        """The sessions up to and including `date`."""
        return tuple(b for b in self.bars if b.date <= date)

    @property
    def last(self) -> Bar | None:
        return self.bars[-1] if self.bars else None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def read_daily(
    payload: dict[str, Any], *, symbol: str, source_symbol: str, now: int, source: str = SOURCE
) -> Series:
    """Read a Yahoo Finance chart answer with one bar a day."""
    chart = payload.get("chart")
    if not isinstance(chart, dict) or not chart.get("result"):
        raise SourceError(f"no data for {source_symbol}")
    result = chart["result"][0]
    meta = result.get("meta") or {}
    if meta.get("symbol") != source_symbol:
        raise SourceError("answer for another symbol")
    if meta.get("dataGranularity") not in (None, "1d"):
        raise SourceError("not daily bars")
    offset = int(_number(meta.get("gmtoffset")) or 0)
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0] or {}
    stamps = result.get("timestamp") or []
    columns = [quote.get(k) or [] for k in ("open", "high", "low", "close", "volume")]
    regular = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    start, end = _number(regular.get("start")), _number(regular.get("end"))
    bars: list[Bar] = []
    for index, stamp in enumerate(stamps):
        moment = _number(stamp)
        values = [_number(c[index]) if index < len(c) else None for c in columns]
        if moment is None or any(v is None for v in values):
            continue  # a session the source gives no full row for
        o, h, low, c, v = (float(x) for x in values if x is not None)
        if c <= 0 or v < 0:
            continue
        if start is not None and end is not None and start <= moment < end and now < end:
            continue  # today's session, still trading: not a close yet
        day = datetime.fromtimestamp(int(moment) + offset, UTC).strftime("%Y-%m-%d")
        bar = Bar(day, o, h, low, c, v)
        if bars and bars[-1].date == day:
            bars[-1] = bar
        else:
            bars.append(bar)
    name = str(meta.get("longName") or meta.get("shortName") or source_symbol)
    return Series(
        symbol=symbol,
        source_symbol=source_symbol,
        name=name,
        currency=str(meta.get("currency") or ""),
        exchange=str(meta.get("fullExchangeName") or meta.get("exchangeName") or ""),
        bars=tuple(bars),
        source=source,
        page=f"https://finance.yahoo.com/quote/{source_symbol}/history/",
        read_at=now,
    )


class BarSource(Protocol):
    name: str

    def daily(self, symbol: str, source_symbol: str, now: int) -> Series: ...


@dataclass
class YahooDaily:
    """A year of daily bars from Yahoo Finance, one request per symbol."""

    name: str = SOURCE
    hosts: tuple[str, ...] = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")
    pause: float = 0.4  # seconds between requests: be gentle with a free source
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False)

    def daily(self, symbol: str, source_symbol: str, now: int) -> Series:
        problem = "no answer"
        for host in self.hosts:
            url = f"https://{host}/v8/finance/chart/{source_symbol}?range=1y&interval=1d"
            try:
                payload = get_json(url)
            except SourceError as error:
                problem = str(error)
                self.sleep(self.pause)
                continue
            self.sleep(self.pause)
            if isinstance(payload, dict):
                return read_daily(payload, symbol=symbol, source_symbol=source_symbol, now=now)
            problem = "unexpected answer"
        raise SourceError(problem)


@dataclass
class RecordedDaily:
    """Saved answers in a folder, one `<SYMBOL>.json` per symbol. For tests and replays."""

    folder: Path
    name: str = "TEST DATA, recorded answers"

    def daily(self, symbol: str, source_symbol: str, now: int) -> Series:
        path = self.folder / f"{source_symbol.removesuffix('.TO')}.json"
        try:
            payload = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError) as error:
            raise SourceError(type(error).__name__) from error
        return read_daily(
            payload, symbol=symbol, source_symbol=source_symbol, now=now, source=self.name
        )
