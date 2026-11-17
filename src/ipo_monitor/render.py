"""Turns facts and calculations into the page.

Templates never contain a number. They call `n("some.id")`, which renders the
value as a button that opens its source: the passage it was copied from
(FILED, PRESS) or the formula and inputs behind it (CALC). An unknown id
raises, so a page with an unsourced number cannot be produced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from importlib import resources
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

from ipo_monitor import __version__, fmt
from ipo_monitor.calc import PRICED, QUARTER_NAMES, QUARTERS, Calc, Term, compute
from ipo_monitor.charts import Mark
from ipo_monitor.edgar import Watch, batches, price_fact
from ipo_monitor.facts import Fact, Facts
from ipo_monitor.figures import Figures, unlock_label, unlock_steps
from ipo_monitor.market import Snapshot, eastern_at
from ipo_monitor.market import facts as market_facts
from ipo_monitor.reconcile import assert_consistent

LOOP0_URL = "https://agmgd-on-loop0-22c0a8ea.fly.dev/"
# The name and the words that present the page: the tab, the share card on X, the search result.
SITE = {
    "name": "Anthropic IPO Watch",
    "url": "https://antipo.watch/",
    "title": "Anthropic IPO Watch: Anthropic's IPO in numbers you can trace",
    "description": (
        "An unofficial dashboard on Anthropic's IPO: the value at the IPO price, the deal, the "
        "lock-ups, the filings. Every figure opens the SEC filing it came from. "
        "Not investment advice."
    ),
    "image_alt": (
        "Anthropic IPO Watch, antipo.watch: Anthropic's IPO in numbers you can trace. "
        "Unofficial, not affiliated with Anthropic, not investment advice."
    ),
}
SHARE_IMAGE = ("og.png", 1200, 630)  # deploy/share/og.svg, drawn by deploy/share/make_og.py
REPOSITORY_URL = "https://github.com/sonixz/monitor-anthropic-ipo"

# Markup.format escapes every argument.
BUTTON = Markup(
    '<button type="button" class="n n-{kind}{tone}" popovertarget="{target}" data-ref="{ref}">'
    '{text}<span class="vh"> ({kind}, show source)</span></button>'
)

DEFAULT_STYLE = {
    "USD": "b",
    "USD/share": "p",
    "shares": "b",
    "percent": "plain",
    "ratio": "x",
    "years": "years",
    "count": "count",
    "date": "long",
    "text": "text",
}


def slug(ref: str) -> str:
    return "src-" + re.sub(r"[^a-z0-9]+", "-", ref.lower()).strip("-")


def display(value: float | str, unit: str, style: str = "", *, plus: bool = False) -> str:
    """Format a value for the page."""
    style = style or DEFAULT_STYLE[unit]
    if isinstance(value, str):
        return fmt.iso_date(value, style) if unit == "date" else value
    if unit == "USD":
        return fmt.money(value, style, plus=plus)
    if unit == "USD/share":
        return fmt.money(value, "p")
    if unit == "shares":
        return fmt.shares(value, style)
    if unit == "percent":
        return fmt.percent(value, style)
    if unit in {"ratio", "years"}:
        return fmt.ratio(value, style)
    return fmt.count(value)


def precise(value: float | str, unit: str) -> str:
    """The same value with all the precision a reader may want to check."""
    if isinstance(value, str):
        return display(value, unit)
    if unit == "USD":
        return fmt.money(value, "p") if abs(value) < 1e6 else fmt.money(value, "b1")
    if unit == "shares":
        return fmt.shares(value, "full")
    if unit == "percent":
        return fmt.percent(value, "one")
    if unit in {"ratio", "years"}:
        return f"{value:,.2f}"
    return display(value, unit)


@dataclass(frozen=True)
class TermView:
    name: str
    value: str
    label: str
    where: str


@dataclass(frozen=True)
class Source:
    """Everything a source card shows."""

    slug: str
    ref: str
    label: str
    title: str
    value: str
    period: str | None = None
    where: str | None = None
    quote: str | None = None
    context: str | None = None
    url: str | None = None
    link_text: str | None = None
    formula: str | None = None
    terms: tuple[TermView, ...] = ()
    note: str | None = None


@dataclass
class Numbers:
    """The `n(...)` function of the templates. Remembers what it rendered."""

    facts: Facts
    calcs: dict[str, Calc]
    used: dict[str, None] = field(default_factory=dict)

    def _lookup(self, ref: str) -> tuple[str, float | str, str]:
        if ref in self.calcs:
            calc = self.calcs[ref]
            return "CALC", calc.value, calc.unit
        fact = self.facts.get(ref)
        return fact.label, fact.value, fact.unit

    def __call__(
        self, ref: str, style: str = "", *, plus: bool = False, mag: bool = False
    ) -> Markup:
        label, value, unit = self._lookup(ref)
        if mag and not isinstance(value, str):
            value = abs(value)
        self.used[ref] = None
        text = display(value, unit, style, plus=plus)
        kind = label.lower()
        tone = ""
        if plus and not isinstance(value, str) and value != 0:
            tone = " up" if value > 0 else " down"
        if isinstance(value, str) and len(text) > 16:
            tone = " long"  # words, not a figure: they may wrap
        return BUTTON.format(kind=kind, tone=tone, target=slug(ref), ref=ref, text=text)

    def text(self, ref: str, style: str = "") -> str:
        """A value as plain text, for the description of a chart mark."""
        _, value, unit = self._lookup(ref)
        self.used[ref] = None
        return display(value, unit, style)

    def mark(
        self,
        ref: str,
        label: str,
        style: str = "",
        *,
        plus: bool = False,
        mag: bool = False,
        divide: float = 1.0,
    ) -> Mark:
        """A value to draw on a chart. Its source card is rendered like any other."""
        kind, value, unit = self._lookup(ref)
        if isinstance(value, str):
            raise TypeError(f"{ref} is not numeric")
        if mag:
            value = abs(value)
        self.used[ref] = None
        return Mark(
            ref=ref,
            src=slug(ref),
            label=label,
            value=value / divide,
            text=display(value, unit, style, plus=plus),
            kind=kind.lower(),
        )

    def raw(self, ref: str) -> float:
        """A value for drawing only (bar widths). Never printed."""
        _, value, _ = self._lookup(ref)
        if isinstance(value, str):
            raise TypeError(f"{ref} is not numeric")
        return value

    def share(self, ref: str, of: str) -> float:
        """Width of a bar, in percent of another value."""
        return round(min(100.0, max(0.0, abs(self.raw(ref)) / abs(self.raw(of)) * 100)), 2)

    # -- source cards -------------------------------------------------------

    def _term(self, term: Term) -> TermView:
        value = precise(term.value, term.unit)
        if term.ref is None:
            return TermView(term.name, value, "", "")
        if term.ref in self.calcs:
            return TermView(term.name, value, "CALC", "our arithmetic")
        fact = self.facts.get(term.ref)
        return TermView(term.name, value, fact.label, self._short_where(fact))

    def _short_where(self, fact: Fact) -> str:
        if fact.label in {"PRESS", "MARKET"}:
            return fact.outlet or fact.label.lower()
        document = self.facts.document_of(fact.id)
        form = document.form if document else "filing"
        return f"{form}, {fmt.page_ref(fact.page)}"

    def _fact_source(self, fact: Fact) -> Source:
        value = fact.as_filed + (f" ({fact.scale})" if fact.scale else "")
        if fact.label == "MARKET":
            where = f"{fact.outlet} · delayed, unofficial · read {fact.accessed}"
            link_text = "Open the quote at the source"
            url = fact.url
        elif fact.label == "PRESS":
            where = f"{fact.outlet}, published {fmt.iso_date(fact.published or '')}"
            if fact.accessed:
                where += f" · read {fmt.iso_date(fact.accessed)}"
            link_text = "Open the article"
            url = fact.url
        else:
            document = self.facts.document_of(fact.id)
            if document is None:
                raise ValueError(f"filed fact without a document: {fact.id}")
            parts = [
                f"{document.company}, {document.title}",
                f"filed {fmt.iso_date(document.filed)}",
                fmt.page_ref(fact.page),
            ]
            if fact.section:
                parts.append(fact.section)
            where = " · ".join(parts)
            link_text = "Open the filing on sec.gov"
            url = document.url
        return Source(
            slug=slug(fact.id),
            ref=fact.id,
            label=fact.label,
            title=fact.title,
            value=value,
            period=fact.period,
            where=where,
            quote=fact.quote,
            context=fact.context,
            url=url,
            link_text=link_text,
        )

    def _calc_source(self, calc: Calc) -> Source:
        return Source(
            slug=slug(calc.id),
            ref=calc.id,
            label="CALC",
            title=calc.title,
            value=precise(calc.value, calc.unit),
            formula=calc.formula,
            terms=tuple(self._term(t) for t in calc.terms),
            note=calc.note,
        )

    def sources(self) -> list[Source]:
        """One card per number rendered so far."""
        cards = []
        for ref in self.used:
            if ref in self.calcs:
                cards.append(self._calc_source(self.calcs[ref]))
            else:
                cards.append(self._fact_source(self.facts.get(ref)))
        return cards


@dataclass(frozen=True)
class Page:
    """The rendered dashboard and what went into it."""

    html: str
    facts: int
    calcs: int
    checks: int
    numbers: int
    filed: str
    charts: dict[str, tuple[Mark, ...]]
    market: str  # off, awaiting, trading, closed or unavailable
    filings: str = "off"  # off, ok or unavailable


@dataclass(frozen=True)
class Moment:
    """One line of the timeline of the IPO."""

    what: str  # in words; may hold a form name, shown as a label
    state: str  # done, next or later
    day: str = ""  # an ISO date read from EDGAR's list, or
    ref: str = ""  # the id of a fact that holds the date (or what happens)
    url: str = ""
    count: int = 1  # filings of the same form in a row
    last_day: str = ""  # the date of the last of them


def timeline(watch: Watch | None, priced: bool, trading: bool) -> list[Moment]:
    """The IPO from the first filing to the first lock-up step, in order.

    Filings come from EDGAR's list when the watch has one, filings of one form in a row on one
    line; otherwise from the document the page reads. Then the dates the press reported, and the
    first step at which existing shares may be sold, as the filing words it.
    """
    moments: list[Moment] = []
    filed = list(reversed(watch.filings)) if watch and watch.filings else []
    for filing in filed:
        last = moments[-1] if moments else None
        if last is not None and last.what == filing.name:
            moments[-1] = Moment(
                last.what,
                "done",
                last.day,
                url=last.url,
                count=last.count + 1,
                last_day=filing.filed,
            )
        else:
            moments.append(Moment(filing.name, "done", filing.filed, url=filing.url))
    if not filed:
        moments.append(Moment("Form S-1/A, Amendment No. 2", "done", ref="doc.filed_date"))
    moments.append(Moment("priced", "done" if priced else "next", ref="press.cnbc.pricing_date"))
    moments.append(
        Moment(
            "first trade",
            "done" if trading else ("next" if priced else "later"),
            ref="press.cnbc.trading_date",
        )
    )
    moments.append(Moment("first existing shares may be sold", "later", ref="unlock.01"))
    return moments


def clock(moment: int) -> str:
    """A time of a check, in New York: '19:15 ET'."""
    offset, _ = eastern_at(moment)
    local = datetime.fromtimestamp(moment, timezone(timedelta(seconds=offset)))
    return f"{local.hour}:{local:%M} ET"


def phase(priced: bool, market: Snapshot | None) -> str:
    """Where the IPO stands, in a few words, from what the page has seen."""
    if market is not None and market.quote is not None:
        return "TRADING" if market.state == "trading" else "LISTED · MARKET CLOSED"
    if priced:
        return "PRICED · WAITING FOR THE FIRST TRADE"
    return "WAITING FOR THE IPO"


def _environment() -> Environment:
    return Environment(
        loader=PackageLoader("ipo_monitor", "templates"),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def asset_version() -> str:
    """Changes when a static file changes, so browsers refetch it."""
    import hashlib

    digest = hashlib.sha256()
    static = resources.files("ipo_monitor") / "static"
    for name in ("app.css", "app.js", SHARE_IMAGE[0]):
        digest.update((static / name).read_bytes())
    return digest.hexdigest()[:10]


def render_page(
    facts: Facts,
    *,
    release: str = "dev",
    market: Snapshot | None = None,
    filings: Watch | None = None,
) -> Page:
    """Check the facts, compute, and render the dashboard.

    `market` is the last answer of the market source and `filings` the last answer of the SEC's
    filing index; None when that source is not connected.
    """
    checks = assert_consistent(facts)
    if filings is not None and filings.price is not None:
        # The price on the cover of the final prospectus replaces one recorded from the press.
        fact, final = price_fact(filings.price, facts.documents["s1a2"].company)
        facts = facts.plus([fact], final, replacing=True)
    if market is not None:
        facts = facts.plus(market_facts(market))
    calcs = compute(facts)
    numbers = Numbers(facts, calcs)
    priced = PRICED in facts
    at = "final" if priced else "mid"
    price_ref = PRICED if priced else "offering.price_mid"
    quote = market.quote if market else None
    figures = Figures(numbers, at, price_ref, quote)
    document = facts.documents["s1a2"]
    context: dict[str, Any] = {
        "n": numbers,
        "chart": figures,
        "filings": filings,
        "newer": filings.newer_than(document.accession) if filings else None,
        "listed": batches(filings.filings) if filings else (),
        "day": fmt.iso_date,
        "clock": clock,
        "phase": phase(priced, market),
        "pricing_day": facts.text("press.cnbc.pricing_date"),
        "moments": timeline(filings, priced, quote is not None),
        "unlock": [
            (key, unlock_label(facts.text(key + ".when"))) for key in unlock_steps(facts.ids())
        ],
        "banks": facts.text("underwriting.banks").split("; "),
        "market": market,
        "quote": quote,
        "priced": priced,
        "at": at,
        "price_ref": price_ref,
        "document": document,
        "quarters": [(q, QUARTER_NAMES[q]) for q in QUARTERS],
        "checks": len(checks),
        "version": __version__,
        "release": release,
        "asset_version": asset_version(),
        "loop0_url": LOOP0_URL,
        "site": SITE,
        "share": {
            "image": f"{SITE['url']}static/{SHARE_IMAGE[0]}?v={asset_version()}",
            "width": SHARE_IMAGE[1],
            "height": SHARE_IMAGE[2],
        },
        "repository_url": REPOSITORY_URL,
    }
    html = _environment().get_template("index.html.j2").render(context)
    return Page(
        html=html,
        facts=len(facts),
        calcs=len(calcs),
        checks=len(checks),
        numbers=len(numbers.used),
        filed=document.filed,
        charts=figures.marks(),
        market=market.state if market else "off",
        filings=filings.state if filings else "off",
    )
