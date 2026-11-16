"""Reconciliation: the extracted figures must agree with each other.

Every check compares numbers that the filing states in two different places
(a table and its total, a sentence and a table, quarters and the year). If one
fails, the dataset is refused: the application does not start and the build
fails, instead of publishing a wrong figure.
"""

from __future__ import annotations

from dataclasses import dataclass

from ipo_monitor.facts import Facts

MILLION = 1_000_000.0
BILLION = 1_000_000_000.0

OPEX_PARTS = ("compute", "personnel", "bartz", "sales", "other_opex")
STATEMENT_ROWS = (
    "revenue",
    *OPEX_PARTS,
    "total_opex",
    "operating_income",
    "interest_income",
    "fv_change",
    "other_income",
    "total_other",
    "pretax",
    "taxes",
    "net_loss",
)
ANNUAL = ("fy2023", "fy2024", "fy2025", "9m2025", "9m2026")
QUARTERS = ("2025q1", "2025q2", "2025q3", "2025q4", "2026q1", "2026q2", "2026q3")
OBLIGATION_ROWS = ("operating_leases", "finance_leases", "purchase_commitments")
OBLIGATION_YEARS = ("2026", "2027", "2028", "2029", "2030", "thereafter")


@dataclass(frozen=True)
class Check:
    """One comparison and its outcome."""

    name: str
    ok: bool
    detail: str


class ReconciliationError(RuntimeError):
    """At least one reconciliation check failed."""

    def __init__(self, failed: list[Check]) -> None:
        self.failed = failed
        lines = "\n".join(f"  - {c.name}: {c.detail}" for c in failed)
        super().__init__(f"{len(failed)} reconciliation check(s) failed:\n{lines}")


def _close(name: str, left: float, right: float, tolerance: float) -> Check:
    gap = abs(left - right)
    detail = f"{left:,.0f} vs {right:,.0f} (gap {gap:,.0f}, allowed {tolerance:,.0f})"
    return Check(name, gap <= tolerance, detail)


def run_checks(f: Facts) -> list[Check]:
    """Every check, passed or not."""
    checks: list[Check] = []

    # 1. Each statement of operations adds up, column by column.
    for prefix, periods in (("is", ANNUAL), ("q", QUARTERS)):
        for p in periods:

            def v(row: str, prefix: str = prefix, p: str = p) -> float:
                return f.num(f"{prefix}.{row}.{p}")

            name = f"{prefix}.{p}"
            checks += [
                _close(
                    f"{name}: operating expenses add up",
                    sum(v(r) for r in OPEX_PARTS),
                    v("total_opex"),
                    MILLION,
                ),
                _close(
                    f"{name}: revenue - expenses = operating result",
                    v("revenue") - v("total_opex"),
                    v("operating_income"),
                    MILLION,
                ),
                _close(
                    f"{name}: other income adds up",
                    v("interest_income") + v("fv_change") + v("other_income"),
                    v("total_other"),
                    MILLION,
                ),
                _close(
                    f"{name}: operating result + other = pre-tax loss",
                    v("operating_income") + v("total_other"),
                    v("pretax"),
                    MILLION,
                ),
                _close(
                    f"{name}: pre-tax loss - taxes = net loss",
                    v("pretax") - v("taxes"),
                    v("net_loss"),
                    MILLION,
                ),
            ]

    # 2. Quarters add up to the periods of the annual table.
    spans = {
        "fy2025": ("2025q1", "2025q2", "2025q3", "2025q4"),
        "9m2025": ("2025q1", "2025q2", "2025q3"),
        "9m2026": ("2026q1", "2026q2", "2026q3"),
    }
    for period, quarters in spans.items():
        for row in STATEMENT_ROWS:
            checks.append(
                _close(
                    f"quarters add up to {period}: {row}",
                    sum(f.num(f"q.{row}.{q}") for q in quarters),
                    f.num(f"is.{row}.{period}"),
                    2 * MILLION,
                )
            )

    # 3. Growth rates stated in the text match the quarterly table.
    for metric, row in (("revenue_growth_q3", "revenue"), ("compute_growth_q3", "compute")):
        computed = (f.num(f"q.{row}.2026q3") / f.num(f"q.{row}.2025q3") - 1) * 100
        checks.append(
            _close(
                f"stated {row} growth matches the table", computed, f.num(f"metrics.{metric}"), 0.5
            )
        )

    # 4. Cash.
    checks.append(
        _close(
            "cash equivalents + short-term investments = total",
            f.num("balance.cash_equivalents") + f.num("balance.short_term_investments"),
            f.num("balance.cash.actual"),
            100 * MILLION,
        )
    )
    checks.append(
        _close(
            "post-offering cash - cash today + RSU taxes paid = net proceeds",
            f.num("balance.cash.as_adjusted")
            - f.num("balance.cash.actual")
            + f.num("shares.rsu_tax_withheld") * f.num("offering.price_mid"),
            f.num("offering.net_proceeds_mid"),
            100 * MILLION,
        )
    )
    checks.append(
        _close(
            "accumulated deficit: text matches table",
            f.num("deficit.accumulated"),
            -f.num("balance.accumulated_deficit.actual"),
            50 * MILLION,
        )
    )
    checks.append(
        _close(
            "fair-value change of the nine months: text matches table",
            f.num("deficit.fair_value_9m2026"),
            -f.num("is.fv_change.9m2026"),
            50 * MILLION,
        )
    )

    # 5. Commitments.
    checks.append(
        _close(
            "the five parts of committed spend add up to the total",
            f.num("obligations.total.total")
            + f.num("commit.short_term")
            + f.num("commit.leases_not_commenced")
            + f.num("commit.after_sep30")
            + f.num("commit.after_sep30_short_term"),
            f.num("commit.total"),
            150 * MILLION,
        )
    )
    ordered = f.num("commit.next_12m") <= f.num("commit.before_2031") <= f.num(
        "commit.total"
    ) and f.num("commit.conditional") <= f.num("commit.total")
    checks.append(
        Check(
            "commitment horizons are nested (12 months <= before 2031 <= total)",
            ordered,
            "ordering of the stated amounts",
        )
    )
    for year in ("total", *OBLIGATION_YEARS):
        checks.append(
            _close(
                f"obligations table, column {year}: rows add up",
                sum(f.num(f"obligations.{r}.{year}") for r in OBLIGATION_ROWS),
                f.num(f"obligations.total.{year}"),
                MILLION,
            )
        )
    for row in (*OBLIGATION_ROWS, "total"):
        checks.append(
            _close(
                f"obligations table, row {row}: years add up",
                sum(f.num(f"obligations.{row}.{y}") for y in OBLIGATION_YEARS),
                f.num(f"obligations.{row}.total"),
                MILLION,
            )
        )

    # 6. Shares and price.
    checks += [
        _close(
            "share classes add up to all shares outstanding",
            f.num("shares.class_a_after") + f.num("shares.class_n_after") + 2,
            f.num("shares.total_after"),
            0,
        ),
        _close(
            "underwriters' option = difference between the two share totals",
            f.num("shares.total_after_greenshoe") - f.num("shares.total_after"),
            f.num("offering.greenshoe"),
            0,
        ),
        _close(
            "Amazon notes: converted + remaining = total issuable",
            f.num("notes.shares_converted_at_ipo") + f.num("notes.shares_remaining"),
            f.num("notes.shares_issuable_total"),
            0,
        ),
        _close(
            "private placement shares x assumed price = amount",
            f.num("offering.private_placement_shares_mid") * f.num("offering.price_mid"),
            f.num("offering.private_placement"),
            10_000,
        ),
        _close(
            "assumed price is the midpoint of the range",
            (f.num("offering.price_low") + f.num("offering.price_high")) / 2,
            f.num("offering.price_mid"),
            0,
        ),
    ]
    return checks


def assert_consistent(f: Facts) -> list[Check]:
    """Run every check; raise if any fails."""
    checks = run_checks(f)
    failed = [c for c in checks if not c.ok]
    if failed:
        raise ReconciliationError(failed)
    return checks
