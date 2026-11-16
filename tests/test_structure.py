"""Loop 004: where the shares go, when they unlock, who controls the company, the timeline."""

from __future__ import annotations

import re

import pytest

from ipo_monitor.calc import Calc
from ipo_monitor.edgar import Filing, Watch
from ipo_monitor.facts import Facts
from ipo_monitor.figures import unlock_groups, unlock_label, unlock_steps
from ipo_monitor.render import Page, timeline


def test_the_new_facts_are_copied_from_the_filing(facts: Facts) -> None:
    assert facts.num("underwriting.total") == 825_000_000
    banks = facts.text("underwriting.banks").split("; ")
    assert (len(banks), banks[0], banks[-1]) == (
        22,
        "Goldman Sachs & Co. LLC",
        "SG Americas Securities, LLC",
    )
    assert facts.num("holders.existing_after") == 11_910_321_243
    assert (facts.num("holders.existing_after_pct"), facts.num("holders.new_after_pct")) == (
        91.0,
        6.3,
    )
    assert facts.num("offering.insider_interest") == 303_000_000
    assert "NVIDIA" in facts.text("placement.buyers")
    assert (facts.num("control.class_f_pct"), facts.num("control.class_a_pct")) == (50.1, 49.9)
    assert facts.text("control.class_t") == "a majority"
    assert facts.get("control.class_a").as_filed == "one"
    for fact_id in ("underwriting.total", "control.class_f_pct", "unlock.01"):
        fact = facts.get(fact_id)
        assert fact.label == "FILED", fact_id
        assert fact.page, fact_id
        assert fact.quote, fact_id


def test_the_lock_up_schedule_is_the_filing_s_table(facts: Facts) -> None:
    steps = unlock_steps(facts.ids())
    assert len(steps) == 23
    first, biggest, last = facts.get("unlock.01"), facts.get("unlock.12"), facts.get("unlock.23")
    assert (first.value, first.as_filed) == (316_000_000, "up to 316 million")
    assert (biggest.value, biggest.as_filed) == (3_000_000_000, "up to 3.0 billion")
    assert last.value == 1_900_000_000
    assert facts.text("unlock.02.when") == "27th day after the date of this prospectus"
    assert "180th day after the date of this prospectus" in facts.text("unlock.12.when")
    assert (first.page, last.page) == ("318", "319")
    assert "up to" in (first.context or "")


def test_the_deal_s_arithmetic(calcs: dict[str, Calc]) -> None:
    # By hand: 801,351,354 + 23,648,646 + 123,750,000 + 351,351,348.
    assert calcs["deal.shares_all"].value == 1_300_101_348
    # 351,351,348 / 13,086,672,593 = 2.6848%.
    assert calcs["holders.placement_after_pct"].value == pytest.approx(2.6848, abs=1e-4)
    # 825,000,000 / 7,427,991,791 x 49.9 = 5.5422%.
    assert calcs["control.ipo_votes_pct"].value == pytest.approx(5.5422, abs=1e-4)
    assert calcs["control.ipo_votes_pct"].note


def test_short_labels_of_the_lock_up_steps() -> None:
    assert unlock_label("The first trading day following the date of this prospectus") == (
        "1",
        "prospectus",
    )
    assert unlock_label("27th day after the date of this prospectus") == ("27", "prospectus")
    assert unlock_label("13th day after the FY26 Earnings Release Date") == ("13", "FY26")
    assert unlock_label(
        "The second full trading day on Nasdaq immediately following the public release of our "
        "annual financial results for the fiscal year ending December 31, 2026"
    ) == ("R", "FY26")
    assert unlock_label(
        "The earlier of (x) the second full trading day ... fiscal quarter ending March 31, 2027 "
        "... and (y) immediately after the close of trading on the 180th day after the date of "
        "this prospectus"
    ) == ("R*", "Q1 27")
    with pytest.raises(ValueError, match="not understood"):
        unlock_label("when the moon is full")
    labels = [("1", "a"), ("2", "a"), ("R", "b"), ("3", "c")]
    assert unlock_groups(labels) == [("a", 0, 1), ("b", 2, 2), ("c", 3, 3)]


def test_the_timeline_with_and_without_the_sec_s_list() -> None:
    alone = timeline(None, priced=False, trading=False)
    assert [(m.what, m.state) for m in alone] == [
        ("Form S-1/A, Amendment No. 2", "done"),
        ("priced", "next"),
        ("first trade", "later"),
        ("first existing shares may be sold", "later"),
    ]
    url = "https://www.sec.gov/x"
    filings = (
        Filing("a5", "FWP", "2026-11-12", url),
        Filing("a4", "FWP", "2026-11-12", url),
        Filing("a3", "S-1/A", "2026-11-10", url),
        Filing("a2", "S-1/A", "2026-11-02", url),
        Filing("a1", "S-1", "2026-10-26", url),
    )
    watched = timeline(Watch("ok", 0, filings), priced=True, trading=False)
    assert [(m.what, m.day, m.count, m.last_day) for m in watched[:3]] == [
        ("Form S-1", "2026-10-26", 1, ""),
        ("Form S-1/A", "2026-11-02", 2, "2026-11-10"),
        ("Form FWP", "2026-11-12", 2, "2026-11-12"),
    ]
    assert [m.state for m in watched[3:]] == ["done", "next", "later"]
    assert [m.state for m in timeline(Watch("ok", 0, filings), True, True)[3:5]] == [
        "done",
        "done",
    ]


def test_the_page_has_its_new_panels_and_header(page: Page) -> None:
    html = page.html
    for panel in ("shares", "unlock", "control", "timeline"):
        assert f'<section class="panel" id="{panel}"' in html
        assert f'<a href="#{panel}">' in html
    assert {"deal.shares", "unlock.steps"} <= set(page.charts)
    glance = html[html.index('class="glance"') : html.index('<nav class="keys"')]
    for ref in (
        "offering.price_low",
        "offering.shares_total",
        "value.mcap_out.low",
        "press.cnbc.pricing_date",
        "press.cnbc.trading_date",
    ):
        assert f'data-ref="{ref}"' in glance, ref
    assert re.findall(r'<li class="st-(\w+)">', glance) == ["done", "next", "later", "later"]
    assert '<svg class="mark"' in html
    # Every lock-up step is a row of the table, with the filing's wording as its source.
    for index in range(1, 24):
        assert f'data-ref="unlock.{index:02d}.when"' in html
    assert "Goldman Sachs &amp; Co. LLC" in html
