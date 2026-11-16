"""The charts of the dashboard: which facts each one draws, and how.

The drawing itself is in `charts.py`. Everything here goes through
`Numbers.mark`, so a chart cannot show a value that has no source card.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from markupsafe import Markup

from ipo_monitor import charts
from ipo_monitor.calc import QUARTER_NAMES, QUARTERS
from ipo_monitor.charts import Chart, Mark, Range

if TYPE_CHECKING:
    from ipo_monitor.market import Quote
    from ipo_monitor.render import Numbers

BILLION = 1e9
YEARS = ("fy2023", "fy2024", "fy2025", "9m2026")
YEAR_NAMES = {"fy2023": "2023", "fy2024": "2024", "fy2025": "2025", "9m2026": "9 mo. 2026"}
DUE = ("2026", "2027", "2028", "2029", "2030", "thereafter")
DUE_NAMES = {**{year: year for year in DUE}, "thereafter": "later"}


def bridge(at: str) -> tuple[tuple[str, str], ...]:
    """The enterprise value bridge, in order: (id, what the step does to the running total)."""
    return (
        (f"value.equity_diluted.{at}", "total"),
        (f"ev.cash_after.{at}", "minus"),
        ("ev.option_proceeds", "minus"),
        ("debt.credit_facility_drawn", "plus"),
        (f"ev.enterprise_value.{at}", "total"),
    )


MILLION = 1e6
DEAL_PARTS = (
    ("offering.shares_company", "New shares sold by the company"),
    ("offering.shares_selling", "Shares sold by existing stockholders"),
    ("offering.greenshoe", "Underwriters' option to buy more"),
    ("offering.private_placement_shares_mid", "Private placement, at the assumed price"),
)
DEAL_SHORT = (
    ("offering.shares_company", "company", "new"),
    ("offering.shares_selling", "sellers", "sellers"),
    ("offering.greenshoe", "option", "option"),
    ("offering.private_placement_shares_mid", "placement", "placement"),
)
# What each group of lock-up steps counts from: words of the filing, and the chart's short name.
UNLOCK_EVENTS = (
    ("fiscal quarter ending September 30, 2027", "Q3"),
    ("fiscal quarter ending June 30, 2027", "Q2 27"),
    ("Q2 Earnings Release Date", "Q2 27"),
    ("fiscal quarter ending March 31, 2027", "Q1 27"),
    ("Q1 Earnings Release Date", "Q1 27"),
    ("fiscal year ending December 31, 2026", "FY26"),
    ("FY26 Earnings Release Date", "FY26"),
    ("date of this prospectus", "prospectus"),
)


def unlock_steps(ids: list[str]) -> list[str]:
    """The lock-up steps in the filing's order: unlock.01, unlock.02..."""
    return sorted(key for key in ids if re.fullmatch(r"unlock\.\d{2}", key))


def unlock_label(when: str) -> tuple[str, str]:
    """A short label for a step and the event it counts from, both read from its wording.

    "27th day after the FY26 Earnings Release Date" -> ("27", "FY26"). The day of a release is
    "R"; a step at "the earlier of" a release and a day after the prospectus is "R*".
    """
    event = next((name for words, name in UNLOCK_EVENTS if words in when), "")
    if not event:
        raise ValueError(f"lock-up step not understood: {when}")
    if when.startswith("The earlier of"):
        return "R*", event
    day = re.match(r"(\d+)(?:st|nd|rd|th) day after", when)
    if day:
        return day.group(1), event
    return ("1" if when.startswith("The first trading day") else "R"), event


def unlock_groups(labels: list[tuple[str, str]]) -> list[tuple[str, int, int]]:
    """Consecutive steps that count from the same event, as (name, first slot, last slot)."""
    groups: list[tuple[str, int, int]] = []
    for slot, (_, event) in enumerate(labels):
        if groups and groups[-1][0] == event:
            groups[-1] = (event, groups[-1][1], slot)
        else:
            groups.append((event, slot, slot))
    return groups


def shares_m(value: float) -> str:
    """An axis tick in millions of shares."""
    return f"{value:,.0f}M"


def shares_b(value: float) -> str:
    """An axis tick in billions of shares, from millions."""
    return "0" if value == 0 else f"{value / 1000:,.1f}B"


def dollars_b(value: float) -> str:
    """An axis tick in billions of dollars."""
    if value == 0:
        return "$0"
    return f"${value:,.0f}B" if value == int(value) else f"${value:,.1f}B"


def percent(value: float) -> str:
    return f"{value:,.0f}%".replace("-", "−")


class Figures:
    """The `chart(...)` function of the templates. Remembers what it drew."""

    def __init__(
        self,
        numbers: Numbers,
        at: str = "mid",
        price_ref: str = "offering.price_mid",
        quote: Quote | None = None,
    ) -> None:
        self.n = numbers
        self.at = at  # the price point of the headline figures: mid, or final once priced
        self.price_ref = price_ref
        self.quote = quote
        self.drawn: dict[str, Chart] = {}
        self.steps: dict[str, list[Mark]] = {}
        self._quarter_slots = [QUARTER_NAMES[q].split()[0] for q in QUARTERS]
        years = [QUARTER_NAMES[q].split()[1] for q in QUARTERS]
        self._quarter_groups = [
            (year, years.index(year), len(years) - 1 - years[::-1].index(year))
            for year in dict.fromkeys(years)
        ]

    def __call__(self, name: str) -> Markup:
        builders = {
            "value.ranges": self._value_ranges,
            "ev.ranges": self._ev_ranges,
            "growth.revenue": self._revenue,
            "growth.qoq": self._growth_rate,
            "growth.revenue_vs_compute": self._revenue_vs_compute,
            "growth.margin": self._margin,
            "contracts.due_by_year": self._due_by_year,
            "losses.by_year": self._loss_by_year,
            "market.day": self._market_day,
            "deal.shares": self._deal_shares,
            "unlock.steps": self._unlock_steps,
        }
        chart = builders[name]()
        self.drawn[name] = chart
        return chart.svg

    # -- the standalone charts ------------------------------------------------

    def _quarterly(self, prefix: str, what: str, style: str, **options: bool) -> list[Mark]:
        return [
            self.n.mark(
                f"{prefix}.{q}", f"{what}, {QUARTER_NAMES[q]}", style, divide=BILLION, **options
            )
            for q in QUARTERS
        ]

    def _value_ranges(self) -> Chart:
        price = {point: self.n.text(f"offering.price_{point}") for point in ("low", "mid", "high")}

        def row(name: str, prefix: str, others: tuple[tuple[Mark, str], ...] = ()) -> Range:
            low, mid, high = (
                self.n.mark(f"{prefix}.{point}", f"{name} at {price[point]}", divide=BILLION)
                for point in ("low", "mid", "high")
            )
            return Range(name, low, mid, high, others)

        reuters = self.n.mark(
            "press.reuters.outstanding_high", "Reported by Reuters", divide=BILLION
        )
        cnbc = self.n.mark("press.cnbc.fully_diluted_high", "Reported by CNBC", divide=BILLION)
        return charts.ranges(
            [
                row("Outstanding", "value.mcap_out", ((reuters, "Reuters"),)),
                row("Diluted", "value.equity_diluted"),
                row("Press basis", "value.headline", ((cnbc, "CNBC"),)),
            ],
            tick_fmt=dollars_b,
            between="to",
            aria=(
                "Value across the IPO price range for three ways of counting shares, "
                "with the two figures reported by the press. The values are in the table."
            ),
        )

    def _ev_ranges(self) -> Chart:
        price = {point: self.n.text(f"offering.price_{point}") for point in ("low", "mid", "high")}

        def row(name: str, prefix: str) -> Range:
            low, mid, high = (
                self.n.mark(f"{prefix}.{point}", f"{name} at {price[point]}", divide=BILLION)
                for point in ("low", "mid", "high")
            )
            return Range(name, low, mid, high)

        return charts.ranges(
            [
                row("Diluted value", "value.equity_diluted"),
                row("Enterprise value", "ev.enterprise_value"),
            ],
            tick_fmt=dollars_b,
            between="to",
            aria=(
                "Diluted value and enterprise value across the IPO price range. "
                "The values are in the tables."
            ),
        )

    def _revenue(self) -> Chart:
        return charts.columns(
            self._quarterly("q.revenue", "Revenue", "b"),
            xlabels=self._quarter_slots,
            groups=self._quarter_groups,
            tick_fmt=dollars_b,
            label=[6, 4, 0],
            aria="Revenue by quarter, in columns. The values are in the tables below.",
        )

    def _growth_rate(self) -> Chart:
        marks: list[Mark | None] = [None]
        marks += [
            self.n.mark(
                f"growth.qoq.{q}",
                f"Growth over the prior quarter, {QUARTER_NAMES[q]}",
                "signed",
                plus=True,
            )
            for q in QUARTERS[1:]
        ]
        return charts.lines(
            [("s1", marks)],
            xlabels=self._quarter_slots,
            groups=self._quarter_groups,
            tick_fmt=percent,
            label=[(0, 6, "below"), (0, 5, "above"), (0, 3, "below"), (0, 1, "above")],
            aria="Revenue growth over the prior quarter, as a line. The values are in the tables.",
        )

    def _revenue_vs_compute(self) -> Chart:
        revenue: list[Mark | None] = list(self._quarterly("q.revenue", "Revenue", "b"))
        compute: list[Mark | None] = list(self._quarterly("q.compute", "Compute cost", "b"))
        return charts.lines(
            [("s1", revenue), ("s2", compute)],
            xlabels=self._quarter_slots,
            groups=self._quarter_groups,
            tick_fmt=dollars_b,
            label=[(0, 6, "above"), (1, 6, "below"), (1, 0, "above")],
            aria=(
                "Revenue and compute cost by quarter, as two lines. Revenue passes compute cost "
                "at the start of the second year. The values are in the tables below."
            ),
        )

    def _margin(self) -> Chart:
        marks = [
            self.n.mark(
                f"growth.operating_margin.{q}",
                f"Operating margin, {QUARTER_NAMES[q]}",
                "signed",
                plus=True,
            )
            for q in QUARTERS
        ]
        return charts.columns(
            marks,
            xlabels=self._quarter_slots,
            groups=self._quarter_groups,
            tick_fmt=percent,
            label=[6, 5, 0, 2],
            signed=True,
            aria=(
                "Operating margin by quarter, in columns above and below zero. "
                "The values are in the tables below."
            ),
        )

    def _due_by_year(self) -> Chart:
        marks = [
            self.n.mark(
                f"obligations.total.{year}",
                "Due after 2030" if year == "thereafter" else f"Due in {year}",
                "b1",
                divide=BILLION,
            )
            for year in DUE
        ]
        return charts.columns(
            marks,
            xlabels=[DUE_NAMES[year] for year in DUE],
            tick_fmt=dollars_b,
            label=[5, 3, 0, 1],
            apart=[5],
            height=154.0,
            aria=(
                "Fixed payments already running, by the year they fall due. "
                "The last column adds up every later year. The values are in the table."
            ),
        )

    def _loss_by_year(self) -> Chart:
        groups = [
            (
                YEAR_NAMES[year],
                [
                    self.n.mark(
                        f"is.operating_income.{year}",
                        f"Operating loss, {YEAR_NAMES[year]}",
                        "b1",
                        mag=True,
                        divide=BILLION,
                    ),
                    self.n.mark(
                        f"is.net_loss.{year}",
                        f"Net loss, {YEAR_NAMES[year]}",
                        "b1",
                        mag=True,
                        divide=BILLION,
                    ),
                ],
            )
            for year in YEARS
        ]
        return charts.grouped(
            groups,
            tones=["s1", "s2"],
            tick_fmt=dollars_b,
            label=[(3, 1), (2, 1), (3, 0), (1, 1)],
            height=154.0,
            aria=(
                "Operating loss and net loss by period, in pairs of columns. "
                "The values are in the table."
            ),
        )

    def _market_day(self) -> Chart:
        quote = self.quote
        if quote is None or len(quote.line) < 2:
            raise ValueError("no price series to draw")
        line = quote.line
        zone = timezone(timedelta(seconds=quote.offset))

        def clock(moment: int) -> str:
            local = datetime.fromtimestamp(moment, zone)
            return f"{local.hour}:{local:%M}"

        last = self.n.mark("market.price", f"Last price, {quote.when()}")
        ipo = self.n.raw(self.price_ref)
        name = "IPO price" if self.at == "final" else "middle of the IPO range"
        return charts.trace(
            line,
            last=last,
            tick_fmt=lambda value: f"${value:,.2f}",
            ends=(clock(line[0][0]), f"{clock(line[-1][0])} {quote.zone}"),
            level=(ipo, name),
            aria=(
                "Share price through the trading day, as a line. The last price, the range of "
                "the day and the volume are in the table."
            ),
        )

    def _deal_shares(self) -> Chart:
        marks = [self.n.mark(ref, name, "m", divide=MILLION) for ref, name in DEAL_PARTS]
        return charts.columns(
            marks,
            xlabels=[short for _, _, short in DEAL_SHORT],
            tick_fmt=shares_m,
            label=[0, 1, 2, 3],
            apart=[2],
            height=154.0,
            aria=(
                "Shares in the deal, by where they come from: new shares from the company, "
                "shares from existing stockholders, the underwriters' option (muted: used only "
                "if demand allows) and the private placement. The values are in the table."
            ),
        )

    def _unlock_steps(self) -> Chart:
        steps = unlock_steps(self.n.facts.ids())
        marks = [
            self.n.mark(key, f"Step {index}: {self.n.text(key + '.when')}", "m", divide=MILLION)
            for index, key in enumerate(steps, start=1)
        ]
        labels = [unlock_label(self.n.facts.text(key + ".when")) for key in steps]
        groups = unlock_groups(labels)
        biggest = sorted(range(len(marks)), key=lambda i: -marks[i].value)[:3]
        return charts.columns(
            marks,
            xlabels=[""] * len(labels),  # too many for a phone: the table names each step
            tick_fmt=shares_b,
            label=biggest,
            groups=groups,
            height=168.0,
            aria=(
                "Shares that may be sold at each step after the IPO, as the filing's table "
                "gives them, each a maximum. Steps are grouped by the event they count from. "
                "The values and the filing's wording are in the table."
            ),
        )

    # -- the bridge, drawn row by row inside its table ----------------------------

    def step(self, ref: str) -> Markup:
        """The bar of one row of the enterprise value bridge."""
        steps = bridge(self.at)
        top = self.n.raw(steps[0][0])
        running = 0.0
        for step_ref, kind in steps:
            value = self.n.raw(step_ref)
            if kind == "total":
                start, end, running = 0.0, value, value
            elif kind == "minus":
                start, end, running = running - value, running, running - value
            else:
                start, end, running = running, running + value, running + value
            if step_ref == ref:
                mark = self.n.mark(ref, kind, "b1", divide=BILLION)
                self.steps.setdefault("ev.bridge", []).append(mark)
                x, width = start / top * 100, (end - start) / top * 100
                bar = charts.tag("rect", class_="bar-bg", width=100.0, height=4.0)
                if width > 0:
                    bar += charts.tag(
                        "rect", class_=f"bar-fg step-{kind}", x=x, width=max(width, 0.4), height=4.0
                    )
                # Safe: only numbers and fixed class names go into this markup.
                return Markup(  # noqa: S704
                    charts.tag(
                        "svg",
                        bar,
                        class_="bar",
                        viewBox="0 0 100 4",
                        preserveAspectRatio="none",
                        aria_hidden="true",
                        focusable="false",
                    )
                )
        raise KeyError(ref)

    def marks(self) -> dict[str, tuple[Mark, ...]]:
        """Every value drawn so far, by chart."""
        out = {name: chart.marks for name, chart in self.drawn.items()}
        out.update({name: tuple(marks) for name, marks in self.steps.items()})
        return out
