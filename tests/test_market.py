"""The market panel: what the source said, and nothing more."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ipo_monitor import market
from ipo_monitor.calc import Calc, compute
from ipo_monitor.config import Settings
from ipo_monitor.facts import Fact, Facts
from ipo_monitor.market import Quote, RecordedAnswer, Snapshot, SourceError, Watcher, YahooChart
from ipo_monitor.render import Page, render_page
from ipo_monitor.web import create_app

from .conftest import FACTS_DIR, MARKET, TRADING_NOW, snapshot_of


class Fake:
    """A source that answers what the test tells it to."""

    name = "Fake source"

    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.asked = 0

    def page(self, symbol: str) -> str:
        return f"https://example.org/{symbol}"

    def fetch(self, symbol: str) -> dict[str, Any]:
        self.asked += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer  # type: ignore[no-any-return]


def recorded(name: str) -> dict[str, Any]:
    return json.loads((MARKET / name).read_text("utf-8"))  # type: ignore[no-any-return]


def test_before_the_listing_the_source_knows_the_symbol_without_a_price() -> None:
    snapshot = snapshot_of("ant-awaiting.json")  # recorded on 2026-11-16
    assert snapshot.state == "awaiting"
    assert snapshot.quote is None
    assert (
        snapshot.detail
        == "TEST DATA, not a real quote lists ANT as Anthropic, PBC, with no trade yet"
    )
    assert market.facts(snapshot) == []


def test_a_listed_symbol_gives_price_time_volume_and_the_day() -> None:
    source = RecordedAnswer(MARKET / "aapl-listed.json")  # a real answer for a listed company
    snapshot = market.check(source, "AAPL", "Apple", None, TRADING_NOW)
    quote = snapshot.quote
    assert quote is not None
    assert snapshot.state == "trading"
    assert (quote.symbol, quote.name, quote.exchange) == ("AAPL", "Apple Inc.", "NasdaqGS")
    assert quote.price == 356.27
    assert quote.time == 1794603601
    assert quote.when() == "Nov 13, 2026, 16:00 EST"
    assert (quote.day_high, quote.day_low, quote.volume) == (360.83, 355.755, 40027467)
    assert quote.previous_close == 354.88
    assert len(quote.points) == 79
    assert quote.points[0] == (1794580200, 359.2550048828125)
    # Outside the regular hours of the answer, the market is closed.
    assert market.check(source, "AAPL", "Apple", None, TRADING_NOW + 86400).state == "closed"


def test_a_price_for_another_company_is_never_shown() -> None:
    source = RecordedAnswer(MARKET / "aapl-listed.json")
    for symbol, company in (("AAPL", "Anthropic"), ("ANT", "Apple")):
        snapshot = market.check(source, symbol, company, None, TRADING_NOW)
        assert snapshot.state == "unavailable", (symbol, company)
        assert snapshot.quote is None


@pytest.mark.parametrize(
    ("answer", "detail"),
    [
        (SourceError("HTTP 429"), "HTTP 429"),
        ({"finance": {}}, "unexpected answer"),
        ({"chart": {"result": [], "error": None}}, "unexpected answer"),
        ({"chart": {"result": [{"meta": None}]}}, "answer for another symbol"),
        ({"chart": {"result": ["x"]}}, "answer for another symbol"),
    ],
)
def test_a_failing_source_becomes_unavailable(answer: Any, detail: str) -> None:
    snapshot = market.check(Fake(answer), "ANT", "Anthropic", None, TRADING_NOW)
    assert snapshot.state == "unavailable"
    assert snapshot.quote is None
    assert snapshot.detail == detail


def test_an_unknown_symbol_is_awaiting_and_bad_prices_are_refused() -> None:
    unknown = {"chart": {"result": None, "error": {"code": "Not Found"}}}
    assert market.check(Fake(unknown), "ANT", "Anthropic", None, TRADING_NOW).state == "awaiting"
    for change in ({"regularMarketPrice": 0}, {"regularMarketPrice": -3.0}, {"currency": "EUR"}):
        answer = recorded("ant-trading-TEST.json")
        answer["chart"]["result"][0]["meta"].update(change)
        snapshot = market.check(Fake(answer), "ANT", "Anthropic", None, TRADING_NOW)
        assert (snapshot.state, snapshot.detail) == ("unavailable", "price not in dollars"), change
    text = recorded("ant-trading-TEST.json")
    text["chart"]["result"][0]["meta"]["regularMarketPrice"] = "81.25"  # not a number
    assert market.check(Fake(text), "ANT", "Anthropic", None, TRADING_NOW).state == "awaiting"


def test_the_last_quote_is_kept_while_the_source_fails() -> None:
    good = snapshot_of("ant-trading-TEST.json")
    assert good.state == "trading"
    for answer in (SourceError("no answer"), recorded("ant-awaiting.json")):
        later = market.check(Fake(answer), "ANT", "Anthropic", good, TRADING_NOW + 600)
        assert later.state == "unavailable"
        assert later.quote == good.quote
        assert later.checked == TRADING_NOW + 600
    assert later.detail == "the source stopped giving a price"


def test_the_quote_becomes_facts_with_source_and_time() -> None:
    snapshot = snapshot_of("ant-trading-TEST.json")
    by_id = {fact.id: fact for fact in market.facts(snapshot)}
    assert set(by_id) == {
        "market.price",
        "market.time",
        "market.day_high",
        "market.day_low",
        "market.volume",
    }  # no previous close on a first day: the fact does not exist
    price = by_id["market.price"]
    assert (price.label, price.value, price.unit, price.as_filed) == (
        "MARKET",
        81.25,
        "USD/share",
        "$81.25",
    )
    for fact in by_id.values():
        assert fact.outlet == "TEST DATA, not a real quote"
        assert fact.period == "Nov 13, 2026, 16:00 EST"
        assert fact.url == "https://finance.yahoo.com/quote/ANT/"
        assert "delayed, unofficial" in (fact.context or "")


def test_values_at_the_market_price(facts: Facts, calcs: dict[str, Calc]) -> None:
    with_quote = compute(facts.plus(market.facts(snapshot_of("ant-trading-TEST.json"))))
    assert "market.mcap_out" not in calcs  # nothing at a market price before a quote exists
    price = 81.25
    assert with_quote["market.mcap_out"].value == pytest.approx(13_086_672_593 * price)
    diluted = calcs["value.shares_diluted.mid"].value
    assert with_quote["market.equity_diluted"].value == pytest.approx(diluted * price)
    ev = diluted * price - 212_684e6 - calcs["ev.option_proceeds"].value
    assert with_quote["market.enterprise_value"].value == pytest.approx(ev)
    assert with_quote["market.vs_ipo"].value == pytest.approx((81.25 / 74 - 1) * 100)
    assert with_quote["market.multiple.run_rate"].value == pytest.approx(ev / 81e9)
    refs = [term.ref for term in with_quote["market.enterprise_value"].terms]
    assert refs == [
        "market.equity_diluted",
        "ev.cash_after.mid",
        "ev.option_proceeds",
        "debt.credit_facility_drawn",
    ]
    assert "middle of the filed range" in (with_quote["market.vs_ipo"].note or "")


def test_the_final_ipo_price_becomes_the_headline_price(facts: Facts) -> None:
    final = Fact.model_validate(
        {
            "id": "pricing.ipo_price",
            "title": "IPO price",
            "label": "PRESS",
            "value": 76.0,
            "unit": "USD/share",
            "as_filed": "$76.00",
            "quote": "A made-up article, for this test only.",
            "outlet": "Test outlet",
            "url": "https://example.org/priced",
            "published": "2026-11-18",
        }
    )
    priced = facts.plus([final])
    calcs = compute(priced)
    shares = 13_086_672_593 - 26e9 / 74 + 26e9 / 76
    assert calcs["value.shares_out.final"].value == pytest.approx(shares, rel=1e-6)
    assert calcs["value.mcap_out.final"].value == pytest.approx(shares * 76, rel=1e-6)
    assert calcs["ev.cash_after.final"].value == pytest.approx(212_684e6 + 2 * 793e6)
    assert calcs["ev.multiple.run_rate"].terms[0].ref == "ev.enterprise_value.final"
    page = render_page(priced, release="test", market=snapshot_of("ant-trading-TEST.json"))
    assert "priced at" in page.html
    assert 'data-ref="value.mcap_out.final"' in page.html
    assert 'data-ref="ev.enterprise_value.final"' in page.html
    assert "the IPO price of" in page.html
    assert "middle of the IPO range" not in page.html


def test_the_page_before_the_listing_shows_no_price(page: Page) -> None:
    assert page.market == "awaiting"
    assert "awaiting listing" in page.html
    assert 'id="market"' not in page.html
    assert "market.price" not in page.html
    assert "tag-market" not in page.html


def test_the_page_on_a_trading_day(trading_page: Page) -> None:
    html = trading_page.html
    assert trading_page.market == "trading"
    assert '<section class="panel" id="market"' in html
    assert html.index('id="market"') < html.index('id="value"')  # the market comes first
    assert "awaiting listing" not in html
    assert "market.day" in trading_page.charts
    # Wherever a market value appears, the page names its source and says what it is.
    panel = html[html.index('id="market"') : html.index('id="value"')]
    assert "TEST DATA, not a real quote · delayed, unofficial · last trade" in panel
    for ref in ("market.price", "market.vs_ipo", "market.mcap_out", "market.enterprise_value"):
        assert f'data-ref="{ref}"' in panel, ref
    card = re.search(r'<div popover id="src-market-price".*?</div>', html, re.S)
    assert card is not None
    assert "MARKET" in card.group()
    assert "$81.25" in card.group()
    assert "Nov 13, 2026, 16:00 EST" in card.group()
    assert "delayed, unofficial" in card.group()
    assert "https://finance.yahoo.com/quote/ANT/" in card.group()
    # A value computed from the quote shows the quote among its inputs, with its label.
    card = re.search(r'<div popover id="src-market-mcap-out".*?</div>', html, re.S)
    assert card is not None
    assert "tag-market" in card.group()


def test_source_unavailable_with_and_without_a_last_quote(facts: Facts) -> None:
    down = market.check(Fake(SourceError("HTTP 429")), "ANT", "Anthropic", None, TRADING_NOW)
    page = render_page(facts, release="test", market=down)
    assert page.market == "unavailable"
    assert "source unavailable" in page.html
    assert "no price is shown" in page.html
    assert 'id="market"' not in page.html
    good = snapshot_of("ant-trading-TEST.json")
    stale = market.check(
        Fake(SourceError("no answer")), "ANT", "Anthropic", good, TRADING_NOW + 900
    )
    page = render_page(facts, release="test", market=stale)
    assert "the source is unavailable: this is the last quote it gave" in page.html
    assert 'data-ref="market.price"' in page.html
    assert render_page(facts, release="test").market == "off"


def test_the_watcher_renders_again_only_when_something_changed() -> None:
    source = Fake(recorded("ant-awaiting.json"))
    seen: list[Snapshot] = []
    clock = iter(range(TRADING_NOW, TRADING_NOW + 100))
    watcher = Watcher(source, "ANT", "Anthropic", seen.append, clock=lambda: next(clock))
    assert watcher.snapshot.state == "awaiting"  # the first answer is read before the first page
    asyncio.run(watcher.step())
    assert seen == []  # same answer: nothing to do
    source.answer = recorded("ant-trading-TEST.json")
    asyncio.run(watcher.step())
    assert [s.state for s in seen] == ["trading"]
    asyncio.run(watcher.step())
    assert len(seen) == 1
    source.answer = SourceError("HTTP 503")
    asyncio.run(watcher.step())
    assert [s.state for s in seen] == ["trading", "unavailable"]
    assert seen[-1].quote == seen[0].quote
    assert source.asked == 5
    # While the source fails, the questions space out, up to half an hour.
    waits = [watcher.wait]
    for _ in range(4):
        asyncio.run(watcher.step())
        waits.append(watcher.wait)
    assert waits == [300, 600, 1200, 1800, 1800]
    source.answer = recorded("ant-trading-TEST.json")
    asyncio.run(watcher.step())
    assert watcher.wait in {120, 1800}  # trading or closed, depending on the hour


def test_the_service_follows_the_market_and_survives_a_bad_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings("127.0.0.1", 8000, FACTS_DIR, "test", "info")
    source = Fake(recorded("ant-awaiting.json"))
    app = create_app(settings, source)
    with TestClient(app) as client:
        first = client.get("/")
        assert "awaiting listing" in first.text
        assert client.get("/health").json()["market"] == {
            "state": "awaiting",
            "source": "Fake source",
            "checked": client.get("/health").json()["market"]["checked"],
            "quote_time": None,
        }
        watcher = app.state.watcher
        assert isinstance(watcher, Watcher)
        source.answer = recorded("ant-trading-TEST.json")
        asyncio.run(watcher.step())
        second = client.get("/")
        assert second.headers["etag"] != first.headers["etag"]
        assert 'id="market"' in second.text
        assert client.get("/health").json()["market"]["quote_time"] == "2026-11-13T21:00:01+00:00"

        # A rendering that fails leaves the page that was being served.
        import ipo_monitor.web as web

        def broken(*args: Any, **kwargs: Any) -> Page:
            raise RuntimeError("boom")

        monkeypatch.setattr(web, "render_page", broken)
        source.answer = SourceError("no answer")
        asyncio.run(watcher.step())
        third = client.get("/")
        assert third.status_code == 200
        assert third.headers["etag"] == second.headers["etag"]


def test_sources_by_name() -> None:
    assert market.source_from("off") is None
    assert isinstance(market.source_from("yahoo"), YahooChart)
    assert isinstance(market.source_from("file:somewhere.json"), RecordedAnswer)
    with pytest.raises(ValueError, match="unknown market source"):
        market.source_from("guess")
    with pytest.raises(SourceError):
        RecordedAnswer(MARKET / "missing.json").fetch("ANT")
    assert YahooChart().page("ANT") == "https://finance.yahoo.com/quote/ANT/"
    quote = Quote("ANT", "Anthropic, PBC", "NasdaqGS", 81.25, 1794603601, "EST", -18000)
    assert quote.when(1794580200) == "Nov 13, 2026, 9:30 EST"
