"""Formatting never changes a value, only how it reads."""

from __future__ import annotations

import pytest

from ipo_monitor import fmt
from ipo_monitor.render import display, precise, slug


@pytest.mark.parametrize(
    ("value", "style", "expected"),
    [
        (968_413_771_882, "b", "$968B"),
        (1_019_355_000_000, "b", "$1,019B"),
        (13.8e9, "b", "$13.8B"),
        (900.9e9, "b1", "$900.9B"),
        (-104_039e6, "b1", "−$104.0B"),
        (16_956e6, "m", "$16,956M"),
        (16_956e6, "t", "16,956"),
        (-567e6, "t", "−567"),
        (74.0, "p", "$74.00"),
    ],
)
def test_money(value: float, style: str, expected: str) -> None:
    assert fmt.money(value, style) == expected


def test_signed_values() -> None:
    assert fmt.money(974e6, "t", plus=True) == "+974"
    assert fmt.percent(46.74, "signed") == "+47%"
    assert fmt.percent(-3.34, "signed") == "−3%"
    assert fmt.percent(1126.9) == "1,127%"
    assert fmt.percent(90.66, "one") == "90.7%"


def test_shares_ratios_dates() -> None:
    assert fmt.shares(13_086_672_593) == "13.09B"
    assert fmt.shares(1_563_617_444, "m") == "1,563.6M"
    assert fmt.shares(13_086_672_593, "full") == "13,086,672,593"
    assert fmt.ratio(13.32) == "13.3×"
    assert fmt.ratio(1.7192, "usd") == "$1.72"
    assert fmt.ratio(11.12, "years") == "11.1"
    assert fmt.iso_date("2026-11-10") == "Nov 10, 2026"
    assert fmt.iso_date("2026-11-19", "short") == "Nov 19"
    assert fmt.page_ref("164") == "p. 164"
    assert fmt.page_ref("sheet 2") == "unnumbered front page (sheet 2)"
    assert fmt.page_ref(None) == ""


def test_display_and_precise() -> None:
    assert display(11_900, "count") == "11,900"
    assert display("ANT", "text") == "ANT"
    assert display("2026-11-10", "date") == "Nov 10, 2026"
    assert precise(1_297_058_771_882, "USD") == "$1,297.1B"
    assert precise(2.91, "USD/share") == "$2.91"
    assert precise(13_086_672_593, "shares") == "13,086,672,593"
    assert precise(13.3234, "ratio") == "13.32"
    assert slug("q.revenue.2026q3") == "src-q-revenue-2026q3"
