"""The private portal: the gate, the login, the session, uploads of result files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ipo_monitor.auth import LIFETIME, MAX_FAILURES, Gate, bearer
from ipo_monitor.config import Settings
from ipo_monitor.web import create_app

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
USER, PASSWORD, TOKEN = "owner", "a long test passphrase", "test-upload-token"


def test_the_session_cookie() -> None:
    gate = Gate(USER, PASSWORD)
    cookie = gate.issue(now=1000)
    assert gate.valid(cookie, now=1001)
    assert not gate.valid(cookie, now=1000 + LIFETIME + 1)  # expired
    expires, _, signature = cookie.partition(".")
    assert not gate.valid(f"{int(expires) + 999}.{signature}", now=1001)  # tampered
    assert not Gate(USER, "another password").valid(cookie, now=1001)  # password changed
    assert not Gate("", "").valid(cookie)  # no account: nothing is valid
    assert PASSWORD not in repr(gate)


def test_wrong_logins_are_slowed_down() -> None:
    gate = Gate(USER, PASSWORD)
    assert gate.login(USER, PASSWORD, now=0) is None
    assert gate.login(USER, "nope", now=1) == "Wrong username or password."
    for i in range(MAX_FAILURES - 1):
        gate.login(USER, "nope", now=2 + i)
    assert "Too many attempts" in (gate.login(USER, PASSWORD, now=20) or "")  # even the right one
    assert gate.login(USER, PASSWORD, now=20 + 301) is None


def test_bearer() -> None:
    assert bearer(f"Bearer {TOKEN}", TOKEN)
    assert not bearer("Bearer wrong", TOKEN)
    assert not bearer(f"Bearer {TOKEN}", "")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    for folder in ("signals", "decisions"):
        (tmp_path / folder).mkdir()
    settings = Settings(
        "127.0.0.1",
        8000,
        ROOT / "data" / "facts",
        "test",
        "info",
        scan=f"file:{FIX / 'scan' / '2026-11-20'}",
        signals="off",
        scan_candidates=FIX / "scan" / "candidates-tsx60.json",
        site_user=USER,
        site_password=PASSWORD,
        upload_token=TOKEN,
        data_dir=tmp_path,
        ledger=tmp_path / "ledger.json",
    )
    app = create_app(settings)
    test = TestClient(app, base_url="https://testserver")
    test.__enter__()
    app.state.scanner.start()
    app.state.scanner.on_change(app.state.scanner.board)
    return test


def sign_in(client: TestClient) -> None:
    answer = client.post(
        "/login",
        content=f"username={USER}&password=a+long+test+passphrase&next=/portfolio",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert answer.status_code == 303
    assert answer.headers["location"] == "/portfolio"


def test_every_page_is_behind_the_login(client: TestClient) -> None:
    for path in ("/", "/portfolio", "/ant", "/scan/dossier.json", "/stats"):
        answer = client.get(path, follow_redirects=False)
        assert answer.status_code == 303, path
        assert answer.headers["location"].startswith("/login"), path
    assert client.post("/seen").status_code == 401
    assert client.get("/health").status_code == 200  # no result in it
    assert client.get("/static/app.css").status_code == 200
    page = client.get("/login")
    assert 'name="username"' in page.text
    assert 'type="password"' in page.text


def test_signing_in_and_out(client: TestClient) -> None:
    wrong = client.post(
        "/login",
        content="username=owner&password=nope&next=/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert wrong.status_code == 401
    assert "Wrong username or password." in wrong.text
    sign_in(client)
    home = client.get("/")
    assert home.status_code == 200
    assert "ANTIPO" in home.text
    assert home.headers["cache-control"] == "private, no-store"
    assert client.get("/portfolio").status_code == 200
    client.get("/logout")
    assert client.get("/", follow_redirects=False).status_code == 303


def test_next_never_leaves_the_site(client: TestClient) -> None:
    answer = client.post(
        "/login",
        content=f"username={USER}&password=a+long+test+passphrase&next=//evil.example",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert answer.headers["location"] == "/"


def test_uploads_are_checked_then_stored_on_the_server(client: TestClient, tmp_path: Path) -> None:
    good = json.loads((FIX / "signals" / "2026-11-20.json").read_text())
    url = "/api/upload/signals/2026-11-20.json"
    assert client.put(url, json=good).status_code == 401  # no token
    auth = {"Authorization": f"Bearer {TOKEN}"}
    bad = {**good, "signals": [{**good["signals"][0], "summary": "Up 5% today."}]}
    refused = client.put(url, json=bad, headers=auth)
    assert refused.status_code == 422
    assert any("typed by hand" in p for p in refused.json()["problems"])
    assert not (tmp_path / "signals" / "2026-11-20.json").exists()
    assert client.put(url, json=good, headers=auth).json() == {"stored": "2026-11-20.json"}
    assert (tmp_path / "signals" / "2026-11-20.json").exists()
    sign_in(client)
    assert "TEST DATA. Pulled back" in client.get("/").text  # on the page at once
    decisions = json.loads((FIX / "decisions" / "2026-11-20.json").read_text())
    stored = client.put("/api/upload/decisions/2026-11-20.json", json=decisions, headers=auth)
    assert stored.json() == {"stored": "2026-11-20.json"}
    assert "buy" in client.get("/portfolio").text
    ledger = {"schema": "antipo.ledger/1", "real": True, "fills": []}
    assert (
        client.put("/api/upload/ledger/ledger.json", json=ledger, headers=auth).status_code == 200
    )
    assert client.put("/api/upload/other/x.json", json={}, headers=auth).status_code == 404
