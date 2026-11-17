"""The header says whether the page is up to date, and never more than the SEC's list said."""

from __future__ import annotations

import re

from ipo_monitor.edgar import Filing, Watch
from ipo_monitor.facts import Facts
from ipo_monitor.render import render_page

NOON = 1_795_453_200  # 2026-11-17 12:00 ET (17:00 UTC)


def line(facts: Facts, watch: Watch | None) -> str:
    html = render_page(facts, release="test", filings=watch).html
    found = re.search(r'<p class="uptodate">(.*?)</p>', html, re.S)
    assert found is not None
    seen = re.sub(r'<span class="vh">.*?</span>', "", found.group(1))  # for screen readers
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", seen)).strip()


def current(facts: Facts) -> Filing:
    document = facts.filing
    return Filing(document.accession, "S-1/A", document.filed, document.url)


def test_not_watched_names_the_filing_only(facts: Facts) -> None:
    assert line(facts, None) == "figures: Amendment No. 3, filed Nov 17"


def test_up_to_date_when_the_list_holds_nothing_newer(facts: Facts) -> None:
    listing = Filing("0001628280-26-074342", "8-A12B", "2026-11-17", "u")  # not a prospectus
    text = line(facts, Watch("ok", NOON, (listing, current(facts))))
    assert text == "● up to date · SEC checked 12:00 ET · figures: Amendment No. 3, Nov 17"


def test_a_newer_prospectus_is_named_and_not_read(facts: Facts) -> None:
    final = Filing("0001628280-26-099999", "424B4", "2026-11-18", "u")
    text = line(facts, Watch("ok", NOON, (final, current(facts))))
    assert text.startswith("new filing Form 424B4, Nov 18")
    assert text.endswith("not read yet")
    assert "up to date" not in text


def test_a_failed_check_is_not_up_to_date(facts: Facts) -> None:
    text = line(facts, Watch("unavailable", NOON, (current(facts),)))
    assert text.startswith("last SEC check failed 12:00 ET")
    assert "up to date" not in text
    alone = line(facts, Watch("unavailable", NOON))
    assert alone == "SEC list unavailable · figures: Amendment No. 3, filed Nov 17"
