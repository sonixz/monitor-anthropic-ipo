"""The night of Nov 18: the price as the press reported it, before the final prospectus.

The Associated Press reported $83 a share, and an offer grown to 980 million shares raising
$81 billion. The page uses the price, says the offer size comes from the press, and keeps the
filed share counts until the final prospectus replaces the press price with its own.
"""

from __future__ import annotations

import re

import pytest

from ipo_monitor.calc import compute
from ipo_monitor.edgar import RecordedIndex
from ipo_monitor.facts import Facts
from ipo_monitor.render import render_page

from .conftest import snapshot_of
from .test_charts import test_every_value_a_chart_draws_is_also_a_number_in_a_table as in_tables
from .test_edgar import EDGAR, ask, audit


def glance(html: str) -> str:
    return html[
        html.index('<section class="glance"') : html.index(
            "</section>", html.index('<section class="glance"')
        )
    ]


def test_the_press_price_is_on_file(reported: Facts) -> None:
    price = reported.get("pricing.ipo_price")
    assert (price.label, price.value) == ("PRESS", 83.0)
    assert (
        price.quote == "Anthropic priced its initial public offering at $83 per share on Wednesday."
    )
    assert reported.num("press.ap.shares_total") == 980_000_000
    assert reported.num("press.ap.proceeds") == 81_000_000_000


def test_values_at_the_reported_price(reported: Facts) -> None:
    calcs = compute(reported)
    # By hand: the private placement buys $26 billion of shares at the IPO price.
    shares = 13_086_672_593 - 26e9 / 74 + 26e9 / 83
    assert calcs["value.shares_out.final"].value == pytest.approx(shares, rel=1e-6)
    assert calcs["value.mcap_out.final"].value == pytest.approx(shares * 83, rel=1e-6)
    assert calcs["ev.multiple.run_rate"].terms[0].ref == "ev.enterprise_value.final"


def test_the_page_says_the_offer_size_is_reported(reported: Facts) -> None:
    page = render_page(reported, release="test", market=snapshot_of("ant-awaiting.json"))
    html = page.html
    top = glance(html)
    assert "IPO price" in top
    assert "price range" not in top
    for ref in ("pricing.ipo_price", "press.ap.shares_total", "press.ap.proceeds"):
        assert f'data-ref="{ref}"' in top
    assert "Press figures; values below use the" in top
    assert 'data-ref="offering.shares_total"' in top  # the filed count, named beside it
    card = re.search(
        r'<div popover id="src-pricing-ipo-price".*?(?=<div popover id=|</body>)', html, re.S
    )
    assert card is not None
    assert "Associated Press" in card.group()
    assert "Anthropic priced its initial public offering at $83 per share" in card.group()
    assert "PRICED · WAITING FOR THE FIRST TRADE" in html
    checked = audit(html)
    assert [text for text in checked.loose_text if re.search(r"\d", text)] == []
    for button in checked.buttons:
        assert button.get("popovertarget") in checked.popovers
    in_tables(page)  # every value a chart draws is also a number on the page


def test_the_final_prospectus_replaces_the_press_price(reported: Facts) -> None:
    watch = ask(RecordedIndex(EDGAR / "filings-final-TEST.json"))
    html = render_page(reported, release="test", filings=watch).html
    card = re.search(
        r'<div popover id="src-pricing-ipo-price".*?(?=<div popover id=|</body>)', html, re.S
    )
    assert card is not None
    assert "Form 424B4, final prospectus" in card.group()
    assert "Associated Press" not in card.group()
    assert "Press figures; values below use the" not in html
    # The glance gives the offer as priced, from the same cover, not the filed range's size.
    top = glance(html)
    assert 'data-ref="final.shares_offered"' in top
    assert 'data-ref="final.total"' in top
    assert "press.ap." not in top
