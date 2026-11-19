"""The final prospectus (Form 424B4, dated Nov 18, 2026) as the page's filing.

It gives one price, $83.00, and every "after the offering" figure at that price: no range,
no "each $1.00" sensitivity. The page computes at the IPO price only, drops the views across
the range, and HISTORY lists what changed from Amendment No. 3.
"""

from __future__ import annotations

import re

import pytest

from ipo_monitor.calc import compute
from ipo_monitor.edgar import RecordedIndex
from ipo_monitor.facts import Facts
from ipo_monitor.reconcile import run_checks
from ipo_monitor.render import render_page
from ipo_monitor.versions import versions

from .conftest import snapshot_of
from .test_charts import test_every_value_a_chart_draws_is_also_a_number_in_a_table as in_tables
from .test_edgar import EDGAR, ask, audit


def test_the_final_prospectus_is_the_filing(final: Facts) -> None:
    document = final.filing
    assert (document.form, document.title) == ("424B4", "Form 424B4, final prospectus")
    assert document.filed == "2026-11-18"  # "Prospectus dated November 18, 2026"
    price = final.get("pricing.ipo_price")
    assert (price.label, price.value) == ("FILED", 83.0)
    assert final.document_of("pricing.ipo_price") == document
    assert "offering.price_low" not in final
    assert all(check.ok for check in run_checks(final))


def test_values_at_the_ipo_price(final: Facts) -> None:
    calcs = compute(final)
    assert not [k for k in calcs if k.endswith((".low", ".mid", ".high"))]
    # By hand, from the final prospectus's own figures at $83.00.
    assert calcs["offering.shares_total"].value == 956_351_354 + 23_648_646
    assert calcs["offering.size.final"].value == 980_000_000 * 83
    assert calcs["value.shares_out.final"].value == 13_219_642_276
    assert calcs["value.mcap_out.final"].value == 13_219_642_276 * 83
    owed = calcs["value.owed_shares"].value
    assert calcs["value.equity_diluted.final"].value == pytest.approx((13_219_642_276 + owed) * 83)
    assert calcs["ev.cash_after.final"].value == 232_351_000_000
    expected = (13_219_642_276 + owed) * 83 - 232_351e6 - 1_774_342_693 * 2.91
    assert calcs["ev.enterprise_value.final"].value == pytest.approx(expected)
    # Cash today + net proceeds − RSU taxes paid = cash after, to rounding (checked in reconcile).
    assert pytest.approx(232_351e6, abs=100e6) == 131_845e6 + 104_800e6 - 51_578_975 * 83


def test_the_page_at_the_ipo_price(final: Facts) -> None:
    page = render_page(final, release="test", market=snapshot_of("ant-awaiting.json"))
    html = page.html
    words = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html))
    assert "figures: final prospectus, dated Nov 18" in words
    assert "SEC Form 424B4, final prospectus · dated Nov 18, 2026" in words
    assert "across the price range" not in html
    assert "price range" not in html[html.index('<section class="glance"') :][:2000]
    assert 'data-ref="value.mcap_out.final"' in html
    assert 'data-ref="offering.size.final"' in html
    assert "Press figures" not in html
    assert "not known yet" not in html  # the lock-up note: the prospectus is dated now
    card = re.search(
        r'<div popover id="src-pricing-ipo-price".*?(?=<div popover id=|</body>)', html, re.S
    )
    assert card is not None
    assert "The initial public offering price per share is $83.00." in card.group()
    assert "Form 424B4, final prospectus" in card.group()
    checked = audit(html)
    assert [text for text in checked.loose_text if re.search(r"\d", text)] == []
    for button in checked.buttons:
        assert button.get("popovertarget") in checked.popovers
    in_tables(page)


def test_history_from_amendment_3(final: Facts) -> None:
    _, steps = versions(final)
    newest = steps[0]
    assert newest.older.title == "Form S-1/A, Amendment No. 3"
    assert newest.newer.title == "Form 424B4, final prospectus"
    ids = {c.id: c for c in newest.changes}
    for fact_id in ("offering.shares_company", "shares.total_after", "offering.price_mid"):
        assert fact_id in ids
    assert ids["offering.price_low"].after is None  # no longer given
    titles = [c.title for c in newest.changes]
    assert len(titles) == len(set(titles))  # two columns of a table are named apart
    html = render_page(final, release="test").html
    words = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html))
    assert "Form 424B4, final prospectus dated Nov 18, 2026" in words


def test_a_price_read_from_edgar_does_not_replace_the_filing(final: Facts) -> None:
    # The recorded final prospectus (test data) says $74.00: the page keeps its filing's $83.00.
    watch = ask(RecordedIndex(EDGAR / "filings-final-TEST.json"))
    html = render_page(final, release="test", filings=watch).html
    card = re.search(
        r'<div popover id="src-pricing-ipo-price".*?(?=<div popover id=|</body>)', html, re.S
    )
    assert card is not None
    assert "$83.00" in card.group()
    assert "its price is used on this page" not in html
