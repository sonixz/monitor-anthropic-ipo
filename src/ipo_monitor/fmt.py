"""Formatting of values for display. Nothing here changes a value."""

from __future__ import annotations

MINUS = "−"
TIMES = "×"


def _sign(value: float, text: str, *, plus: bool = False) -> str:
    if value < 0:
        return MINUS + text
    if plus and value > 0:
        return "+" + text
    return text


def money(value: float, style: str = "b", *, plus: bool = False) -> str:
    """Dollars.

    b   billions, one decimal under $100B: $13.8B, $968B, $1,297B
    b1  billions, always one decimal: $1,297.1B
    m   millions with the symbol: $16,956M
    t   millions for table cells, no symbol: 16,956
    p   a price: $74.00
    """
    magnitude = abs(value)
    if style == "p":
        return _sign(value, f"${magnitude:,.2f}", plus=plus)
    if style == "t":
        return _sign(value, f"{magnitude / 1e6:,.0f}", plus=plus)
    if style == "m":
        return _sign(value, f"${magnitude / 1e6:,.0f}M", plus=plus)
    billions = magnitude / 1e9
    if style == "b1" or billions < 99.95:
        return _sign(value, f"${billions:,.1f}B", plus=plus)
    return _sign(value, f"${billions:,.0f}B", plus=plus)


def shares(value: float, style: str = "b") -> str:
    """Share counts: b = 13.09B, m = 1,563.6M, full = 13,086,672,593."""
    if style == "full":
        return f"{value:,.0f}"
    if style == "m":
        return f"{value / 1e6:,.1f}M"
    return f"{value / 1e9:,.2f}B"


def percent(value: float, style: str = "plain") -> str:
    """Percentages: plain = 1,127%, signed = +47%, one = 90.7%."""
    if style == "one":
        return _sign(value, f"{abs(value):,.1f}%")
    return _sign(value, f"{abs(value):,.0f}%", plus=style == "signed")


def ratio(value: float, style: str = "x") -> str:
    """Ratios: x = 13.3×, usd = $1.72, years = 11.1."""
    if style == "usd":
        return f"${value:,.2f}"
    if style == "years":
        return f"{value:,.1f}"
    return f"{value:,.1f}{TIMES}"


def count(value: float) -> str:
    return f"{value:,.0f}"


def iso_date(value: str, style: str = "long") -> str:
    """'2026-11-10' -> 'Nov 10, 2026' (long) or 'Nov 10' (short)."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    year, month, day = value.split("-")
    short = f"{months[int(month) - 1]} {int(day)}"
    return short if style == "short" else f"{short}, {year}"


def page_ref(page: str | None) -> str:
    if page is None:
        return ""
    if page.startswith("sheet "):
        return f"unnumbered front page ({page})"
    return f"p. {page}"
