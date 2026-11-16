"""Real-browser smoke test: the dashboard used the way a person uses it.

Run:  pytest -m e2e
Against a deployed site:  E2E_BASE_URL=https://example.org pytest -m e2e
Keep screenshots:  E2E_SHOTS=devlog/img pytest -m e2e
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Browser, BrowserContext, Page, ViewportSize, expect, sync_playwright

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parent.parent.parent
PANELS = {"v": "value", "e": "ev", "c": "contracts", "g": "growth", "l": "losses"}
PHONE: ViewportSize = {"width": 390, "height": 844}
DESKTOP: ViewportSize = {"width": 1280, "height": 900}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    external = os.environ.get("E2E_BASE_URL")
    if external:
        yield external.rstrip("/")
        return
    port = _free_port()
    env = {**os.environ, "IPO_PORT": str(port), "IPO_RELEASE": "e2e"}
    process = subprocess.Popen(
        [sys.executable, "-m", "ipo_monitor"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"{url}/health", timeout=1):  # noqa: S310
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("the service did not start")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch()
        yield chromium
        chromium.close()


def _open(context: BrowserContext, url: str) -> tuple[Page, list[str]]:
    page = context.new_page()
    errors: list[str] = []
    page.on(
        "console", lambda message: errors.append(message.text) if message.type == "error" else None
    )
    page.on("pageerror", lambda error: errors.append(str(error)))
    response = page.goto(url + "/")
    assert response is not None
    assert response.status == 200
    return page, errors


def _shot(page: Page, name: str, *, full: bool = False) -> None:
    folder = os.environ.get("E2E_SHOTS")
    if folder:
        Path(folder).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(folder) / f"{name}.png"), full_page=full)


def _serious(page: Page) -> list[str]:
    violations = Axe().run(page).response["violations"]
    return [
        f"{v['id']}: {v['help']} ({len(v['nodes'])} nodes)"
        for v in violations
        if v.get("impact") in {"serious", "critical"}
    ]


def test_desktop_reading_and_keyboard(browser: Browser, base_url: str) -> None:
    context = browser.new_context(viewport=DESKTOP)
    page, errors = _open(context, base_url)

    assert "ANT IPO Monitor" in page.title()
    assert page.get_by_text("not investment advice").first.is_visible()
    footer_link = page.get_by_role("link", name="Built with the Loop0 Method")
    assert footer_link.get_attribute("href") == "https://agmgd-on-loop0-22c0a8ea.fly.dev/"
    assert page.get_by_text("awaiting listing").is_visible()
    _shot(page, "loop-001-desktop")
    _shot(page, "loop-001-desktop-full", full=True)

    # One key per panel, no mouse.
    for key, panel in PANELS.items():
        page.keyboard.press(key)
        assert page.evaluate("document.activeElement.id") == panel
        assert page.locator(f"#{panel}").is_visible()

    # A filed number: the card quotes the filing and links to it.
    page.keyboard.press("g")
    number = page.locator('button[data-ref="q.revenue.2026q3"]').first
    number.click()
    card = page.locator("#src-q-revenue-2026q3")
    assert card.is_visible()
    assert "FILED" in card.inner_text()
    assert "$16,956" in card.inner_text()
    assert "p. 164" in card.inner_text()
    href = card.get_by_role("link").get_attribute("href")
    assert href is not None
    assert href.startswith("https://www.sec.gov/Archives/edgar/data/2130357/")
    _shot(page, "loop-001-source-filed")
    page.keyboard.press("Escape")
    assert not card.is_visible()

    # A calculated number: the card shows the formula and its inputs.
    page.keyboard.press("v")
    page.locator('#value .tile-key button[data-ref="ev.enterprise_value.mid"]').click()
    card = page.locator("#src-ev-enterprise-value-mid")
    assert card.is_visible()
    text = card.inner_text()
    assert "CALC" in text
    assert "diluted value" in text
    assert "cash after the offering" in text
    _shot(page, "loop-001-source-calc")
    page.keyboard.press("Escape")

    # Keyboard only: focus a number and open its card with Enter.
    first = page.locator("main button.n").first
    first.focus()
    page.keyboard.press("Enter")
    assert page.locator("[popover]:popover-open").count() == 1
    page.keyboard.press("Escape")
    assert page.locator("[popover]:popover-open").count() == 0

    assert _serious(page) == []
    assert errors == []
    context.close()


def test_phone_first_screen(browser: Browser, base_url: str) -> None:
    context = browser.new_context(
        viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True
    )
    page, errors = _open(context, base_url)

    # Without scrolling: the value at the price range, outstanding and diluted, and the EV.
    for ref in (
        "value.mcap_out.low",
        "value.mcap_out.high",
        "value.equity_diluted.low",
        "value.equity_diluted.high",
        "ev.enterprise_value.mid",
    ):
        box = page.locator(f'#value .tiles button[data-ref="{ref}"]').bounding_box()
        assert box is not None, ref
        assert box["y"] >= 0, ref
        assert box["y"] + box["height"] <= PHONE["height"], f"{ref} is below the first screen"
    assert page.evaluate("window.scrollY") == 0
    _shot(page, "loop-001-phone")

    # No sideways scrolling of the page itself.
    assert page.evaluate("document.documentElement.scrollWidth") <= PHONE["width"]

    # One tap on a panel name, one tap on a number.
    page.get_by_role("link", name="c contracts").tap()
    expect(page.locator("#contracts-h")).to_be_in_viewport()
    page.locator('#contracts button[data-ref="commit.total"]').first.tap()
    card = page.locator("#src-commit-total")
    assert card.is_visible()
    assert "$900.9 billion" in card.inner_text()
    _shot(page, "loop-001-phone-source")

    assert _serious(page) == []
    assert errors == []
    context.close()


def test_works_without_javascript(browser: Browser, base_url: str) -> None:
    context = browser.new_context(viewport=DESKTOP, java_script_enabled=False)
    page, _ = _open(context, base_url)
    assert page.locator("main button.n").count() >= 100
    assert page.locator('button[data-ref="commit.total"]').first.inner_text().startswith("$900.9B")
    # The source card still opens: it relies on the browser, not on our script.
    page.locator('button[data-ref="rpo.total"]').first.click()
    assert page.locator("#src-rpo-total").is_visible()
    context.close()


def test_loads_fast(browser: Browser, base_url: str) -> None:
    context = browser.new_context(viewport=DESKTOP)
    page = context.new_page()
    begin = time.perf_counter()
    page.goto(base_url + "/", wait_until="load")
    elapsed = time.perf_counter() - begin
    assert elapsed < 1.0, f"page load took {elapsed:.2f}s"
    context.close()
