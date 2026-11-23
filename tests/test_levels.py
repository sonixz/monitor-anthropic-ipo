"""The owner's levels at the broker, and stocks already held (Loop 016)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ipo_monitor.config import Settings
from ipo_monitor.scan.board import TORONTO
from ipo_monitor.scan.portfolio import (
    BrokerLevel,
    Holding,
    LevelsFile,
    held_of,
    levels_from_form,
    read_levels,
    write_levels,
)
from ipo_monitor.scan.session import Tick, live
from ipo_monitor.web import create_app

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
TEST = FIX / "session" / "2026-11-23-TEST"  # invented answers, named as test data
USER, PASSWORD, TOKEN = "owner", "a long test passphrase", "a-test-upload-token"


def holding(**mine: float) -> Holding:
    """1 DOL at 220.48; the plan's stop 208.23 and target 229.18; last close 216.61."""
    level = BrokerLevel.model_validate(mine) if mine else None
    return Holding("DOL", 1, 220.48, 216.61, 208.23, 229.18, 216.61, "2026-11-23", level)


def form(**fields: str) -> dict[str, list[str]]:
    return {f"{key}_DOL": [value] for key, value in fields.items()}


# -- reading the form ---------------------------------------------------------------


def test_levels_typed_the_way_people_type_them() -> None:
    found = levels_from_form(
        form(stop="208,10", target="$229.00", near=" 210.5 "), [holding()], "t"
    )
    assert found == {"DOL": BrokerLevel(stop=208.10, target=229.0, near=210.5, updated="t")}


def test_empty_fields_follow_the_plan() -> None:
    assert levels_from_form(form(stop="", target="", near=""), [holding()], "t") == {}
    found = levels_from_form(form(stop="207.5"), [holding()], "t")
    assert isinstance(found, dict)
    h = holding(stop=207.5)
    assert (h.stop_used, h.target_used, h.near_used) == (207.5, 229.18, None)


@pytest.mark.parametrize(
    ("fields", "problem"),
    [
        ({"stop": "abc"}, "'abc' is not a price"),
        ({"stop": "208.2.3"}, "is not a price"),
        ({"stop": "-5"}, "is not a price"),
        ({"stop": "2082.30"}, "too far from the last price"),  # a missing decimal point
        ({"target": "100"}, "too far from the last price"),
        ({"stop": "230", "target": "229"}, "the stop must be below the target alert"),
        ({"stop": "230"}, "the stop must be below the target alert"),  # against the plan's target
        ({"near": "207"}, "the near-stop alert must be above the stop"),
        ({"near": "229.5"}, "the near-stop alert must be below the target alert"),
    ],
)
def test_typos_are_refused_with_a_reason(fields: dict[str, str], problem: str) -> None:
    found = levels_from_form(form(**fields), [holding()], "t")
    assert isinstance(found, str)
    assert found.startswith("DOL")
    assert problem in found


def test_the_file_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "levels.json"
    assert read_levels(path) == LevelsFile()
    saved = LevelsFile(levels={"DOL": BrokerLevel(stop=208.1, updated="t")})
    write_levels(path, saved)
    assert read_levels(path) == saved
    path.write_text("not json", "utf-8")
    assert read_levels(path) == LevelsFile()  # unreadable: the plan applies


# -- what is held --------------------------------------------------------------------


def test_held_names_the_levels_in_force() -> None:
    held = held_of(None, [holding(stop=207.5)])
    one = held["DOL"]
    assert (one.real_shares, one.real_cost, one.sim_shares) == (1, 220.48, 0)
    assert (one.stop, one.target, one.yours) == (207.5, 229.18, True)
    assert held_of(None, [holding()])["DOL"].yours is False


# -- the session panel with the owner's near-stop alert ------------------------------


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=TORONTO)


def test_near_stop_by_atr_and_by_alert() -> None:
    def flag(price: float, near: float | None) -> str:
        tick = Tick(
            "DOL.TO", price, int(at("2026-11-23 11:15").timestamp()), price, price, 9, "t", ""
        )
        return live(
            "DOL", "real", tick=tick, entry=220.48, stop=208.23, target=229.18, atr=4.19,
            last_close=216.61, now=at("2026-11-23 11:20"), near=near,
        ).flag  # fmt: skip

    # Half an ATR: 208.23 + 2.095 = 210.325.
    assert flag(210.30, None) == "near stop"
    assert flag(211.00, None) == ""
    # The owner's alert at 212: at or below it counts, and it replaces the ATR rule.
    assert flag(211.00, 212.0) == "near stop"
    assert flag(212.50, 212.0) == ""
    assert flag(210.30, 209.0) == ""


# -- the page ------------------------------------------------------------------------


def portal(tmp_path: Path, now: str = "2026-11-23T11:20:00-05:00") -> TestClient:
    ledger = {
        "schema": "antipo.ledger/1",
        "real": True,
        "fills": [
            {"date": "2026-11-23", "symbol": "RY", "side": "buy", "shares": 1, "price": 264.1}
        ],
    }
    (tmp_path / "ledger.json").write_text(json.dumps(ledger), "utf-8")
    settings = Settings(
        "127.0.0.1",
        8000,
        ROOT / "data" / "facts",
        "test",
        "info",
        scan=f"file:{FIX / 'scan' / '2026-11-20'}",
        signals=f"dir:{FIX / 'signals'}",
        scan_candidates=FIX / "scan" / "candidates-tsx60.json",
        site_user=USER,
        site_password=PASSWORD,
        upload_token=TOKEN,
        data_dir=tmp_path,
        ledger=tmp_path / "ledger.json",
        today="2026-11-23",
        session=f"file:{TEST}",
        now=now,
    )
    app = create_app(settings)
    client = TestClient(app, base_url="https://testserver")
    app.state.scanner.start()
    app.state.scanner.on_change(app.state.scanner.board)
    app.state.session.step()
    client.post(
        "/login",
        content=f"username={USER}&password=a+long+test+passphrase&next=/portfolio",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return client


def save(client: TestClient, **fields: str) -> Any:
    body = "&".join(f"{k}_RY={v}" for k, v in fields.items())
    return client.post(
        "/levels",
        content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def test_the_plan_applies_until_levels_are_saved(tmp_path: Path) -> None:
    page = portal(tmp_path).get("/portfolio").text
    assert "At the broker" in page
    assert "change your levels" in page
    assert '<span class="yours">YOURS</span> <span class="pl">' not in page
    assert "plan <span data-label>$252.69</span>" in page  # the plan's stop for RY


def test_saved_levels_show_as_yours_and_drive_the_session(tmp_path: Path) -> None:
    client = portal(tmp_path)
    # The recorded session: price 279.10, high 279.40, low 268.20.
    answer = save(client, stop="260,00", target="285", near="280")
    assert answer.status_code == 303
    assert answer.headers["location"] == "/portfolio?lsaved=1#real"
    stored = json.loads((tmp_path / "levels.json").read_text("utf-8"))
    assert stored["levels"]["RY"]["stop"] == 260.0
    page = client.get("/portfolio?lsaved=1").text
    assert "levels saved" in page
    assert '<span class="yv"><span data-label>$260.00</span></span> <span class="yours">' in page
    assert "plan <span data-label>$252.69</span>" in page  # the plan stays beside it
    # The plan's target (278.58) was passed by the high; the owner's (285) was not.
    assert "▲ target reached" not in page
    assert "! near stop" in page  # 279.10 at or below the owner's alert at 280
    # The scanner shows the stock as held, with the owner's stop.
    home = client.get("/").text
    assert '<span class="held">HELD</span>' in home


def test_a_refused_level_changes_nothing(tmp_path: Path) -> None:
    client = portal(tmp_path)
    assert save(client, stop="260").status_code == 303
    before = (tmp_path / "levels.json").read_bytes()
    answer = save(client, stop="2600")
    assert "lrefused=" in answer.headers["location"]
    assert (tmp_path / "levels.json").read_bytes() == before
    page = client.get(answer.headers["location"]).text
    assert "not saved" in page
    assert "too far from the last price" in page


def test_an_upload_of_the_ledger_keeps_the_levels(tmp_path: Path) -> None:
    client = portal(tmp_path)
    save(client, stop="260")
    ledger = json.loads((tmp_path / "ledger.json").read_text("utf-8"))
    answer = client.put(
        "/api/upload/ledger/ledger.json",
        json=ledger,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert answer.json() == {"stored": "ledger.json"}
    assert read_levels(tmp_path / "levels.json").levels["RY"].stop == 260.0


def test_levels_need_the_login(tmp_path: Path) -> None:
    client = portal(tmp_path)
    client.cookies.clear()
    assert save(client, stop="260").status_code == 401
    assert not (tmp_path / "levels.json").exists()
