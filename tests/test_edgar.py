"""The SEC's filing index: what is listed, what is noticed, and the price on a final cover.

No test here talks to sec.gov. `filings-2026-11-16.json` is what EDGAR really answered that day,
reduced to the columns the reader uses. The files with TEST in their name are invented, in the
same shape. The cover is a real excerpt of Amendment No. 2.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from email.message import Message
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ipo_monitor import edgar
from ipo_monitor.config import ConfigError, Settings
from ipo_monitor.edgar import Edgar, Filing, RecordedIndex, SourceError, Watch
from ipo_monitor.facts import Facts
from ipo_monitor.render import render_page
from ipo_monitor.web import create_app

from .conftest import FACTS_DIR, MARKET, ROOT
from .test_web import Audit

EDGAR = ROOT / "tests" / "fixtures" / "edgar"
CIK = "2130357"
AMENDMENT_2 = "0001628280-26-072484"  # the filing the page reads
ABOUT: dict[str, Any] = {"cik": CIK, "company": "Anthropic, PBC", "low": 70.0, "high": 78.0}
FINAL = Filing("0001628280-26-999004", "424B4", "2026-11-19", "https://www.sec.gov/x/")
CONTACT = "someone@example.org"  # stands for the owner's address


def saved(name: str) -> dict[str, Any]:
    return json.loads((EDGAR / name).read_text("utf-8"))  # type: ignore[no-any-return]


def cover(*, final: bool = True, price: str = "", total: str = "") -> bytes:
    """The real cover of Amendment No. 2, optionally turned into a made-up final one."""
    data = (EDGAR / "s1a2-cover.html").read_bytes()
    if final:
        data = data.replace(b"Subject to Completion. Dated", b"")
    if price:
        row = data.index(b"Initial public offering price")
        filled = re.sub(rb"\$(&nbsp;)+", b"$" + price.encode(), data[row:], count=1)
        filled = re.sub(rb"\$(&nbsp;)+", b"$" + total.encode(), filled, count=1)
        data = data[:row] + filled
    return data


class Fake:
    """An index that answers what it is given and counts the questions."""

    name = "Fake index"

    def __init__(self, index: dict[str, Any] | Exception, page: bytes | Exception = b"") -> None:
        self.answer, self.page = index, page
        self.indexes = self.covers = 0

    def index(self, cik: str) -> dict[str, Any]:
        self.indexes += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    def cover(self, url: str) -> bytes:
        self.covers += 1
        if isinstance(self.page, Exception):
            raise self.page
        return self.page


def ask(source: edgar.Index, previous: Watch | None = None, now: int = 1000) -> Watch:
    return edgar.check(source, previous, now, **ABOUT)


# -- the index ---------------------------------------------------------------------------------


def test_the_index_lists_filings_newest_first(facts: Facts) -> None:
    filings = edgar.read_index(saved("filings-TEST.json")["index"], cik=CIK, company="Anthropic")
    assert [(f.form, f.filed) for f in filings] == [
        ("S-1/A", "2026-11-10"),
        ("S-1/A", "2026-11-03"),
        ("S-1", "2026-10-20"),
    ]
    # The link is built the way the real one is: it equals the link of the filing the page reads.
    assert filings[0].url == facts.documents["s1a2"].url
    assert filings[0].accession == facts.documents["s1a2"].accession == AMENDMENT_2
    assert filings[0].meaning == "amended registration statement"
    assert Filing("x", "NT 10-K", "2027-01-01", "u").meaning == ""  # shown by its name alone


def test_the_real_index_of_the_registrant(facts: Facts) -> None:
    # What EDGAR answered on 2026-11-16, reduced to the columns the reader uses.
    watch = ask(RecordedIndex(EDGAR / "filings-2026-11-16.json"))
    assert watch.state == "ok"
    assert len(watch.filings) == 14
    assert [f.form for f in watch.filings[:8]] == ["FWP"] * 5 + ["S-1/A", "S-1/A", "S-1"]
    assert watch.filings[5].url == facts.documents["s1a2"].url  # the filing the page reads
    assert watch.filings[-1].form == "DRS"
    assert watch.filings[0].meaning == "free writing prospectus, extra material for investors"
    # Material for investors filed after Amendment No. 2 does not change the figures.
    assert watch.newer_than(AMENDMENT_2) is None
    assert watch.prospectus is None
    html = render_page(facts, release="test", filings=watch).html
    assert "watching the SEC · latest:" in html
    assert "new filing" not in html
    # Five documents of the same form and day take one line, each with its own link.
    lines = edgar.batches(watch.filings)
    assert len(lines) == edgar.SHOWN == 8
    assert (lines[0].first.form, len(lines[0].others)) == ("FWP", 4)
    assert [line.first.form for line in lines[1:]] == ["S-1/A", "S-1/A", "S-1"] + ["DRS/A"] * 4
    panel = html[html.index('id="filings"') : html.index("</main>")]
    assert panel.count("<tr>") == 8
    assert panel.count("anthropicpbc-fwp") == 5
    assert "same day:" in panel
    checked = audit(html)
    assert [text for text in checked.loose_text if re.search(r"\d", text)] == []


def test_an_index_that_is_not_the_registrant_or_not_understood_is_refused() -> None:
    good = saved("filings-TEST.json")["index"]

    def changed(**fields: Any) -> dict[str, Any]:
        answer: dict[str, Any] = copy.deepcopy(good)
        answer["filings"]["recent"].update(fields)
        return answer

    refused = [
        ({**good, "cik": "320193"}, "another company"),
        ({**good, "name": "Apple Inc."}, "another company"),
        ({**good, "filings": {}}, "unexpected answer"),
        (changed(form=["S-1/A"]), "unexpected answer"),  # columns of different lengths
        (changed(accessionNumber=["1", "2", "3"]), "unexpected answer"),
        (changed(filingDate=["yesterday", "2026-11-03", "2026-10-20"]), "unexpected answer"),
        (changed(primaryDocument=None), "unexpected answer"),
    ]
    for answer, problem in refused:
        with pytest.raises(SourceError, match=problem):
            edgar.read_index(answer, cik=CIK, company="Anthropic, PBC")
    # A document name that is not a plain file name is not put in a link.
    odd = changed(primaryDocument=["../../x", "a.htm", ""])
    filings = edgar.read_index(odd, cik=CIK, company="Anthropic")
    assert filings[0].url.endswith("/000162828026072484/")
    assert filings[2].url.endswith("/000162828026999001/")


def test_what_counts_as_a_newer_filing() -> None:
    watch = ask(RecordedIndex(EDGAR / "filings-TEST.json"))
    assert (watch.state, watch.source) == ("ok", "TEST DATA, not real filings")
    assert watch.prospectus is None
    assert watch.newer_than(AMENDMENT_2) is None  # the page reads the latest one

    later = saved("filings-TEST.json")["index"]
    recent = later["filings"]["recent"]
    recent["accessionNumber"][:0] = ["0001628280-26-999009", "0001628280-26-999008"]
    recent["filingDate"][:0] = ["2026-11-13", "2026-11-12"]
    recent["form"][:0] = ["8-A12B", "S-1/A"]
    recent["primaryDocument"][:0] = ["a.htm", "b.htm"]
    watch = ask(Fake(later))
    newer = watch.newer_than(AMENDMENT_2)
    # A registration of the listing is listed, but only a prospectus changes the figures.
    assert watch.filings[0].form == "8-A12B"
    assert newer is not None
    assert (newer.form, newer.filed) == ("S-1/A", "2026-11-12")


# -- the price on the cover ----------------------------------------------------------------


def read(data: bytes, filing: Filing = FINAL, company: str = "Anthropic, PBC") -> edgar.Price:
    return edgar.read_price(data, filing, company=company, low=70.0, high=78.0)


def test_the_price_is_read_from_a_final_cover() -> None:
    # The real cover of Amendment No. 2, made final with a made-up price: test data.
    price = read(cover(price="74.00", total="61,050,000,000"))
    assert (price.value, price.shares, price.total) == (74.0, 825_000_000, 61_050_000_000.0)
    assert price.quote == (
        "825,000,000 Shares … Initial public offering price $74.00 $61,050,000,000"
    )
    assert price.filing == FINAL
    fact, document = edgar.price_fact(price, "Anthropic, PBC")
    assert (fact.id, fact.label, fact.value, fact.as_filed) == (
        "pricing.ipo_price",
        "FILED",
        74.0,
        "$74.00",
    )
    assert (document.form, document.filed, document.url) == ("424B4", "2026-11-19", FINAL.url)


def test_a_price_that_cannot_be_trusted_is_refused() -> None:
    real = cover(final=False)  # Amendment No. 2 as it was filed: preliminary, price blank
    amendment = Filing(AMENDMENT_2, "S-1/A", "2026-11-10", "u")
    refused: list[tuple[Callable[[], object], str]] = [
        (lambda: read(real, amendment), "not a final prospectus"),
        (lambda: read(real), "a preliminary prospectus"),
        (lambda: read(cover()), "the price is blank"),
        (lambda: read(cover(price="74.00", total="61,050,000,001")), "not the price times"),
        (lambda: read(cover(price="74", total="61,050,000,000")), "dollars and cents"),
        (lambda: read(cover(price="740.00", total="610,500,000,000")), "far from the filed"),
        (lambda: read(cover(price="74.00", total="61,050,000,000"), company="Apple Inc."), "name"),
        (lambda: read(b"<html><body>Nothing here</body></html>"), "no price row"),
    ]
    for attempt, problem in refused:
        with pytest.raises(SourceError, match=problem):
            attempt()


# -- one check, and the next ---------------------------------------------------------------


def test_the_cover_of_a_final_prospectus_is_read_once() -> None:
    index = saved("filings-final-TEST.json")["index"]
    source = Fake(index, cover(price="74.00", total="61,050,000,000"))
    first = ask(source)
    assert first.prospectus is not None
    assert (first.prospectus.form, first.cover_read) == ("424B4", True)
    assert first.price is not None
    assert first.price.value == 74.0
    assert first.newer_than(AMENDMENT_2) == first.prospectus
    second = ask(source, first, now=2000)
    assert (source.indexes, source.covers) == (2, 1)  # a document does not change
    assert second.price == first.price
    assert second.shown == first.shown  # nothing new to draw

    # A cover that cannot be read is judged once too, and says why.
    blank = Fake(index, cover())
    watch = ask(blank)
    assert (watch.price, watch.price_problem, watch.cover_read) == (
        None,
        "the price is blank",
        True,
    )
    ask(blank, watch)
    assert blank.covers == 1

    # A cover that could not be downloaded is asked for again.
    down = Fake(index, SourceError("HTTP 503"))
    watch = ask(down)
    assert (watch.price_problem, watch.cover_read) == ("not downloaded (HTTP 503)", False)
    ask(down, watch)
    assert down.covers == 2


def test_when_the_sec_does_not_answer_what_was_known_stays() -> None:
    known = ask(RecordedIndex(EDGAR / "filings-final-TEST.json"))
    assert known.price is not None
    for failure in (SourceError("HTTP 403"), KeyError("filings")):
        watch = ask(Fake(failure), known, now=5000)
        assert (watch.state, watch.checked) == ("unavailable", 5000)
        assert (watch.filings, watch.price) == (known.filings, known.price)
    nothing = ask(Fake(SourceError("HTTP 403")))
    assert (nothing.state, nothing.filings, nothing.detail) == ("unavailable", (), "HTTP 403")
    assert nothing.source == "Fake index"


def test_the_watcher_tells_the_page_only_when_something_changed() -> None:
    told: list[Watch] = []
    source = Fake(saved("filings-TEST.json")["index"])
    watcher = edgar.Watcher(source, told.append, clock=lambda: 1000.0, **ABOUT)
    assert (watcher.watch.state, watcher.wait) == ("ok", edgar.EVERY)
    asyncio.run(watcher.step())
    assert told == []
    source.answer = saved("filings-final-TEST.json")["index"]
    source.page = cover(price="74.00", total="61,050,000,000")
    asyncio.run(watcher.step())
    assert len(told) == 1
    assert told[0].price is not None
    source.answer = SourceError("HTTP 503")
    asyncio.run(watcher.step())
    asyncio.run(watcher.step())
    assert watcher.wait == 2 * edgar.EVERY  # asked less often while the SEC fails
    assert watcher.watch.price is not None


# -- the contact address -------------------------------------------------------------------


def test_the_contact_address_goes_to_the_sec_and_nowhere_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[urllib.request.Request] = []

    def refuse(request: urllib.request.Request, timeout: float = 0) -> Any:
        sent.append(request)
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    client = Edgar(CONTACT)
    with pytest.raises(SourceError) as failure:
        client.index(CIK)
    assert CONTACT not in str(failure.value)
    assert sent[0].full_url == "https://data.sec.gov/submissions/CIK0002130357.json"
    assert sent[0].get_header("User-agent") == f"ANT IPO Monitor {CONTACT}"
    for elsewhere in ("https://example.org/x", "http://www.sec.gov/x", "https://sec.gov.example/"):
        with pytest.raises(SourceError, match="not an address of the SEC"):
            client.cover(elsewhere)
    assert len(sent) == 1  # nothing left for another host


def test_an_address_that_is_not_one_is_never_echoed() -> None:
    for bad in (
        "",
        "someone",
        "a@b",
        "a b@example.org",
        f"{CONTACT}\r\nX-Other: 1",
        f"<{CONTACT}>",
    ):
        assert not edgar.valid_contact(bad)
        with pytest.raises(ValueError, match="one e-mail address") as failure:
            Edgar(bad)
        assert bad == "" or bad not in str(failure.value)
    assert edgar.valid_contact(CONTACT)

    good = {"IPO_FACTS_DIR": str(FACTS_DIR)}
    settings = Settings.from_env({**good, "SEC_CONTACT": f" {CONTACT} "})
    assert (settings.sec_contact, settings.sec_contact_refused) == (CONTACT, False)
    assert CONTACT not in repr(settings)
    refused = Settings.from_env({**good, "SEC_CONTACT": "not an address"})
    assert (refused.sec_contact, refused.sec_contact_refused) == ("", True)
    assert edgar.source_from(refused.filings, refused.sec_contact) is None  # the watch is off
    assert isinstance(edgar.source_from("auto", CONTACT), Edgar)
    assert edgar.source_from("off", CONTACT) is None
    with pytest.raises(ConfigError, match="IPO_FILINGS"):
        Settings.from_env({**good, "IPO_FILINGS": "sometimes"})


def test_the_address_is_in_no_log_and_on_no_page(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def refuse(request: urllib.request.Request, timeout: float = 0) -> Any:
        headers = Message()
        headers["User-Agent"] = str(request.get_header("User-agent"))  # what the SEC was sent
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", headers, None)

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    settings = Settings(
        "127.0.0.1", 8000, FACTS_DIR, "test", "info", filings="auto", sec_contact=CONTACT
    )
    with caplog.at_level(logging.DEBUG):
        app = create_app(settings)
        with TestClient(app) as client:
            page = client.get("/").text
            health = client.get("/health")
    assert health.json()["filings"]["state"] == "unavailable"
    assert health.json()["filings"]["source"] == "SEC EDGAR"
    assert "source unavailable" in page
    logged = caplog.text + "".join(str(getattr(r, "fields", "")) for r in caplog.records)
    for place in (page, health.text, logged, repr(settings)):
        assert CONTACT not in place
        assert "example.org" not in place


# -- the page ------------------------------------------------------------------------------


def audit(html: str) -> Audit:
    parser = Audit()
    parser.feed(html)
    return parser


def test_the_page_lists_the_filings(facts: Facts) -> None:
    watch = ask(RecordedIndex(EDGAR / "filings-TEST.json"))
    page = render_page(facts, release="test", filings=watch)
    assert page.filings == "ok"
    html = page.html
    status = html[html.index('<section class="status"') : html.index('<ul class="legend">')]
    assert "watching the SEC · latest:" in status
    assert "new filing" not in html
    panel = html[html.index('id="filings"') : html.index("</main>")]
    assert panel.count("<tr>") == 3
    assert f'href="{facts.documents["s1a2"].url}"' in panel
    assert "amended registration statement" in panel
    assert "TEST DATA, not real filings" in panel  # the source names itself
    checked = audit(html)
    assert [text for text in checked.loose_text if re.search(r"\d", text)] == []
    # Without a watch the page says so and has no list.
    plain = render_page(facts, release="test").html
    assert "not watched · this page does not check the SEC for new filings" in plain
    assert 'id="filings"' not in plain


def test_the_final_price_switches_the_page(facts: Facts) -> None:
    watch = ask(RecordedIndex(EDGAR / "filings-final-TEST.json"))
    before = render_page(facts, release="test")
    page = render_page(facts, release="test", filings=watch)
    html = page.html
    assert "new filing" in html
    assert "its price is used on this page" in html
    assert "priced at" in html
    assert "priced at" not in before.html
    assert page.checks == before.checks  # every consistency check still passes
    card = re.search(
        r'<div popover id="src-pricing-ipo-price".*?(?=<div popover id=|</body>)', html, re.S
    )
    assert card is not None
    assert "FILED" in card.group()
    assert "Initial public offering price $74.00 $61,050,000,000" in card.group()
    assert "Form 424B4, final prospectus" in card.group()
    assert "https://www.sec.gov/Archives/edgar/data/2130357/000162828026999004/" in card.group()
    checked = audit(html)
    assert [text for text in checked.loose_text if re.search(r"\d", text)] == []
    for button in checked.buttons:
        assert button.get("popovertarget") in checked.popovers

    # A final prospectus whose cover cannot be read: noticed, and nothing is taken from it.
    unread = ask(Fake(saved("filings-final-TEST.json")["index"], cover()))
    html = render_page(facts, release="test", filings=unread).html
    assert "new filing" in html
    assert "its figures are not read by this page yet" in html
    assert "the price on the cover of the final prospectus was not taken" in html
    assert "priced at" not in html


def test_the_service_with_filings_and_a_market(facts: Facts) -> None:
    settings = Settings("127.0.0.1", 8000, FACTS_DIR, "test", "info")
    app = create_app(
        settings,
        edgar_market(),
        RecordedIndex(EDGAR / "filings-final-TEST.json"),
    )
    with TestClient(app) as client:
        health = client.get("/health").json()
        page = client.get("/").text
    assert health["filings"] == {
        "state": "ok",
        "source": "TEST DATA, not real filings",
        "checked": health["filings"]["checked"],
        "latest": {"form": "424B4", "filed": "2026-11-19"},
        "final_prospectus": "2026-11-19",
        "final_price_read": True,
    }
    assert health["market"]["state"] == "trading"
    assert 'id="filings"' in page
    assert 'id="market"' in page

    # A filing index that breaks the rendering leaves the page of the facts and the market.
    broken = Fake(saved("filings-TEST.json")["index"])
    app = create_app(settings, edgar_market(), broken)
    watcher = app.state.filings
    watcher.watch = Watch("ok", 1, (Filing("a", "S-1/A", "not a date", "u"),), "Fake index")
    watcher.on_change(watcher.watch)
    with TestClient(app) as client:
        page = client.get("/").text
    assert 'id="market"' in page
    assert 'id="filings"' not in page


def edgar_market() -> Any:
    from ipo_monitor.market import RecordedAnswer

    return RecordedAnswer(MARKET / "ant-trading-TEST.json")
