"""Calculations: every CALC number on the page, with its formula and inputs.

A calculation only combines facts (and other calculations). It records what
it combined, so the page can show the arithmetic behind each result.
"""

from __future__ import annotations

from dataclasses import dataclass

from ipo_monitor.facts import Facts

PRICE_POINTS = ("low", "mid", "high")
PRICED = "pricing.ipo_price"  # the final IPO price, once a sourced fact records it
MARKET_PRICE = "market.price"  # the last share price, once the stock trades
QUARTERS = ("2025q1", "2025q2", "2025q3", "2025q4", "2026q1", "2026q2", "2026q3")
QUARTER_NAMES = {
    "2025q1": "Q1 2025",
    "2025q2": "Q2 2025",
    "2025q3": "Q3 2025",
    "2025q4": "Q4 2025",
    "2026q1": "Q1 2026",
    "2026q2": "Q2 2026",
    "2026q3": "Q3 2026",
}


@dataclass(frozen=True)
class Term:
    """One input of a calculation."""

    name: str
    value: float
    unit: str
    ref: str | None  # id of the fact or calculation it comes from; None for a constant


@dataclass(frozen=True)
class Calc:
    """One calculated value."""

    id: str
    title: str
    value: float
    unit: str
    formula: str
    terms: tuple[Term, ...]
    note: str | None = None


class Calculator:
    """Builds all calculations from the facts."""

    def __init__(self, facts: Facts) -> None:
        self.facts = facts
        self.calcs: dict[str, Calc] = {}
        priced = PRICED in facts
        # An amendment gives a price range; the final prospectus gives only the IPO price.
        self.ranged = "offering.price_low" in facts
        if self.ranged:
            self.points: tuple[str, ...] = (*PRICE_POINTS, "final") if priced else PRICE_POINTS
        else:
            self.points = ("final",)
        self.at = "final" if priced else "mid"  # the price the headline figures use
        # The price the filing's "after the offering" figures use: the middle of the range in
        # an amendment, the IPO price in the final prospectus.
        self.basis = facts.num("offering.price_mid")
        self.basis_text = f"${self.basis:.2f}"

    def price_ref(self, point: str) -> str:
        return PRICED if point == "final" else f"offering.price_{point}"

    # -- building blocks ----------------------------------------------------

    def term(self, name: str, ref: str) -> Term:
        if ref in self.calcs:
            calc = self.calcs[ref]
            return Term(name, calc.value, calc.unit, ref)
        fact = self.facts.get(ref)
        return Term(name, self.facts.num(ref), fact.unit, ref)

    def value(self, ref: str) -> float:
        return self.calcs[ref].value if ref in self.calcs else self.facts.num(ref)

    def put(
        self,
        calc_id: str,
        title: str,
        value: float,
        unit: str,
        formula: str,
        terms: list[Term],
        note: str | None = None,
    ) -> float:
        if calc_id in self.calcs or calc_id in self.facts:
            raise ValueError(f"duplicate id: {calc_id}")
        self.calcs[calc_id] = Calc(calc_id, title, value, unit, formula, tuple(terms), note)
        return value

    def total(
        self, calc_id: str, title: str, parts: list[tuple[str, str]], note: str | None = None
    ) -> float:
        terms = [self.term(name, ref) for name, ref in parts]
        formula = " + ".join(t.name for t in terms)
        return self.put(
            calc_id, title, sum(t.value for t in terms), terms[0].unit, formula, terms, note
        )

    def divide(
        self,
        calc_id: str,
        title: str,
        top: tuple[str, str],
        bottom: tuple[str, str],
        unit: str = "ratio",
        note: str | None = None,
    ) -> float:
        a, b = self.term(*top), self.term(*bottom)
        return self.put(
            calc_id, title, a.value / b.value, unit, f"{a.name} ÷ {b.name}", [a, b], note
        )

    def growth(self, calc_id: str, title: str, new: tuple[str, str], old: tuple[str, str]) -> float:
        a, b = self.term(*new), self.term(*old)
        value = (a.value / b.value - 1) * 100
        return self.put(calc_id, title, value, "percent", f"{a.name} ÷ {b.name} − 1", [a, b])

    # -- the calculations ---------------------------------------------------

    def run(self) -> dict[str, Calc]:
        self._offering()
        self._value()
        self._growth()
        self._enterprise_value()
        self._market()
        self._contracts()
        self._losses()
        self._structure()
        return self.calcs

    def _offering(self) -> None:
        self.total(
            "offering.shares_total",
            "Shares offered in the IPO",
            [
                ("shares sold by the company", "offering.shares_company"),
                ("shares sold by existing stockholders", "offering.shares_selling"),
            ],
        )
        ends = ("low", "high") if self.ranged else ()
        for point in (*ends, *(("final",) if "final" in self.points else ())):
            shares = self.term("shares offered", "offering.shares_total")
            price = self.term("IPO price", self.price_ref(point))
            self.put(
                f"offering.size.{point}",
                "Size of the IPO at the IPO price"
                if point == "final"
                else f"Size of the IPO at the {point} end of the range",
                shares.value * price.value,
                "USD",
                "shares offered × IPO price",
                [shares, price],
                "Includes the shares sold by existing stockholders, whose proceeds do not go to "
                "the company. Excludes the underwriters' option and the private placement.",
            )

    def _value(self) -> None:
        owed = [
            ("shares still owed to Amazon on its convertible notes", "notes.shares_remaining"),
            ("shares issuable on exercise of stock options", "shares.options"),
            ("shares issuable when outstanding RSUs vest", "shares.rsus_unvested"),
            ("shares for RSUs granted after Sep 30", "shares.rsus_granted_after"),
            ("Class A shares issued for acquisitions after Sep 30", "shares.acquisitions_class_a"),
            ("Class N shares issued for acquisitions after Sep 30", "shares.acquisitions_class_n"),
            ("shares issued after Sep 30 to match donations", "shares.matching_issuance"),
        ]
        self.total(
            "value.owed_shares",
            "Shares already owed or granted, not yet counted as outstanding",
            owed,
            "The filing lists each of these as excluded from the shares outstanding. "
            "Options and RSUs are counted in full, vested or not.",
        )
        self.total(
            "value.rsu_shares",
            "Shares issuable for RSUs",
            [
                ("RSUs outstanding as of Sep 30", "shares.rsus_unvested"),
                ("RSUs granted after Sep 30", "shares.rsus_granted_after"),
            ],
        )
        self.total(
            "value.issued_since_shares",
            "Shares issued after Sep 30, 2026",
            [
                ("Class A shares for acquisitions", "shares.acquisitions_class_a"),
                ("Class N shares for acquisitions", "shares.acquisitions_class_n"),
                ("shares to match employee donations", "shares.matching_issuance"),
            ],
        )
        self.total(
            "value.reserve_shares",
            "Shares reserved for grants that do not exist yet",
            [
                ("2026 Equity Incentive Plan reserve", "shares.plan_2026_reserve"),
                ("employee stock purchase plan reserve", "shares.espp_reserve"),
            ],
            "Reserved, not granted: nobody holds these shares or a right to them today.",
        )
        self.total(
            "value.headline_shares",
            "Share count that reproduces the 'fully diluted' press figures",
            [
                ("shares outstanding after the offering", "shares.total_after"),
                ("stock options", "shares.options"),
                ("RSUs outstanding as of Sep 30", "shares.rsus_unvested"),
                ("RSUs granted after Sep 30", "shares.rsus_granted_after"),
                ("Class A shares for acquisitions", "shares.acquisitions_class_a"),
                ("Class N shares for acquisitions", "shares.acquisitions_class_n"),
                ("shares to match employee donations", "shares.matching_issuance"),
                ("2026 Equity Incentive Plan reserve", "shares.plan_2026_reserve"),
                ("employee stock purchase plan reserve", "shares.espp_reserve"),
            ],
            "Our reconstruction: news outlets do not publish their share count. This sum, "
            "multiplied by the top of the range, gives the reported $1.405 trillion. It includes "
            "shares reserved for future grants and leaves out the shares owed to Amazon.",
        )

        for point in self.points:
            price = self.term("IPO price", self.price_ref(point))
            label = f"at ${price.value:.2f}"

            if price.value == self.basis:
                out = self.term("shares outstanding after the offering", "shares.total_after")
                self.put(
                    f"value.shares_out.{point}",
                    f"Shares outstanding after the offering, {label}",
                    out.value,
                    "shares",
                    f"as stated in the filing at the {self.basis_text} price",
                    [out],
                )
            else:
                amount = self.term("private placement amount", "offering.private_placement")
                placement = self.put(
                    f"value.placement_shares.{point}",
                    f"Shares sold in the private placement, {label}",
                    amount.value / price.value,
                    "shares",
                    "private placement amount ÷ IPO price",
                    [amount, price],
                    "The placement is a fixed dollar amount, so its share count moves with "
                    "the price.",
                )
                terms = [
                    self.term(f"shares outstanding at {self.basis_text}", "shares.total_after"),
                    self.term(
                        f"private placement shares at {self.basis_text}",
                        "offering.private_placement_shares_mid",
                    ),
                    self.term(
                        f"private placement shares {label}", f"value.placement_shares.{point}"
                    ),
                ]
                self.put(
                    f"value.shares_out.{point}",
                    f"Shares outstanding after the offering, {label}",
                    terms[0].value - terms[1].value + placement,
                    "shares",
                    f"shares outstanding at {self.basis_text} − private placement shares at "
                    f"{self.basis_text} + private placement shares {label}",
                    terms,
                )

            out = self.term("shares outstanding after the offering", f"value.shares_out.{point}")
            self.put(
                f"value.mcap_out.{point}",
                f"Value of the shares outstanding, {label}",
                out.value * price.value,
                "USD",
                "shares outstanding after the offering × IPO price",
                [out, price],
                "Counts only shares that exist right after the offering.",
            )
            owed_term = self.term("shares already owed or granted", "value.owed_shares")
            diluted = self.put(
                f"value.shares_diluted.{point}",
                f"Diluted share count, {label}",
                out.value + owed_term.value,
                "shares",
                "shares outstanding after the offering + shares already owed or granted",
                [out, owed_term],
            )
            diluted_term = self.term("diluted share count", f"value.shares_diluted.{point}")
            self.put(
                f"value.equity_diluted.{point}",
                f"Diluted value, {label}",
                diluted * price.value,
                "USD",
                "diluted share count × IPO price",
                [diluted_term, price],
                "Adds every share already owed or granted: the Amazon notes, stock options "
                "and RSUs. Leaves out shares only reserved for future grants.",
            )
            reserve = self.term("shares reserved for future grants", "value.reserve_shares")
            self.put(
                f"value.equity_with_reserves.{point}",
                f"Value if the shares reserved for future grants also counted, {label}",
                (diluted + reserve.value) * price.value,
                "USD",
                "(diluted share count + shares reserved for future grants) × IPO price",
                [diluted_term, reserve, price],
            )
            headline = self.term("press-basis share count", "value.headline_shares")
            self.put(
                f"value.headline.{point}",
                f"'Fully diluted' value on the press basis, {label}",
                headline.value * price.value,
                "USD",
                "press-basis share count × IPO price",
                [headline, price],
                "Our reconstruction of the basis behind the reported figures.",
            )

    def _growth(self) -> None:
        for index, quarter in enumerate(QUARTERS):
            name = QUARTER_NAMES[quarter]
            revenue = (f"revenue {name}", f"q.revenue.{quarter}")
            if index >= 1:
                before = QUARTERS[index - 1]
                self.growth(
                    f"growth.qoq.{quarter}",
                    f"Revenue growth over the previous quarter, {name}",
                    revenue,
                    (f"revenue {QUARTER_NAMES[before]}", f"q.revenue.{before}"),
                )
            if index >= 4:
                year_ago = QUARTERS[index - 4]
                self.growth(
                    f"growth.yoy.{quarter}",
                    f"Revenue growth over the same quarter a year earlier, {name}",
                    revenue,
                    (f"revenue {QUARTER_NAMES[year_ago]}", f"q.revenue.{year_ago}"),
                )
            self.divide(
                f"growth.revenue_per_compute.{quarter}",
                f"Revenue per $1 of compute and infrastructure expense, {name}",
                revenue,
                (f"compute and infrastructure {name}", f"q.compute.{quarter}"),
            )
            operating = self.term(f"operating result {name}", f"q.operating_income.{quarter}")
            sales = self.term(*revenue)
            self.put(
                f"growth.operating_margin.{quarter}",
                f"Operating margin, {name}",
                operating.value / sales.value * 100,
                "percent",
                f"{operating.name} ÷ {sales.name}",
                [operating, sales],
            )

        self.growth(
            "growth.annual.fy2024",
            "Revenue growth, 2024 over 2023",
            ("revenue 2024", "is.revenue.fy2024"),
            ("revenue 2023", "is.revenue.fy2023"),
        )
        self.growth(
            "growth.annual.fy2025",
            "Revenue growth, 2025 over 2024",
            ("revenue 2025", "is.revenue.fy2025"),
            ("revenue 2024", "is.revenue.fy2024"),
        )
        self.growth(
            "growth.annual.9m2026",
            "Revenue growth, first nine months of 2026 over 2025",
            ("revenue, nine months 2026", "is.revenue.9m2026"),
            ("revenue, nine months 2025", "is.revenue.9m2025"),
        )

        last_four = QUARTERS[-4:]
        self.total(
            "growth.ttm_revenue",
            "Revenue of the last twelve months (to Sep 30, 2026)",
            [(f"revenue {QUARTER_NAMES[q]}", f"q.revenue.{q}") for q in last_four],
        )
        q3 = self.term("revenue Q3 2026", "q.revenue.2026q3")
        self.put(
            "growth.q3_annualized",
            "Q3 2026 revenue, annualized",
            q3.value * 4,
            "USD",
            "revenue Q3 2026 × 4",
            [q3, Term("quarters in a year", 4, "count", None)],
            "A simple multiplication, not a figure from the filing.",
        )
        october = self.term("Run-Rate Revenue as of Oct 31", "metrics.run_rate_oct31")
        increase = self.term("increase during October", "metrics.run_rate_increase_oct")
        self.put(
            "growth.run_rate_sep30",
            "Run-Rate Revenue as of Sep 30, 2026",
            october.value - increase.value,
            "USD",
            "Run-Rate Revenue as of Oct 31 − increase during October",
            [october, increase],
            "The filing gives the October figure and the increase; this is the difference.",
        )

    def _enterprise_value(self) -> None:
        options = self.term("stock options", "shares.options")
        strike = self.term("average exercise price", "shares.options_exercise_price")
        self.put(
            "ev.option_proceeds",
            "Cash the company receives if all stock options are exercised",
            options.value * strike.value,
            "USD",
            "stock options × average exercise price",
            [options, strike],
            "The diluted value counts every option as a share, so the cash paid to exercise "
            "them is counted too.",
        )
        withheld = self.term("RSU shares withheld for taxes", "shares.rsu_tax_withheld")
        assumed = self.term("IPO price the filing assumes", "offering.price_mid")
        self.put(
            "ev.rsu_tax_paid",
            "Cash paid by the company for taxes on employee RSUs at the offering",
            withheld.value * assumed.value,
            "USD",
            "RSU shares withheld for taxes × IPO price the filing assumes",
            [withheld, assumed],
            "The company keeps these shares and pays the employees' taxes in cash. Cash today "
            "+ net proceeds − this amount matches the filing's post-offering cash to within "
            "rounding.",
        )
        mid = self.basis
        at_basis = self.basis_text
        for point in self.points:
            price = self.term("IPO price", self.price_ref(point))
            label = f"at ${price.value:.2f}"
            base = self.term(f"cash after the offering at {at_basis}", "balance.cash.as_adjusted")
            if price.value == mid:
                self.put(
                    f"ev.cash_after.{point}",
                    f"Cash after the offering, {label}",
                    base.value,
                    "USD",
                    f"as stated in the filing (pro forma as adjusted) at the {at_basis} price",
                    [base],
                )
            else:
                per_dollar = self.term(
                    "change per $1.00 of IPO price", "balance.cash_sensitivity_per_dollar"
                )
                self.put(
                    f"ev.cash_after.{point}",
                    f"Cash after the offering, {label}",
                    base.value + (price.value - mid) * per_dollar.value,
                    "USD",
                    f"cash after the offering at {at_basis} + (IPO price − {at_basis}) "
                    "× change per $1.00",
                    [base, price, per_dollar],
                )
            equity = self.term("diluted value", f"value.equity_diluted.{point}")
            cash = self.term("cash after the offering", f"ev.cash_after.{point}")
            proceeds = self.term("cash from option exercises", "ev.option_proceeds")
            debt = self.term("borrowings drawn", "debt.credit_facility_drawn")
            self.put(
                f"ev.enterprise_value.{point}",
                f"Enterprise value, {label}",
                equity.value - cash.value - proceeds.value + debt.value,
                "USD",
                "diluted value − cash after the offering − cash from option exercises "
                "+ borrowings drawn",
                [equity, cash, proceeds, debt],
                "What the price pays for the business itself, once the cash that comes with it "
                "is set aside. The Amazon convertible notes are counted as shares in the diluted "
                "value, so they are not added again as debt. Lease and compute commitments are "
                "not debt here: see CONTRACTS.",
            )

        headline = self.facts.num(self.price_ref(self.at))
        ev = (f"enterprise value at ${headline:.2f}", f"ev.enterprise_value.{self.at}")
        self.divide(
            "ev.multiple.run_rate",
            "Enterprise value as a multiple of Run-Rate Revenue",
            ev,
            ("Run-Rate Revenue as of Oct 31", "metrics.run_rate_oct31"),
        )
        self.divide(
            "ev.multiple.q3_annualized",
            "Enterprise value as a multiple of annualized Q3 revenue",
            ev,
            ("Q3 2026 revenue × 4", "growth.q3_annualized"),
        )
        self.divide(
            "ev.multiple.ttm",
            "Enterprise value as a multiple of the last twelve months of revenue",
            ev,
            ("revenue of the last twelve months", "growth.ttm_revenue"),
        )

    def _market(self) -> None:
        """The same values at the last share price. Only when the stock trades."""
        if MARKET_PRICE not in self.facts:
            return
        at = self.at
        price = self.term("market price", MARKET_PRICE)
        ipo = self.term("IPO price", self.price_ref(at))
        basis = "the IPO price" if at == "final" else "the middle of the IPO price range"
        note = (
            "The price is a delayed, unofficial quote. The share counts and the cash are those "
            f"of the filing at {basis} (${ipo.value:.2f}): they do not move with the market."
        )
        out = self.term("shares outstanding after the offering", f"value.shares_out.{at}")
        self.put(
            "market.mcap_out",
            "Value of the shares outstanding at the market price",
            out.value * price.value,
            "USD",
            "shares outstanding after the offering × market price",
            [out, price],
            note,
        )
        diluted = self.term("diluted share count", f"value.shares_diluted.{at}")
        self.put(
            "market.equity_diluted",
            "Diluted value at the market price",
            diluted.value * price.value,
            "USD",
            "diluted share count × market price",
            [diluted, price],
            note,
        )
        equity = self.term("diluted value at the market price", "market.equity_diluted")
        cash = self.term("cash after the offering", f"ev.cash_after.{at}")
        proceeds = self.term("cash from option exercises", "ev.option_proceeds")
        debt = self.term("borrowings drawn", "debt.credit_facility_drawn")
        self.put(
            "market.enterprise_value",
            "Enterprise value at the market price",
            equity.value - cash.value - proceeds.value + debt.value,
            "USD",
            "diluted value at the market price − cash after the offering "
            "− cash from option exercises + borrowings drawn",
            [equity, cash, proceeds, debt],
            note,
        )
        self.put(
            "market.vs_ipo",
            f"Market price against {basis}",
            (price.value / ipo.value - 1) * 100,
            "percent",
            "market price ÷ IPO price − 1",
            [price, ipo],
            None
            if at == "final"
            else "The final IPO price is not recorded here yet: this compares the market price "
            "with the middle of the filed range.",
        )
        self.divide(
            "market.multiple.run_rate",
            "Enterprise value at the market price as a multiple of Run-Rate Revenue",
            ("enterprise value at the market price", "market.enterprise_value"),
            ("Run-Rate Revenue as of Oct 31", "metrics.run_rate_oct31"),
        )

    def _contracts(self) -> None:
        total = self.term("total committed spend", "commit.total")
        before = self.term("expected before Dec 31, 2030", "commit.before_2031")
        soon = self.term("due in the next 12 months", "commit.next_12m")
        self.put(
            "contracts.after_2030",
            "Committed spend expected from 2031 to 2045",
            total.value - before.value,
            "USD",
            "total committed spend − expected before Dec 31, 2030",
            [total, before],
            "The filing says substantially all of the remainder falls between 2031 and 2045.",
        )
        self.put(
            "contracts.rest_before_2031",
            "Committed spend after the next 12 months and before 2031",
            before.value - soon.value,
            "USD",
            "expected before Dec 31, 2030 − due in the next 12 months",
            [before, soon],
        )
        self.total(
            "contracts.signed_after_sep30",
            "Commitments signed after Sep 30, 2026",
            [
                ("long-term commitments signed after Sep 30", "commit.after_sep30"),
                ("short-term commitments signed after Sep 30", "commit.after_sep30_short_term"),
            ],
        )
        conditional = self.term("cancellable or conditional", "commit.conditional")
        self.put(
            "contracts.firm",
            "Committed spend with no termination right or pending condition",
            total.value - conditional.value,
            "USD",
            "total committed spend − cancellable or conditional",
            [total, conditional],
        )
        signed = self.term("signed customer contracts", "rpo.total")
        share = self.term("share recognised within 12 months", "rpo.share_next_12m")
        self.put(
            "contracts.rpo_next_12m",
            "Signed customer contracts recognised as revenue within 12 months",
            signed.value * share.value / 100,
            "USD",
            "signed customer contracts × share recognised within 12 months",
            [signed, share],
        )
        self.divide(
            "contracts.owed_vs_signed",
            "Committed spend for each $1 of signed customer contracts",
            ("total committed spend", "commit.total"),
            ("signed customer contracts", "rpo.total"),
        )
        self.divide(
            "contracts.years_of_run_rate",
            "Committed spend, in years of today's Run-Rate Revenue",
            ("total committed spend", "commit.total"),
            ("Run-Rate Revenue as of Oct 31", "metrics.run_rate_oct31"),
            unit="years",
            note="How many years of revenue at the October pace the commitments represent. "
            "Not a forecast: revenue and commitments both change.",
        )
        self.divide(
            "contracts.cash_cover_12m",
            "Cash after the offering for each $1 due in the next 12 months",
            ("cash after the offering", f"ev.cash_after.{self.at}"),
            ("due in the next 12 months", "commit.next_12m"),
        )

    def _losses(self) -> None:
        period = "nine months to Sep 30, 2026"
        interest = self.term("interest income", "is.interest_income.9m2026")
        other = self.term("other income (expense), net", "is.other_income.9m2026")
        taxes = self.term("provision for income taxes", "is.taxes.9m2026")
        self.put(
            "losses.other_net",
            f"Interest, other items and taxes, net, {period}",
            interest.value + other.value - taxes.value,
            "USD",
            "interest income + other income (expense), net − provision for income taxes",
            [interest, other, taxes],
        )
        net = ("net loss", "is.net_loss.9m2026")
        parts = (
            ("fair_value", "fair-value changes", "is.fv_change.9m2026"),
            ("operating", "operating loss", "is.operating_income.9m2026"),
            ("other", "interest, other items and taxes, net", "losses.other_net"),
        )
        for key, name, ref in parts:
            a, b = self.term(name, ref), self.term(*net)
            self.put(
                f"losses.share.{key}",
                f"Share of the net loss: {name}, {period}",
                a.value / b.value * 100,
                "percent",
                f"{a.name} ÷ {b.name}",
                [a, b],
            )

    def _structure(self) -> None:
        """Where the shares of the deal go, and what the IPO buyers' votes weigh."""
        self.total(
            "deal.shares_all",
            "All shares in the deal, if the underwriters use their option",
            [
                ("new shares sold by the company", "offering.shares_company"),
                ("shares sold by existing stockholders", "offering.shares_selling"),
                ("the underwriters' option", "offering.greenshoe"),
                (
                    "the private placement, at the assumed price",
                    "offering.private_placement_shares_mid",
                ),
            ],
            "The option is used only if demand allows. The private placement's share count "
            "depends on the IPO price; this one is at the middle of the range.",
        )
        placed = self.term("private placement shares", "offering.private_placement_shares_mid")
        everyone = self.term("all shares after the IPO", "shares.total_after")
        self.put(
            "holders.placement_after_pct",
            "Share of all shares held by the private placement's buyers",
            placed.value / everyone.value * 100,
            "percent",
            "private placement shares ÷ all shares after the IPO",
            [placed, everyone],
        )
        bought = self.term("shares sold in the IPO", "holders.new_after")
        class_a = self.term("Class A shares after the IPO", "shares.class_a_after")
        power = self.term("voting power of all Class A shares", "control.class_a_pct")
        self.put(
            "control.ipo_votes_pct",
            "Voting power of the shares sold in the IPO",
            bought.value / class_a.value * power.value,
            "percent",
            "shares sold in the IPO ÷ Class A shares × voting power of all Class A shares",
            [bought, class_a, power],
            "Each Class A share has one vote, and all of them together hold the voting power "
            "the filing states. Assumes no IPO share is bought by an existing holder.",
        )
        ipo = self.term("voting power of the shares sold in the IPO", "control.ipo_votes_pct")
        self.put(
            "control.class_a_other_pct",
            "Voting power of the other Class A shares",
            power.value - ipo.value,
            "percent",
            "voting power of all Class A shares − voting power of the shares sold in the IPO",
            [power, ipo],
            "The Class A shares held by everyone but the IPO's buyers: the third part of the "
            "ring of votes in CONTROL.",
        )


def compute(facts: Facts) -> dict[str, Calc]:
    """All calculations."""
    return Calculator(facts).run()
