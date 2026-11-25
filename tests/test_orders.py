"""The owner reports an order on the page (D-057): the envelope follows it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ipo_monitor.scan.portfolio import Fill, Holding, order_from_form
from tests.test_levels import TOKEN, portal

# 1 RY bought at 264.10 on Nov 23; the last close read is Nov 20's, 263.05.
HELD = [Holding("RY", 1, 264.1, 263.05, 252.69, 278.58, 263.05, "2026-11-23")]
KNOWN = [Fill(date="2026-11-23", symbol="RY", side="buy", shares=1, price=264.1)]


def read(**fields: str) -> Fill | str:
    typed = {"side": "sell", "symbol": "RY", "shares": "1", "price": "270", "date": "2026-11-24"}
    typed.update(fields)
    return order_from_form(
        {k: [v] for k, v in typed.items()},
        held=HELD,
        prices={"RY": 263.05, "TD": 80.0},
        cash=3735.9,
        start="2026-11-20",
        today="2026-11-24",
        known=KNOWN,
    )


def test_a_sale_typed_the_way_people_type_it() -> None:
    found = read(symbol=" ry.to ", price="$270,15")
    assert found == Fill(date="2026-11-24", symbol="RY", side="sell", shares=1, price=270.15)


def test_a_buy_of_a_stock_of_the_scanner() -> None:
    found = read(side="buy", symbol="TD", shares="10", price="80.5")
    assert isinstance(found, Fill)
    assert (found.side, found.symbol, found.shares, found.price) == ("buy", "TD", 10, 80.5)


@pytest.mark.parametrize(
    ("fields", "problem"),
    [
        ({"side": ""}, "choose bought or sold"),
        ({"symbol": ""}, "name the stock"),
        ({"symbol": "TD"}, "TD is not held"),
        ({"side": "buy", "symbol": "ZZZ"}, "ZZZ is not a stock of the scanner"),
        ({"shares": "1.5"}, "'1.5' is not a number of shares"),
        ({"shares": "0"}, "'0' is not a number of shares"),
        ({"shares": "2"}, "RY: 2 shares sold, 1 held"),
        ({"price": ""}, "give the price you got"),
        ({"price": "abc"}, "'abc' is not a price"),
        ({"price": "2700"}, "2700.00 is too far from the last price, 263.05"),
        ({"date": "24/11/2026"}, "'24/11/2026' is not a date"),
        ({"date": "2026-11-25"}, "the date is after today"),
        ({"date": "2026-11-22"}, "the date is before the position was opened"),
        (
            {"side": "buy", "symbol": "TD", "shares": "50", "price": "80"},
            "50 × 80.00 is more than the cash left, 3735.90",
        ),
        (
            {"side": "buy", "shares": "1", "price": "264.1", "date": "2026-11-23"},
            "this order is already reported",
        ),
    ],
)
def test_typos_are_refused_with_a_reason(fields: dict[str, str], problem: str) -> None:
    assert read(**fields) == problem


# -- on the site --------------------------------------------------------------------


def report(client: TestClient, **fields: str) -> Any:
    typed = {"side": "sell", "symbol": "RY", "shares": "1", "price": "270", "date": "2026-11-23"}
    typed.update(fields)
    return client.post(
        "/orders",
        content="&".join(f"{k}={v}" for k, v in typed.items()),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def fills(tmp_path: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = json.loads((tmp_path / "ledger.json").read_text("utf-8"))["fills"]
    return found


def test_the_form_is_on_the_page(tmp_path: Path) -> None:
    page = portal(tmp_path).get("/portfolio").text
    form = page[page.index('id="report"') : page.index('id="metrics"')]
    assert 'action="/orders"' in form
    assert 'value="2026-11-23"' in form  # today, Toronto
    assert '<option value="RY">' in form


def test_a_reported_sale_closes_the_position(tmp_path: Path) -> None:
    client = portal(tmp_path)
    answer = report(client, price="270,00")
    assert answer.status_code == 303
    assert answer.headers["location"] == "/portfolio?osaved=sell%201%20RY%20at%20270.00#report"
    assert fills(tmp_path)[-1] == {
        "date": "2026-11-23",
        "symbol": "RY",
        "side": "sell",
        "shares": 1,
        "price": 270.0,
    }
    page = client.get(answer.headers["location"]).text
    assert "reported: <span data-label>sell 1 RY at 270.00</span>" in page
    assert 'id="real-h"' not in page  # nothing held any more
    results = page[page.index('id="metrics"') : page.index('id="rules"')]
    # 270.00 − 264.10 = +5.90 on the one closed trade.
    assert "Closed trades" in results
    assert "+$5.90" in results
    # The envelope counts the sale at once: 4,000 + 5.90 = 4,005.90, +0.1%.
    glance = page[page.index('aria-label="The envelope at a glance"') :]
    assert "$4,005.90" in glance[:600]
    assert "+0.1%" in results
    # The scanner no longer marks RY as held.
    assert '<span class="held">HELD</span>' not in client.get("/").text


def test_a_reported_buy_adds_to_the_position(tmp_path: Path) -> None:
    client = portal(tmp_path)
    assert report(client, side="buy", price="266.10").status_code == 303
    page = client.get("/portfolio").text
    real = page[page.index('id="real"') : page.index('id="broker-h"')]
    # 2 shares at (264.10 + 266.10) ÷ 2 = 265.10.
    assert "<td><span data-label>2</span></td><td><span data-label>$265.10</span></td>" in real


def test_a_refused_order_changes_nothing(tmp_path: Path) -> None:
    client = portal(tmp_path)
    before = (tmp_path / "ledger.json").read_bytes()
    answer = report(client, shares="3")
    assert "orefused=" in answer.headers["location"]
    assert (tmp_path / "ledger.json").read_bytes() == before
    page = client.get(answer.headers["location"]).text
    assert "not reported: <span data-label>RY: 3 shares sold, 1 held</span>" in page


def test_orders_need_the_login(tmp_path: Path) -> None:
    client = portal(tmp_path)
    client.cookies.clear()
    before = (tmp_path / "ledger.json").read_bytes()
    assert report(client).status_code == 401
    assert (tmp_path / "ledger.json").read_bytes() == before


def test_an_upload_never_drops_an_order_reported_on_the_page(tmp_path: Path) -> None:
    client = portal(tmp_path)
    old = json.loads((tmp_path / "ledger.json").read_text("utf-8"))
    report(client)
    bearer = {"Authorization": f"Bearer {TOKEN}"}
    answer = client.put("/api/upload/ledger/ledger.json", json=old, headers=bearer)
    assert answer.status_code == 422
    assert "the server holds sell 1 RY on 2026-11-23" in answer.json()["problems"][0]
    assert len(fills(tmp_path)) == 2
    # The copy downloaded from the server, with an order added, is accepted.
    copy = client.get("/api/upload/ledger", headers=bearer)
    assert copy.status_code == 200
    newer = copy.json()
    newer["fills"].append(
        {"date": "2026-11-23", "symbol": "RY", "side": "buy", "shares": 1, "price": 265.0}
    )
    answer = client.put("/api/upload/ledger/ledger.json", json=newer, headers=bearer)
    assert answer.json() == {"stored": "ledger.json"}


def test_the_ledger_copy_needs_the_token(tmp_path: Path) -> None:
    client = portal(tmp_path)
    client.cookies.clear()
    assert client.get("/api/upload/ledger").status_code == 401
    wrong = {"Authorization": "Bearer not-the-token"}
    assert client.get("/api/upload/ledger", headers=wrong).status_code == 401
