"""The market panel: what the source said, and nothing more."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ipo_monitor import market
from ipo_monitor.calc import Calc, compute
from ipo_monitor.config import Settings
from ipo_monitor.facts import Fact, Facts
from ipo_monitor.market import (
    Chain,
    NasdaqQuote,
    Quote,
    RecordedAnswer,
    Snapshot,
    SourceError,
    Watcher,
    YahooChart,
)
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

    def ask(self, symbol: str, company: str, now: int) -> Snapshot:
        self.asked += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return market.read_yahoo(
            self.answer,
            symbol=symbol,
            company=company,
            name=self.name,
            page=self.page(symbol),
            now=now,
        )


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
        assert fact.url == "https://example.org/test-data/ANT"
        assert "as given by TEST DATA, not a real quote for ANT (Anthropic, PBC" in fact.quote
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
    assert "https://example.org/test-data/ANT" in card.group()
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
    assert isinstance(market.source_from("nasdaq"), NasdaqQuote)
    both = market.source_from("auto")
    assert isinstance(both, Chain)
    assert both.name == "Nasdaq.com and Yahoo Finance"
    assert both.page("ANT") == "https://www.nasdaq.com/market-activity/stocks/ant"
    assert isinstance(market.source_from("file:somewhere.json"), RecordedAnswer)
    with pytest.raises(ValueError, match="unknown market source"):
        market.source_from("guess")
    with pytest.raises(SourceError):
        RecordedAnswer(MARKET / "missing.json").fetch("ANT")
    assert YahooChart().page("ANT") == "https://finance.yahoo.com/quote/ANT/"
    quote = Quote("ANT", "Anthropic, PBC", "NasdaqGS", 81.25, 1794603601, "EST", -18000)
    assert quote.when(1794580200) == "Nov 13, 2026, 9:30 EST"


def test_new_york_time_through_the_year() -> None:
    assert market.eastern(2026, 11, 16) == (-18000, "EST")
    assert market.eastern(2026, 7, 1) == (-14400, "EDT")
    assert market.eastern(2026, 3, 7) == (-18000, "EST")  # the day before the clocks move
    assert market.eastern(2026, 3, 8) == (-14400, "EDT")  # second Sunday of March
    assert market.eastern(2026, 10, 31) == (-14400, "EDT")
    assert market.eastern(2026, 11, 1) == (-18000, "EST")  # first Sunday of November
    assert market.eastern(2027, 3, 14) == (-14400, "EDT")


def test_nasdaq_before_the_listing_and_for_a_listed_symbol() -> None:
    unknown = snapshot_of("nasdaq-ant-unknown.json")  # recorded on 2026-11-16
    assert (unknown.state, unknown.quote) == ("awaiting", None)
    assert unknown.detail == "TEST DATA, not a real quote does not list ANT yet"

    source = RecordedAnswer(MARKET / "nasdaq-aapl-premarket.json")  # a real answer, before the open
    snapshot = market.check(source, "AAPL", "Apple", None, TRADING_NOW)
    quote = snapshot.quote
    assert quote is not None
    assert snapshot.state == "closed"  # the answer says: Pre-Market
    assert (quote.name, quote.exchange) == ("Apple Inc. Common Stock", "NASDAQ-GS")
    assert quote.price == 357.70
    assert quote.when() == "Nov 16, 2026, 8:20 EST"
    assert quote.time == 1794835200  # 13:20 UTC
    assert (quote.day_low, quote.day_high) == (None, None)  # "NA" before the open
    assert quote.volume == 2981347
    assert len(quote.points) == 44
    assert quote.points[0][0] == 1794819600  # 4:00 in New York is 9:00 UTC
    assert quote.when(quote.points[0][0]) == "Nov 16, 2026, 4:00 EST"
    assert market.check(source, "AAPL", "Anthropic", None, TRADING_NOW).state == "unavailable"


def test_nasdaq_with_the_market_open() -> None:
    source = RecordedAnswer(MARKET / "nasdaq-aapl-open.json")  # a real answer, 9:34 in New York
    now = 1794839695  # the moment it was recorded
    snapshot = market.check(source, "AAPL", "Apple", None, now)
    quote = snapshot.quote
    assert quote is not None
    assert snapshot.state == "trading"  # the answer says: Open
    assert quote.price == 355.9601  # the service gives more than two decimals at times
    assert quote.when() == "Nov 16, 2026, 9:34 EST"
    assert (quote.day_low, quote.day_high) == (353.79, 357.10)
    assert quote.volume == 4970164
    assert quote.previous_close is None  # not read from this service
    assert len(quote.points) == 335
    assert quote.when(quote.points[0][0]) == "Nov 16, 2026, 4:00 EST"  # early trading included
    # The range counts regular hours only: early trades went higher than its top.
    assert max(value for _, value in quote.points) > 357.10
    facts = {fact.id: fact for fact in market.facts(snapshot)}
    assert facts["market.day_high"].title == "Highest price in regular trading hours"
    assert facts["market.price"].as_filed == "$355.96"


def test_the_line_of_the_day_ends_at_the_last_trade() -> None:
    source = RecordedAnswer(MARKET / "nasdaq-aapl-open.json")
    quote = market.check(source, "AAPL", "Apple", None, 1794839695).quote
    assert quote is not None
    # The series has a point for the minute of the last trade, at another price.
    assert quote.points[-1] == (quote.time, 355.57)
    assert quote.line[-1] == (quote.time, quote.price)
    assert quote.line[:-1] == quote.points[:-1]
    # A series that runs past the last trade is cut there; a trade with no series gives no line.
    late = dataclasses.replace(quote, time=quote.points[100][0] + 30)
    assert len(late.line) == 102
    assert late.line[-1] == (late.time, quote.price)
    assert late.line[-2] == quote.points[100]
    assert dataclasses.replace(quote, points=()).line == ()
    assert dataclasses.replace(quote, time=quote.points[0][0]).line == ()


def test_no_previous_close_on_a_first_trading_day() -> None:
    answer = recorded("aapl-listed.json")
    meta = answer["chart"]["result"][0]["meta"]
    assert meta["previousClose"] == 354.88

    def previous(first_trade: int | None) -> float | None:
        meta["firstTradeDate"] = first_trade
        quote = market.read_yahoo(
            answer, symbol="AAPL", company="Apple", name="Yahoo Finance", page="p", now=TRADING_NOW
        ).quote
        assert quote is not None
        return quote.previous_close

    traded = meta["regularMarketTime"]  # 16:00 in New York
    assert previous(traded - 86400) == 354.88  # first traded the day before
    assert previous(traded - 6 * 3600) is None  # first traded that morning
    assert previous(None) is None


def nasdaq(**primary: Any) -> dict[str, Any]:
    answer = recorded("nasdaq-aapl-premarket.json")
    answer["info"]["data"].update(symbol="ANT", companyName="Anthropic, PBC Class A Common Stock")
    answer["info"]["data"]["primaryData"].update(primary)
    return answer


def read_ant(answer: dict[str, Any]) -> Snapshot:
    return market.read_nasdaq(
        answer, symbol="ANT", company="Anthropic", name="Nasdaq.com", page="p", now=TRADING_NOW
    )


def test_nasdaq_answers_that_are_not_a_price() -> None:
    # Listed, no trade yet: the morning of the first day.
    for empty in ("", "N/A"):
        waiting = read_ant(nasdaq(lastSalePrice=empty))
        assert waiting.state == "awaiting"
        assert waiting.detail == (
            "Nasdaq.com lists ANT as Anthropic, PBC Class A Common Stock, with no trade yet"
        )
    for change, problem in (
        ({"lastSalePrice": "357.70"}, "price not in dollars"),
        ({"lastSalePrice": "$0.00"}, "price not in dollars"),
        ({"lastTradeTimestamp": "a moment ago"}, "time of the trade not understood"),
    ):
        with pytest.raises(SourceError, match=problem):
            read_ant(nasdaq(**change))
    with pytest.raises(SourceError, match="unexpected answer"):
        read_ant({"info": {"data": None, "status": {"rCode": 500}}})
    with pytest.raises(SourceError, match="unexpected answer"):
        read_ant({"chart": {}})

    # During the session the answer carries a range, and the state follows the market status.
    session = nasdaq(lastSalePrice="$81.25", lastTradeTimestamp="Nov 19, 2026 2:05 PM ET")
    session["info"]["data"]["marketStatus"] = "Open"
    session["info"]["data"]["keyStats"]["dayrange"]["value"] = "79.50 - 84.10"
    session["chart"] = None  # the line of the day is optional
    snapshot = read_ant(session)
    assert snapshot.state == "trading"
    assert snapshot.quote is not None
    assert snapshot.quote.when() == "Nov 19, 2026, 14:05 EST"
    assert (snapshot.quote.day_low, snapshot.quote.day_high) == (79.5, 84.1)
    assert snapshot.quote.points == ()


def test_the_second_source_answers_when_the_first_fails() -> None:
    down, good = Fake(SourceError("HTTP 429")), Fake(recorded("ant-trading-TEST.json"))
    snapshot = market.check(Chain([down, good]), "ANT", "Anthropic", None, TRADING_NOW)
    assert snapshot.state == "trading"
    assert snapshot.source == "Fake source"
    assert (down.asked, good.asked) == (1, 1)
    # An answer of the first source is final, even "not listed yet": the second is not asked.
    first = Fake({"chart": {"result": None, "error": {"code": "Not Found"}}})
    snapshot = market.check(Chain([first, good]), "ANT", "Anthropic", None, TRADING_NOW)
    assert snapshot.state == "awaiting"
    assert good.asked == 1
    # Both down: no price, and the page says which sources were asked.
    both = Chain([Fake(SourceError("HTTP 403")), Fake(SourceError("HTTP 429"))])
    snapshot = market.check(both, "ANT", "Anthropic", None, TRADING_NOW)
    assert (snapshot.state, snapshot.quote) == ("unavailable", None)
    assert snapshot.source == "Fake source and Fake source"
    assert snapshot.detail == "HTTP 403, HTTP 429"
