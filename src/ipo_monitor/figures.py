"""The charts of the dashboard: which facts each one draws, and how.

The drawing itself is in `charts.py`. Everything here goes through
`Numbers.mark`, so a chart cannot show a value that has no source card.
"""

from __future__ import annotations

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
        if quote is None or len(quote.points) < 2:
            raise ValueError("no price series to draw")
        zone = timezone(timedelta(seconds=quote.offset))

        def clock(moment: int) -> str:
            local = datetime.fromtimestamp(moment, zone)
            return f"{local.hour}:{local:%M}"

        last = self.n.mark("market.price", f"Last price, {quote.when()}")
        ipo = self.n.raw(self.price_ref)
        name = "IPO price" if self.at == "final" else "middle of the IPO range"
        return charts.trace(
            quote.points,
            last=last,
            tick_fmt=lambda value: f"${value:,.2f}",
            ends=(clock(quote.points[0][0]), f"{clock(quote.points[-1][0])} {quote.zone}"),
            level=(ipo, name),
            aria=(
                "Share price through the trading day, as a line. The last price, the range of "
                "the day and the volume are in the table."
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
