"""Calculations, checked against arithmetic done by hand from the filing."""

from __future__ import annotations

import math

import pytest

from ipo_monitor.calc import Calc
from ipo_monitor.facts import Facts

B = 1e9


def value(calcs: dict[str, Calc], calc_id: str) -> float:
    return calcs[calc_id].value


def test_value_of_the_shares_outstanding(calcs: dict[str, Calc]) -> None:
    assert value(calcs, "value.shares_out.mid") == 13_086_672_593
    assert value(calcs, "value.mcap_out.mid") == pytest.approx(13_086_672_593 * 74)
    # The private placement is a fixed $26.0B, so its share count moves with the price.
    low = 13_086_672_593 - 351_351_348 + 26e9 / 70
    high = 13_086_672_593 - 351_351_348 + 26e9 / 78
    assert value(calcs, "value.shares_out.low") == pytest.approx(low)
    assert value(calcs, "value.mcap_out.high") == pytest.approx(high * 78)
    assert round(value(calcs, "value.mcap_out.high") / B) == 1019


def test_diluted_value_counts_what_is_owed_or_granted(calcs: dict[str, Calc]) -> None:
    owed = (
        1_563_617_444 + 1_774_342_693 + 1_026_660_010 + 47_041_287 + 561_963 + 848_882 + 27_991_850
    )
    assert value(calcs, "value.owed_shares") == owed
    assert value(calcs, "value.shares_diluted.mid") == 13_086_672_593 + owed
    assert value(calcs, "value.equity_diluted.mid") == pytest.approx((13_086_672_593 + owed) * 74)


def test_press_basis_reproduces_the_reported_figures(calcs: dict[str, Calc], facts: Facts) -> None:
    assert round(value(calcs, "value.headline.high") / B) == 1405
    assert value(calcs, "value.headline.high") == pytest.approx(
        facts.num("press.cnbc.fully_diluted_high"), rel=1e-4
    )
    assert value(calcs, "value.mcap_out.high") == pytest.approx(
        facts.num("press.reuters.outstanding_high"), rel=2e-3
    )


def test_enterprise_value_bridge(calcs: dict[str, Calc]) -> None:
    equity = value(calcs, "value.equity_diluted.mid")
    assert value(calcs, "ev.cash_after.mid") == 212_684e6
    assert value(calcs, "ev.cash_after.low") == pytest.approx(212_684e6 - 4 * 793e6)
    assert value(calcs, "ev.cash_after.high") == pytest.approx(212_684e6 + 4 * 793e6)
    assert value(calcs, "ev.option_proceeds") == pytest.approx(1_774_342_693 * 2.91)
    expected = equity - 212_684e6 - 1_774_342_693 * 2.91
    assert value(calcs, "ev.enterprise_value.mid") == pytest.approx(expected)
    assert value(calcs, "ev.multiple.run_rate") == pytest.approx(expected / 81e9)
    assert value(calcs, "ev.multiple.ttm") == pytest.approx(expected / 35_282e6)


def test_cash_after_the_offering_is_explained(calcs: dict[str, Calc]) -> None:
    explained = 131_845e6 + 84.6e9 - value(calcs, "ev.rsu_tax_paid")
    assert explained == pytest.approx(value(calcs, "ev.cash_after.mid"), abs=100e6)


def test_growth(calcs: dict[str, Calc]) -> None:
    assert value(calcs, "growth.qoq.2026q3") == pytest.approx((16_956 / 11_555 - 1) * 100)
    assert round(value(calcs, "growth.yoy.2026q3")) == 1127
    assert value(calcs, "growth.revenue_per_compute.2026q3") == pytest.approx(16_956 / 9_863)
    assert value(calcs, "growth.operating_margin.2026q2") == pytest.approx(974 / 11_555 * 100)
    assert value(calcs, "growth.ttm_revenue") == (2_040 + 4_731 + 11_555 + 16_956) * 1e6
    assert value(calcs, "growth.q3_annualized") == 16_956e6 * 4
    assert value(calcs, "growth.run_rate_sep30") == 71e9
    assert "growth.qoq.2025q1" not in calcs
    assert "growth.yoy.2025q4" not in calcs


def test_contracts(calcs: dict[str, Calc]) -> None:
    assert value(calcs, "contracts.after_2030") == pytest.approx(900.9e9 - 451.6e9)
    assert value(calcs, "contracts.rest_before_2031") == pytest.approx(451.6e9 - 70.7e9)
    assert value(calcs, "contracts.signed_after_sep30") == pytest.approx(105.7e9 + 6.6e9)
    assert value(calcs, "contracts.rpo_next_12m") == pytest.approx(13.8e9 * 0.75)
    assert value(calcs, "contracts.owed_vs_signed") == pytest.approx(900.9 / 13.8)
    assert value(calcs, "contracts.years_of_run_rate") == pytest.approx(900.9 / 81)
    assert value(calcs, "contracts.cash_cover_12m") == pytest.approx(212.684 / 70.7)


def test_losses_split_adds_up(calcs: dict[str, Calc]) -> None:
    assert value(calcs, "losses.other_net") == pytest.approx((2_359 - 10_397 - 417) * 1e6)
    shares = sum(value(calcs, f"losses.share.{k}") for k in ("fair_value", "operating", "other"))
    assert shares == pytest.approx(100)
    assert value(calcs, "losses.share.fair_value") == pytest.approx(94_324 / 104_039 * 100)


def test_every_input_is_traceable(calcs: dict[str, Calc], facts: Facts) -> None:
    for calc in calcs.values():
        assert calc.title, calc.id
        assert calc.formula, calc.id
        assert calc.terms, calc.id
        assert math.isfinite(calc.value), calc.id
        for term in calc.terms:
            if term.ref is not None:
                assert term.ref in calcs or term.ref in facts, f"{calc.id}: {term.ref}"
