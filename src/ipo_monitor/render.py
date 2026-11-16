"""Turns facts and calculations into the page.

Templates never contain a number. They call `n("some.id")`, which renders the
value as a button that opens its source: the passage it was copied from
(FILED, PRESS) or the formula and inputs behind it (CALC). An unknown id
raises, so a page with an unsourced number cannot be produced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

from ipo_monitor import __version__, fmt
from ipo_monitor.calc import PRICED, QUARTER_NAMES, QUARTERS, Calc, Term, compute
from ipo_monitor.charts import Mark
from ipo_monitor.edgar import SHOWN as FILINGS_SHOWN
from ipo_monitor.edgar import Watch, price_fact
from ipo_monitor.facts import Fact, Facts
from ipo_monitor.figures import Figures
from ipo_monitor.market import Snapshot
from ipo_monitor.market import facts as market_facts
from ipo_monitor.reconcile import assert_consistent

LOOP0_URL = "https://agmgd-on-loop0-22c0a8ea.fly.dev/"
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
    for name in ("app.css", "app.js"):
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
        "listed": filings.filings[:FILINGS_SHOWN] if filings else (),
        "day": fmt.iso_date,
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
