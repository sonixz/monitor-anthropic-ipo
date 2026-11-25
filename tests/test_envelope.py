"""The envelope is the owner's real money (D-056): positions come from the orders they report."""

from __future__ import annotations

import pytest

from ipo_monitor.scan.bars import Series
from ipo_monitor.scan.portfolio import Book, Fill, held_of, simulate
from tests.test_portfolio import decision, flat_then, rules, series, signal


def fill(day: str, side: str, shares: int, price: float, symbol: str = "X") -> Fill:
    return Fill.model_validate(
        {"date": day, "symbol": symbol, "side": side, "shares": shares, "price": price}
    )


def run(
    rows: list[tuple[float, float, float, float]], fills: list[Fill] | None
) -> tuple[Book, Series]:
    """A buy advised after session 20 (index 19); quiet sessions give stop 96, target 106."""
    x = series("X", flat_then(rows))
    day = x.bars[19].date
    book, refused = simulate(
        rules(),
        {day: signal("X", day=day)},
        {f"{day}.json": decision(day, [{"symbol": "X", "action": "buy", "reason": "r"}])},
        {"X": x},
        {"X": "Tech"},
        fills,
    )
    assert refused == []
    return book, x


def test_a_reported_buy_opens_the_position_at_the_price_paid() -> None:
    rows = [(101.0, 102.0, 100.0, 101.0), (101.0, 103.0, 100.0, 102.0)]
    book, _ = run(rows, [fill(series("X", flat_then(rows)).bars[20].date, "buy", 3, 101.5)])
    assert book.real
    one = book.open_positions[0]
    assert (one.entry, one.shares, one.stop, one.target) == (101.5, 3, 96.0, 106.0)
    assert one.sessions == 2
    # 4,000 − 3 × 101.5 = 3,695.50 in cash; 3 × 102 invested at the last close.
    assert book.cash == pytest.approx(3695.5)
    assert book.metrics().equity == pytest.approx(3695.5 + 306)
    assert book.pending == []


def test_advice_not_followed_opens_nothing() -> None:
    book, _ = run([(101.0, 102.0, 100.0, 101.0)], [])
    assert book.positions == []
    assert book.cash == pytest.approx(4000)
    # The same files without a ledger: the simulation fills the advice at the open.
    simulated, _ = run([(101.0, 102.0, 100.0, 101.0)], None)
    assert not simulated.real
    assert simulated.open_positions[0].entry == 101.0


def test_a_target_reached_is_advice_to_sell_until_the_sale_is_reported() -> None:
    rows = [(101.0, 102.0, 100.0, 101.0), (102.0, 107.0, 101.0, 106.5)]
    days = [b.date for b in series("X", flat_then(rows)).bars]
    book, _ = run(rows, [fill(days[20], "buy", 3, 101.5)])
    one = book.open_positions[0]
    assert one.reached == ("target", days[21])
    assert [(p.symbol, why) for p, why in book.exits] == [("X", "target")]
    # Reported sold the next session: closed at the price got, named by the target.
    rows.append((106.0, 106.5, 105.0, 105.5))
    days = [b.date for b in series("X", flat_then(rows)).bars]
    book, _ = run(rows, [fill(days[20], "buy", 3, 101.5), fill(days[22], "sell", 3, 106.2)])
    closed = book.closed_positions[0]
    assert (closed.exit, closed.exited, closed.why_exit) == (106.2, days[22], "target")
    assert closed.pnl == pytest.approx((106.2 - 101.5) * 3)
    assert book.cash == pytest.approx(4000 + (106.2 - 101.5) * 3)
    assert book.exits == []


def test_a_stop_reached_is_flagged_not_filled() -> None:
    rows = [(101.0, 102.0, 100.0, 101.0), (97.0, 97.5, 95.0, 95.5)]
    days = [b.date for b in series("X", flat_then(rows)).bars]
    book, _ = run(rows, [fill(days[20], "buy", 3, 101.5)])
    one = book.open_positions[0]
    assert one.reached == ("stop", days[21])
    assert one.exited is None
    assert book.exits == []  # a stop market sells by itself: the page asks for the sale


def test_held_shows_only_the_owner_s_positions_with_their_age() -> None:
    from ipo_monitor.scan.portfolio import Holding

    rows = [(101.0, 102.0, 100.0, 101.0), (101.0, 103.0, 100.0, 102.0)]
    days = [b.date for b in series("X", flat_then(rows)).bars]
    book, _ = run(rows, [fill(days[20], "buy", 3, 101.5)])
    real = [Holding("X", 3, 101.5, 102.0, 96.0, 106.0, 100.0, days[20])]
    held = held_of(book, real)["X"]
    assert (held.real_shares, held.sim_shares, held.since, held.sessions) == (3, 0, days[20], 2)
