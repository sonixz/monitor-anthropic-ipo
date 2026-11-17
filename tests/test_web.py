"""The page and the service around it."""

from __future__ import annotations

import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ipo_monitor.calc import Calc
from ipo_monitor.config import ConfigError, Settings
from ipo_monitor.facts import Facts, MissingFactError
from ipo_monitor.reconcile import ReconciliationError
from ipo_monitor.render import Numbers, Page
from ipo_monitor.web import create_app

from .conftest import FACTS_DIR

VOID = {"meta", "link", "br", "img", "input", "hr", "rect", "path", "line", "circle"}


class Audit(HTMLParser):
    """Collects the visible text that is not a sourced number, a label or a source card."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[bool] = []  # True = this element and its children are exempt
        self.loose_text: list[str] = []
        self.buttons: list[dict[str, str | None]] = []
        self.popovers: set[str] = set()
        self.links: list[str] = []
        self.lang: str | None = None
        self.path: list[str] = []
        self.chart_sources: list[str] = []
        self.ticks: list[tuple[str, ...]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "a" and a.get("href"):
            self.links.append(str(a["href"]))
        if "popover" in a and a.get("id"):
            self.popovers.add(str(a["id"]))
        if tag == "button" and "n" in classes:
            self.buttons.append(a)
        if "data-src" in a:
            self.chart_sources.append(str(a["data-src"]))
        if "data-tick" in a:
            self.ticks.append(tuple(self.path))
        exempt = (
            (tag == "button" and "n" in classes)
            or "data-label" in a
            or "data-ref" in a  # a value drawn on a chart
            or "data-tick" in a  # a scale mark of a chart axis
            or "popover" in a
            or tag in {"script", "style", "head", "kbd"}
        )
        if tag not in VOID:
            self.path.append(f"{tag}.{'.'.join(classes)}" if classes else tag)
        if tag not in VOID:
            self.stack.append(exempt or (bool(self.stack) and self.stack[-1]))

    def handle_endtag(self, tag: str) -> None:
        if tag not in VOID and self.stack:
            self.stack.pop()
            self.path.pop()

    def handle_data(self, data: str) -> None:
        if not (self.stack and self.stack[-1]) and data.strip():
            self.loose_text.append(data.strip())


@pytest.fixture(scope="module")
def audit(page: Page) -> Audit:
    parser = Audit()
    parser.feed(page.html)
    return parser


def test_no_number_without_a_source(audit: Audit) -> None:
    """Outside sourced numbers and period labels, the page shows no digit at all."""
    offenders = [text for text in audit.loose_text if re.search(r"\d", text)]
    assert offenders == []


def test_chart_marks_open_a_source_card_and_ticks_stay_on_axes(audit: Audit) -> None:
    assert len(audit.chart_sources) >= 60
    for source in audit.chart_sources:
        assert source in audit.popovers, source
    # A digit without a source is accepted in one place only: the axis of a chart.
    assert len(audit.ticks) >= 20
    for path in audit.ticks:
        assert path[-2:] == ("svg.chart-svg", "g.axis"), path


def test_every_number_opens_a_source_card(audit: Audit, page: Page) -> None:
    assert len(audit.buttons) >= 100
    for button in audit.buttons:
        assert button.get("popovertarget") in audit.popovers, button.get("data-ref")
        assert button.get("type") == "button"
    assert page.numbers >= 100


def test_source_cards_show_the_passage_or_the_arithmetic(page: Page) -> None:
    cards = re.findall(
        r'<div popover id="(src-[^"]+)" class="src src-(\w+)">(.*?)(?=<div popover id=|</body>)',
        page.html,
        re.S,
    )
    assert len(cards) == page.numbers
    kinds = {kind for _, kind, _ in cards}
    assert kinds == {"filed", "calc", "press"}
    for card_id, kind, body in cards:
        if kind == "filed":
            assert "<blockquote>" in body, card_id
            assert "https://www.sec.gov/Archives/edgar/data/2130357/" in body, card_id
            # A value of an earlier filing (in HISTORY) opens that filing; the others the latest.
            earlier = card_id.startswith("src-s1a2-")
            assert ("Amendment No. 2" if earlier else "Amendment No. 3") in body, card_id
            assert "p. " in body or "unnumbered" in body, card_id
        elif kind == "calc":
            assert 'class="src-formula"' in body, card_id
            assert 'class="src-terms"' in body, card_id
        else:
            assert "<blockquote>" in body, card_id
            assert "Open the article" in body, card_id


def test_required_notices_are_on_the_page(audit: Audit, page: Page) -> None:
    assert audit.lang == "en"
    assert "https://agmgd-on-loop0-22c0a8ea.fly.dev/" in audit.links
    assert "Built with the Loop0 Method" in page.html
    text = " ".join(audit.loose_text)
    assert "Unofficial" in text
    assert "not affiliated with Anthropic" in text
    assert "not investment advice" in text
    assert "awaiting listing" in text
    for panel in ("value", "ev", "contracts", "growth", "losses"):
        assert f'<section class="panel" id="{panel}"' in page.html


def test_an_unknown_number_cannot_be_rendered(facts: Facts, calcs: dict[str, Calc]) -> None:
    with pytest.raises(MissingFactError):
        Numbers(facts, calcs)("revenue.made.up")


def test_dashboard_response(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    policy = response.headers["content-security-policy"]
    assert "default-src 'none'" in policy
    assert "unsafe-inline" not in policy
    assert "connect-src 'self'" in policy  # the page may ask us, and only us, for newer figures
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "style=" not in response.text  # the policy forbids inline styles
    again = client.get("/", headers={"If-None-Match": response.headers["etag"]})
    assert again.status_code == 304
    assert client.head("/").status_code == 200
    assert client.get("/nothing-here").status_code == 404


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["release"] == "test"
    assert body["data"]["source_filed"] == "2026-11-17"
    assert body["data"]["checks_passed"] >= 120
    assert body["market"]["state"] == "awaiting"
    assert body["market"]["quote_time"] is None
    assert response.headers["cache-control"] == "no-store"


def test_static_files(client: TestClient) -> None:
    for name, kind in (("app.css", "text/css"), ("app.js", "javascript"), ("favicon.svg", "svg")):
        response = client.get(f"/static/{name}")
        assert response.status_code == 200, name
        assert kind in response.headers["content-type"], name
        assert "immutable" in response.headers["cache-control"], name


def test_the_service_refuses_to_start_on_inconsistent_data(tmp_path: Path) -> None:
    broken = tmp_path / "facts"
    shutil.copytree(FACTS_DIR, broken)
    path = broken / "s1a3.json"
    data = json.loads(path.read_text("utf-8"))
    for fact in data["facts"]:
        if fact["id"] == "q.revenue.2026q3":
            fact["value"] += 1_000_000_000
    path.write_text(json.dumps(data), "utf-8")
    settings = Settings("127.0.0.1", 8000, broken, "test", "info")
    with pytest.raises(ReconciliationError):
        create_app(settings)


def test_configuration_is_checked(tmp_path: Path) -> None:
    good = {"IPO_FACTS_DIR": str(FACTS_DIR)}
    settings = Settings.from_env(good)
    assert (settings.host, settings.port, settings.release) == ("127.0.0.1", 8000, "dev")
    assert settings.market == "auto"
    bad = [
        ({"IPO_PORT": "http"}, "IPO_PORT"),
        ({"IPO_PORT": "70000"}, "IPO_PORT"),
        ({"IPO_FACTS_DIR": str(tmp_path / "missing")}, "IPO_FACTS_DIR"),
        ({"IPO_RELEASE": "not a release!"}, "IPO_RELEASE"),
        ({"IPO_LOG_LEVEL": "loud"}, "IPO_LOG_LEVEL"),
        ({"IPO_HOST": ""}, "IPO_HOST"),
        ({"IPO_MARKET": "bloomberg"}, "IPO_MARKET"),
    ]
    for override, name in bad:
        with pytest.raises(ConfigError, match=name):
            Settings.from_env({**good, **override})


def test_share_card_for_x(client: TestClient) -> None:
    """A link to the page shows a large card on X: every tag, absolute addresses, the image."""
    import re
    import struct

    html = client.get("/").text
    tags = dict(
        re.findall(r'<meta (?:property|name)="((?:og|twitter):[a-z:_]+)" content="([^"]*)"', html)
    )
    for name in (
        "og:type",
        "og:site_name",
        "og:title",
        "og:description",
        "og:url",
        "og:image",
        "og:image:width",
        "og:image:height",
        "og:image:alt",
        "twitter:card",
        "twitter:title",
        "twitter:description",
        "twitter:image",
        "twitter:image:alt",
    ):
        assert tags.get(name), name
    assert tags["twitter:card"] == "summary_large_image"
    assert tags["og:url"] == "https://antipo.watch/"
    assert '<link rel="canonical" href="https://antipo.watch/">' in html
    assert tags["og:image"].startswith("https://antipo.watch/static/og.png?v=")
    assert tags["twitter:image"] == tags["og:image"]
    assert "Anthropic IPO Watch" in tags["og:title"]
    assert len(tags["og:title"]) <= 70
    assert "Not investment advice" in tags["og:description"]
    assert (tags["og:image:width"], tags["og:image:height"]) == ("1200", "630")

    image = client.get("/static/og.png")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    body = image.content
    assert body[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(body) < 5_000_000
    assert struct.unpack(">II", body[16:24]) == (1200, 630)


def test_share_image_holds_no_figure() -> None:
    """The card's text has no digit: a price would be false once X has cached it."""
    import re
    from pathlib import Path

    svg = (Path(__file__).parents[1] / "deploy" / "share" / "og.svg").read_text("utf-8")
    words = " ".join(re.findall(r">([^<]+)<", svg))
    assert not re.search(r"\d", words), words
    assert "Unofficial" in words
    assert "not investment advice" in words
