"""The scanner's page: today's signals, the list, the track record. Every value opens its card.

Cards: MARKET for a close read from the source, CALC for an indicator (formula and sessions),
AI for a signal (level, confidence, reasons and the sources each reason cites).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from markupsafe import Markup

from ipo_monitor import __version__
from ipo_monitor.render import LOOP0_URL, REPOSITORY_URL, _environment, asset_version
from ipo_monitor.scan.board import TORONTO, Board, Stock
from ipo_monitor.scan.indicators import Indicator, compute, show
from ipo_monitor.scan.signals import LEVELS, Signal, fill
from ipo_monitor.scan.track import HORIZONS, Outcome

SITE = {
    "name": "antipo.watch",
    "url": "https://antipo.watch/",
    "title": "antipo.watch: AI trading signals on the most traded Canadian stocks",
    "description": (
        "Each trading day after the close, an AI (Claude) writes a signal for the 25 most traded "
        "stocks of the S&P/TSX 60, every reason tied to a figure or a source, every past signal "
        "scored. Unofficial. Not investment advice."
    ),
    "image_alt": "antipo.watch: AI trading signals, every reason sourced. Not investment advice.",
}
STRONGEST = 6  # signals on the first screen

BUTTON = Markup(
    '<button type="button" class="n n-{kind}{tone}" popovertarget="{target}">'
    '{text}<span class="vh"> ({kind}, show source)</span></button>'
)


def _slug(*parts: str) -> str:
    return "c-" + re.sub(r"[^a-z0-9]+", "-", "-".join(parts).lower()).strip("-")


@dataclass
class Card:
    slug: str
    label: str  # MARKET, CALC, AI
    title: str
    value: str
    period: str = ""
    formula: str = ""
    lines: list[tuple[str, str]] = field(default_factory=list)
    note: str = ""
    url: str = ""
    link_text: str = ""
    signal: Signal | None = None
    stock: Stock | None = None


class Cards:
    """The cards the page uses, registered as values are drawn."""

    def __init__(self, session: str | None = None) -> None:
        self.cards: dict[str, Card] = {}
        self.session = session  # the session of the signals shown

    def signal_cards(self) -> list[Card]:
        return [c for c in self.cards.values() if c.signal is not None]

    def plain_cards(self) -> list[Card]:
        return [c for c in self.cards.values() if c.signal is None]

    def button(self, card: Card, text: str, tone: str = "") -> Markup:
        self.cards.setdefault(card.slug, card)
        return BUTTON.format(kind=card.label.lower(), tone=tone, target=card.slug, text=text)

    def indicator(self, stock: Stock, ind: Indicator, *, toned: bool = False) -> Markup:
        series = stock.series
        if ind.key == "close" and series is not None:
            card = Card(
                _slug(stock.symbol, ind.key, ind.last),
                "MARKET",
                f"{stock.symbol} · close",
                ind.shown,
                period=f"session of {day(ind.last)}",
                lines=[
                    ("source", f"{series.source}, delayed, unofficial"),
                    ("symbol at the source", series.source_symbol),
                    ("exchange", series.exchange),
                    ("read", stamp(series.read_at)),
                ],
                url=series.page,
                link_text="Price history at the source",
            )
        else:
            sessions = (
                f"{ind.sessions} sessions, {day(ind.first)} to {day(ind.last)}"
                if ind.sessions > 1
                else f"session of {day(ind.last)}"
            )
            card = Card(
                _slug(stock.symbol, ind.key, ind.last),
                "CALC",
                f"{stock.symbol} · {ind.title}",
                ind.shown,
                period=f"as of {day(ind.last)}",
                formula=ind.formula,
                lines=[("sessions used", sessions)]
                + (
                    [("from", f"daily bars, {series.source}, delayed, unofficial")]
                    if series
                    else []
                ),
                url=series.page if series else "",
                link_text="Price history at the source" if series else "",
            )
        tone = ""
        if toned and ind.unit == "percent" and round(ind.value, 1) != 0:
            tone = " up" if ind.value > 0 else " down"
        return self.button(card, ind.shown, tone)

    def signal(self, stock: Stock, text: str) -> Markup:
        signal = stock.signal
        if signal is None:
            return Markup('<span class="what">no signal</span>')
        card = Card(
            _slug(stock.symbol, "signal"),
            "AI",
            f"{stock.symbol} · {stock.candidate.name}",
            f"{signal.label}, {signal.confidence} confidence",
            signal=signal,
            stock=stock,
        )
        return self.button(card, text, f" lv lv-{signal.level}")

    def reason_parts(self, stock: Stock, text: str) -> Markup:
        out = []
        for words, ind in fill(text, self.at_signal(stock)):
            out.append(self.indicator(stock, ind) if ind is not None else Markup.escape(words))
        return Markup("").join(out)

    def at_signal(self, stock: Stock) -> dict[str, Indicator]:
        """The indicators as of the session the signal was written for."""
        series = stock.series
        if series is None or self.session is None:
            return stock.indicators
        if series.last is not None and series.last.date == self.session:
            return stock.indicators
        return compute(series.upto(self.session), series.currency)


def day(iso: str, style: str = "short") -> str:
    moment = datetime.fromisoformat(iso)
    if style == "long":
        return f"{moment:%a, %b} {moment.day}, {moment.year}"
    return f"{moment:%b} {moment.day}"


def stamp(epoch: int) -> str:
    local = datetime.fromtimestamp(epoch, UTC).astimezone(TORONTO)
    return f"{local:%b} {local.day}, {local:%H:%M} ET"


def when(moment: datetime) -> str:
    local = moment.astimezone(TORONTO)
    return f"{local:%a, %b} {local.day}, {local:%H:%M} ET"


@dataclass(frozen=True)
class ScanPage:
    html: str
    etag: str
    stocks: int
    signals: int


def render_scan(board: Board, *, release: str = "dev") -> ScanPage:
    cards = Cards(board.current.session if board.current else None)
    env = _environment()
    template = env.get_template("scan.html.j2")
    current = board.current
    by_symbol = {s.symbol: s for s in board.stocks}

    def ind(stock: Stock, key: str, toned: bool = False) -> Markup:
        found = stock.indicators.get(key)
        if found is None:
            return Markup('<span class="what">–</span>')
        return cards.indicator(stock, found, toned=toned)

    def change(outcome: Outcome, horizon: int) -> Markup:
        value = outcome.after.get(horizon)
        if value is None:
            return Markup('<span class="what">to come</span>')
        tone = "up" if value > 0 else "down" if value < 0 else ""
        return Markup('<span class="chg {}">{}</span>').format(tone, show(value, "percent"))

    def average(value: float | None) -> str:
        return "–" if value is None else show(value, "percent")

    html = template.render(
        site=SITE,
        board=board,
        current=current,
        strongest=board.ranked_signals()[:STRONGEST],
        stocks=board.stocks,
        by_symbol=by_symbol,
        ind=ind,
        signal=cards.signal,
        reason=cards.reason_parts,
        change=change,
        average=average,
        money=show,
        horizons=HORIZONS,
        levels=LEVELS,
        day=day,
        when=when,
        cards=cards,
        version=__version__,
        release=release,
        asset_version=asset_version(),
        loop0_url=LOOP0_URL,
        repository_url=REPOSITORY_URL,
    )
    etag = '"' + hashlib.sha256(html.encode("utf-8")).hexdigest()[:20] + '"'
    signals = len(current.signals) if current else 0
    return ScanPage(html, etag, len(board.stocks), signals)
