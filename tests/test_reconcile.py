"""Reconciliation: consistent data passes, tampered data is refused."""

from __future__ import annotations

import pytest

from ipo_monitor.facts import Facts
from ipo_monitor.reconcile import ReconciliationError, assert_consistent, run_checks

from .conftest import Tamper


def test_all_checks_pass_on_the_dataset(facts: Facts) -> None:
    checks = assert_consistent(facts)
    assert len(checks) >= 120
    assert all(c.ok for c in checks)


@pytest.mark.parametrize(
    ("fact_id", "delta", "expected"),
    [
        ("q.revenue.2026q3", 1e9, "quarters add up to 9m2026: revenue"),
        ("is.net_loss.9m2026", 5e9, "is.9m2026: pre-tax loss - taxes = net loss"),
        ("commit.total", 10e9, "the five parts of committed spend add up to the total"),
        ("commit.leases_not_commenced", -3e9, "the five parts of committed spend"),
        ("balance.cash.actual", 2e9, "cash equivalents + short-term investments = total"),
        ("shares.total_after", 1000, "share classes add up to all shares outstanding"),
        ("notes.shares_remaining", 1, "Amazon notes: converted + remaining = total issuable"),
        ("obligations.total.2028", 5e6, "obligations table, column 2028: rows add up"),
        ("metrics.revenue_growth_q3", 23, "stated revenue growth matches the table"),
        ("offering.price_high", 1, "assumed price is the midpoint of the range"),
    ],
)
def test_a_wrong_figure_is_refused(
    facts: Facts, tampered: Tamper, fact_id: str, delta: float, expected: str
) -> None:
    broken = tampered({fact_id: facts.num(fact_id) + delta})
    with pytest.raises(ReconciliationError) as error:
        assert_consistent(broken)
    assert expected in str(error.value)
    assert any(not c.ok for c in run_checks(broken))
