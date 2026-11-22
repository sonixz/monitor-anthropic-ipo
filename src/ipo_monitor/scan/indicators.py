"""Indicators computed from daily bars: each with its formula and the sessions it used.

Every number the scanner shows about a stock comes from here, from closes and volumes read
by `bars.py`. The AI that writes the signals cites these by id; it never types a number.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass

from ipo_monitor.scan.bars import Bar

YEAR = 252  # trading sessions in a year, the usual count for a 52-week range


@dataclass(frozen=True)
class Indicator:
    key: str  # rsi14
    title: str
    value: float
    unit: str  # a currency code, "percent", "ratio" or "index"
    formula: str
    sessions: int  # how many sessions it used
    first: str  # the first and last session used
    last: str

    @property
    def shown(self) -> str:
        return show(self.value, self.unit)


def show(value: float, unit: str) -> str:
    if unit == "percent":
        return f"{value:+.1f}%"
    if unit == "ratio":
        return f"{value:.2f}×"
    if unit == "index":
        return f"{value:.0f}"
    if unit == "CAD/day" or unit == "USD/day":
        return f"${value / 1e6:,.0f}M"
    return f"${value:,.2f}"


def sma(closes: Sequence[float], n: int) -> float | None:
    """The average of the last n closes."""
    if n <= 0 or len(closes) < n:
        return None
    return sum(closes[-n:]) / n


def rsi(closes: Sequence[float], n: int = 14) -> float | None:
    """Wilder's relative strength index over n sessions.

    The first average gain and loss are plain means of the first n changes; each later change
    is folded in as (previous average × (n − 1) + change) / n. RSI = 100 − 100 / (1 + gain/loss).
    """
    if len(closes) < n + 1:
        return None
    changes = [b - a for a, b in itertools.pairwise(closes)]
    gain = sum(max(c, 0.0) for c in changes[:n]) / n
    loss = sum(max(-c, 0.0) for c in changes[:n]) / n
    for change in changes[n:]:
        gain = (gain * (n - 1) + max(change, 0.0)) / n
        loss = (loss * (n - 1) + max(-change, 0.0)) / n
    if loss == 0:
        return 100.0
    return 100 - 100 / (1 + gain / loss)


def pct(a: float, b: float) -> float:
    """How far a is from b, in percent of b."""
    return (a / b - 1) * 100


def compute(bars: Sequence[Bar], currency: str) -> dict[str, Indicator]:
    """The indicators as of the last bar given."""
    if not bars:
        return {}
    closes = [b.close for b in bars]
    last = bars[-1]
    out: dict[str, Indicator] = {}

    def add(key: str, title: str, value: float | None, unit: str, formula: str, n: int) -> None:
        if value is None:
            return
        used = bars[-n:]
        out[key] = Indicator(key, title, value, unit, formula, len(used), used[0].date, last.date)

    add("close", "Close", last.close, currency, "the close of the session", 1)
    if len(bars) >= 2:
        prev = bars[-2].close
        add(
            "change_1d",
            "Change on the day",
            pct(last.close, prev),
            "percent",
            "(close ÷ previous close − 1) × 100",
            2,
        )
    for n in (20, 50, 200):
        average = sma(closes, n)
        add(
            f"sma{n}",
            f"{n}-day average close",
            average,
            currency,
            f"the mean of the last {n} closes",
            n,
        )
        if average is not None:
            add(
                f"vs_sma{n}",
                f"Close against its {n}-day average",
                pct(last.close, average),
                "percent",
                f"(close ÷ {n}-day average − 1) × 100",
                n,
            )
    add(
        "rsi14",
        "RSI (14 days)",
        rsi(closes, 14),
        "index",
        "Wilder's RSI: 100 − 100 ÷ (1 + average gain ÷ average loss), smoothed over 14 sessions "
        "from the first session given",
        len(bars),
    )
    if len(bars) >= 21:
        add(
            "ret20",
            "Change over 20 sessions",
            pct(last.close, bars[-21].close),
            "percent",
            "(close ÷ close 20 sessions earlier − 1) × 100",
            21,
        )
    if len(bars) >= 21:
        before = [b.volume for b in bars[-21:-1]]
        average = sum(before) / 20
        if average > 0:
            add(
                "vol_ratio",
                "Volume against its 20-day average",
                last.volume / average,
                "ratio",
                "the session's shares traded ÷ the mean of the 20 sessions before",
                21,
            )
    if len(bars) >= 20:
        dollars = sum(b.close * b.volume for b in bars[-20:]) / 20
        add(
            "dollar_vol20",
            "Average value traded a day (20 sessions)",
            dollars,
            f"{currency}/day",
            "the mean of close × shares traded over the last 20 sessions",
            20,
        )
    span = bars[-YEAR:]
    if len(span) >= 60:
        high = max(b.high for b in span)
        low = min(b.low for b in span)
        n = len(span)
        add(
            "high52",
            "52-week high",
            high,
            currency,
            f"the highest price of the last {n} sessions",
            n,
        )
        add("low52", "52-week low", low, currency, f"the lowest price of the last {n} sessions", n)
        add(
            "from_high52",
            "Close against the 52-week high",
            pct(last.close, high),
            "percent",
            "(close ÷ 52-week high − 1) × 100",
            n,
        )
        add(
            "from_low52",
            "Close against the 52-week low",
            pct(last.close, low),
            "percent",
            "(close ÷ 52-week low − 1) × 100",
            n,
        )
    return out
