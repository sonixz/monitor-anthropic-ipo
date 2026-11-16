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
PHONE_WIDTHS = (360, 390, 430)

# Everything that must stay inside the screen and inside its chart.
OVERFLOW = """() => {
  const wide = [];
  document.querySelectorAll('main *, header *, nav *, footer *').forEach((el) => {
    const r = el.getBoundingClientRect();
    const out = r.right > innerWidth + 1 || r.left < -1;
    if (r.width && out) wide.push(el.tagName + '.' + el.className);
  });
  const cut = [];
  document.querySelectorAll('svg.chart-svg').forEach((svg) => {
    const box = svg.getBoundingClientRect();
    svg.querySelectorAll('text').forEach((text) => {
      const r = text.getBoundingClientRect();
      const across = r.left < box.left - 1 || r.right > box.right + 1;
      const down = r.top < box.top - 1 || r.bottom > box.bottom + 1;
      if (across || down) cut.push(text.textContent);
    });
  });
  const scrolling = [];
  document.querySelectorAll('main table, main figure, main .panel').forEach((el) => {
    if (el.scrollWidth > el.clientWidth + 1) scrolling.push(el.tagName + '.' + el.className);
  });
  return { wide, cut, scrolling, page: document.documentElement.scrollWidth };
}"""


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
    _shot(page, "loop-002-desktop")
    _shot(page, "loop-002-desktop-full", full=True)

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


def test_charts_open_the_same_sources(browser: Browser, base_url: str) -> None:
    context = browser.new_context(viewport=DESKTOP)
    page, errors = _open(context, base_url)
    assert page.locator("svg.chart-svg").count() >= 8
    assert page.evaluate(OVERFLOW)["cut"] == []

    # Mouse: pointing at a column names it, selecting it opens the card of the filed figure.
    column = page.locator('#growth .chart-svg .mark[data-ref="q.revenue.2026q3"]').first
    column.scroll_into_view_if_needed()
    column.hover()
    tip = page.locator("#tip")
    expect(tip).to_be_visible()
    assert "Q3 2026" in tip.inner_text()
    assert "$17.0B" in tip.inner_text()
    _shot(page, "loop-002-chart-hover")
    column.click()
    card = page.locator("#src-q-revenue-2026q3")
    expect(card).to_be_visible()
    assert "p. 164" in card.inner_text()
    _shot(page, "loop-002-chart-source")
    # Selecting the same column again closes the card instead of reopening it.
    column.click()
    expect(card).to_be_hidden()

    # A value printed on a chart is a way in too.
    page.locator('#value .chart-svg text[data-ref="press.cnbc.fully_diluted_high"]').click()
    card = page.locator("#src-press-cnbc-fully-diluted-high")
    expect(card).to_be_visible()
    assert "PRESS" in card.inner_text()
    card.get_by_role("button", name="close").click()
    expect(card).to_be_hidden()

    # Keyboard: one stop per chart, arrows between its marks, Enter opens the card.
    marks = page.locator("#losses .chart-svg .mark")
    assert marks.first.get_attribute("tabindex") == "0"
    assert marks.nth(1).get_attribute("tabindex") == "-1"
    assert "show source" in (marks.first.get_attribute("aria-label") or "")
    marks.first.focus()
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.getAttribute('data-ref')") == "is.net_loss.fy2023"
    page.keyboard.press("End")
    assert page.evaluate("document.activeElement.getAttribute('data-ref')") == "is.net_loss.9m2026"
    page.keyboard.press("Enter")
    card = page.locator("#src-is-net-loss-9m2026")
    expect(card).to_be_visible()
    assert "FILED" in card.inner_text()
    page.keyboard.press("Escape")
    expect(card).to_be_hidden()

    # The panel bar shows where the reader is.
    page.keyboard.press("g")
    expect(page.locator('.keys a[href="#growth"]')).to_have_attribute("aria-current", "true")
    _shot(page, "loop-002-growth")

    assert _serious(page) == []
    assert errors == []
    context.close()


@pytest.mark.parametrize("width", PHONE_WIDTHS)
def test_phone_never_scrolls_sideways(browser: Browser, base_url: str, width: int) -> None:
    context = browser.new_context(
        viewport={"width": width, "height": 800},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
    )
    page, errors = _open(context, base_url)
    found = page.evaluate(OVERFLOW)
    assert found["page"] <= width
    assert found["wide"] == []
    assert found["scrolling"] == []
    assert found["cut"] == []
    # The tables behind the charts start folded, and open in place: still nothing sideways.
    folds = page.locator("details.fold")
    assert folds.count() >= 4
    assert page.locator("details.fold[open]").count() == 0
    for index in range(folds.count()):
        folds.nth(index).locator("summary").tap()
    assert page.locator("details.fold[open]").count() == folds.count()
    found = page.evaluate(OVERFLOW)
    assert (found["page"], found["wide"], found["scrolling"]) == (found["page"], [], [])
    assert found["page"] <= width
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
    _shot(page, "loop-002-phone")

    # No sideways scrolling of the page itself.
    assert page.evaluate("document.documentElement.scrollWidth") <= PHONE["width"]

    # A bar made for thumbs: five names, tall enough, no keyboard keys.
    for name in ("value", "ev", "contracts", "growth", "losses"):
        link = page.get_by_role("link", name=name, exact=True)
        box = link.bounding_box()
        assert box is not None, name
        assert box["height"] >= 44, name
    assert page.locator(".keys a kbd").first.is_hidden()

    # One tap on a panel name, one tap on a number: the card rises from the bottom.
    page.get_by_role("link", name="contracts", exact=True).tap()
    expect(page.locator("#contracts-h")).to_be_in_viewport()
    expect(page.locator('.keys a[href="#contracts"]')).to_have_attribute("aria-current", "true")
    page.locator('#contracts button[data-ref="commit.total"]').first.tap()
    card = page.locator("#src-commit-total")
    assert card.is_visible()
    assert "$900.9 billion" in card.inner_text()
    sheet = card.bounding_box()
    assert sheet is not None
    assert sheet["x"] == 0
    assert sheet["width"] == PHONE["width"]
    assert abs(sheet["y"] + sheet["height"] - PHONE["height"]) <= 1
    _shot(page, "loop-002-phone-source")
    card.get_by_role("button", name="close").tap()
    expect(card).to_be_hidden()

    # One tap on a chart: the same kind of card.
    column = page.locator('#contracts .chart-svg .mark[data-ref="obligations.total.2029"]')
    column.scroll_into_view_if_needed()
    _shot(page, "loop-002-phone-chart")
    column.tap()
    card = page.locator("#src-obligations-total-2029")
    expect(card).to_be_visible()
    assert "FILED" in card.inner_text()
    page.mouse.click(10, 10)  # anywhere outside closes it
    expect(card).to_be_hidden()

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
    page.locator("#src-rpo-total").get_by_role("button", name="close").click()
    assert page.locator("#src-rpo-total").is_hidden()
    # The charts are drawn by the server, and every table behind them is open.
    assert page.locator("svg.chart-svg").count() >= 8
    assert page.locator("svg.chart-svg .col").first.is_visible()
    assert page.locator("details.fold:not([open])").count() == 0
    assert page.locator('button[data-ref="obligations.total.2029"]').first.is_visible()
    context.close()


def test_phone_without_javascript(browser: Browser, base_url: str) -> None:
    context = browser.new_context(
        viewport=PHONE, is_mobile=True, has_touch=True, java_script_enabled=False
    )
    page, _ = _open(context, base_url)
    found = page.evaluate(OVERFLOW)
    assert found["page"] <= PHONE["width"]
    assert (found["wide"], found["scrolling"], found["cut"]) == ([], [], [])
    context.close()


def test_loads_fast(browser: Browser, base_url: str) -> None:
    context = browser.new_context(viewport=DESKTOP)
    page = context.new_page()
    begin = time.perf_counter()
    page.goto(base_url + "/", wait_until="load")
    elapsed = time.perf_counter() - begin
    assert elapsed < 1.0, f"page load took {elapsed:.2f}s"
    context.close()


def test_page_weight(base_url: str) -> None:
    request = urllib.request.Request(base_url + "/", headers={"Accept-Encoding": "gzip"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        assert response.headers["Content-Encoding"] == "gzip"
        compressed = len(response.read())
    assert compressed < 60_000, f"the page weighs {compressed} bytes compressed"
