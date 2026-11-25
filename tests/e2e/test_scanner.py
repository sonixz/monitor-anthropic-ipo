"""The scanner in a real browser: the first screen on a phone, a signal and its sources."""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, expect

from .test_dashboard import DESKTOP, PHONE, _open, _serious, _shot

pytestmark = pytest.mark.e2e

# Nothing past the screen's edge, except inside a table that scrolls by itself (.scroll).
OVERFLOW = """() => {
  const wide = [];
  document.querySelectorAll('main *, header *, footer *').forEach((el) => {
    const r = el.getBoundingClientRect();
    const out = r.right > innerWidth + 1 || r.left < -1;
    if (r.width && out && !el.closest('.scroll')) wide.push(el.tagName + '.' + el.className);
  });
  return { wide, page: document.documentElement.scrollWidth };
}"""


def test_phone_first_screen_shows_the_strongest_signals(browser: Browser, base_url: str) -> None:
    context = browser.new_context(
        viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True
    )
    page, errors = _open(context, base_url, path="/")
    # Without scrolling: what the site is, that it is not advice, who wrote the signals,
    # and the strongest signals with their level, confidence and one line each.
    expect(page.locator(".disclaimer")).to_contain_text("not investment advice")
    expect(page.locator(".disclaimer")).to_be_in_viewport()
    # The time of the last analysis shows the system is working.
    expect(page.locator(".sys .sys-v").first).to_be_in_viewport()
    first = page.locator("#today .sig").first
    expect(first).to_be_in_viewport(ratio=1)
    expect(first.locator(".conf")).to_be_visible()
    expect(first.locator(".sig-sum")).to_be_visible()
    found = page.evaluate(OVERFLOW)
    assert found["wide"] == []
    assert found["page"] <= PHONE["width"]

    # One tap opens the signal's reasons; a value in a reason opens its formula.
    first.locator("button.n-ai").tap()
    card = page.locator(".src-ai:popover-open")
    expect(card).to_be_visible()
    expect(card.locator(".reasons li").first).to_be_visible()
    card.locator("button.n-calc").first.tap()
    calc = page.locator(".src-calc:popover-open")
    expect(calc).to_be_visible()
    expect(calc.locator(".src-formula")).to_contain_text("=")
    _shot(page, "scan-phone")
    assert errors == []
    context.close()


def test_desktop_list_and_track_record(browser: Browser, base_url: str) -> None:
    context = browser.new_context(viewport=DESKTOP)
    page, errors = _open(context, base_url, path="/")
    rows = page.locator("#list tbody tr")
    assert rows.count() >= 20
    expect(page.locator("#list .lede")).to_contain_text("ranked on")
    expect(page.locator("#record")).to_be_visible()
    # The IPO page is no longer linked, but still answers at its address.
    assert page.locator('a[href="/ant"]').count() == 0
    assert _serious(page) == []
    _shot(page, "scan-desktop", full=True)
    assert errors == []
    context.close()


def test_the_simulated_portfolio_on_a_phone(browser: Browser, base_url: str) -> None:
    context = browser.new_context(
        viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True
    )
    page, errors = _open(context, base_url, path="/portfolio")
    expect(page.locator(".sim").first).to_be_visible()  # it says it is simulated
    # The day's checklist comes first, then the orders.
    expect(page.locator("#today legend").first).to_be_in_viewport()
    first = page.locator("#orders .sig").first
    first.scroll_into_view_if_needed()
    first.locator("button.n-calc").tap()
    card = page.locator(".src-calc:popover-open")
    expect(card).to_contain_text("the smallest")
    found = page.evaluate(OVERFLOW)
    assert found["wide"] == []
    _shot(page, "portfolio-phone")
    assert errors == []
    context.close()


def test_signing_in_on_a_phone(browser: Browser, private_url: str) -> None:
    context = browser.new_context(
        viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    page.goto(private_url + "/portfolio")
    assert "/login" in page.url
    expect(page.locator(".login-form button")).to_be_in_viewport()
    _shot(page, "login-phone")
    page.fill("#user", "owner")
    page.fill("#password", "wrong")
    page.locator(".login-form button").tap()
    expect(page.locator(".login-error")).to_contain_text("Wrong username or password")
    page.fill("#user", "owner")
    page.fill("#password", "a long test passphrase")
    page.locator(".login-form button").tap()
    page.wait_for_url("**/portfolio")
    expect(page.locator(".sim").first).to_be_visible()
    page.goto(private_url + "/")
    expect(page.locator("#today")).to_be_visible()  # still signed in
    context.close()


def test_the_checklist_on_a_phone(browser: Browser, base_url: str) -> None:
    context = browser.new_context(
        viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True
    )
    page, errors = _open(context, base_url, path="/portfolio")
    form = page.locator("#today form")
    box = form.bounding_box()
    assert box is not None
    assert box["height"] <= 2 * PHONE["height"]  # within two screens
    page.locator('input[name="read_orders"]').check()
    page.locator('input[name="orders"][value="none"]').check()
    page.locator('input[name="mood"][value="4"]').check()
    page.locator("#today button[type=submit]").tap()
    page.wait_for_url("**saved=1**")
    expect(page.locator('input[name="read_orders"]')).to_be_checked()
    page.goto(base_url + "/journal")
    expect(page.locator("#log")).to_be_visible()
    _shot(page, "journal-phone")
    assert errors == []
    context.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_prices_during_the_session(browser: Browser, session_url: str, viewport: object) -> None:
    phone = viewport == PHONE
    context = browser.new_context(
        viewport=viewport,  # type: ignore[arg-type]
        device_scale_factor=2,
        is_mobile=phone,
        has_touch=phone,
    )
    page, errors = _open(context, session_url, path="/portfolio")
    panel = page.locator("#session")
    expect(panel).to_contain_text("IN SESSION")
    expect(panel).to_contain_text("TEST DATA, not a real quote")
    row = panel.locator(".live").first
    expect(row).to_contain_text("RY")
    expect(row).to_contain_text("11:15 ET")
    expect(row.locator(".live-flag")).to_have_text("▲ target reached")
    found = page.evaluate(OVERFLOW)
    assert found["wide"] == []
    assert found["page"] <= viewport["width"]  # type: ignore[index]
    panel.scroll_into_view_if_needed()
    _shot(page, "session-" + ("phone" if phone else "desktop"))
    assert errors == []
    context.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_levels_at_the_broker(browser: Browser, levels_url: str, viewport: object) -> None:
    """The owner types the levels entered at the broker, saves, and sees them as theirs."""
    phone = viewport == PHONE
    context = browser.new_context(
        viewport=viewport,  # type: ignore[arg-type]
        device_scale_factor=2,
        is_mobile=phone,
        has_touch=phone,
    )
    page, errors = _open(context, levels_url, path="/portfolio")
    real = page.locator("#real")
    broker = real.locator("table.broker")
    expect(broker).to_contain_text("stop market")
    # A typo first: refused with its reason, nothing saved.
    real.locator("summary", has_text="change your levels").click()
    page.fill("input[name=stop_RY]", "2600")
    page.click("form.levels button[type=submit]")
    expect(page.locator("#real .lede")).to_contain_text("too far from the last price")
    # Then the levels as typed on a phone, with a comma.
    page.fill("input[name=stop_RY]", "260,00" if phone else "259.5")
    page.fill("input[name=target_RY]", "285")
    page.fill("input[name=near_RY]", "280")
    page.click("form.levels button[type=submit]")
    expect(page.locator("#real .lede")).to_contain_text("levels saved")
    row = page.locator("table.broker tbody tr").first
    expect(row).to_contain_text("$260.00" if phone else "$259.50")
    expect(row).to_contain_text("YOURS")
    expect(row).to_contain_text("plan $252.69")
    flag = page.locator("#session .live .live-flag").first
    expect(flag).to_have_text("! near stop")
    found = page.evaluate(OVERFLOW)
    assert found["wide"] == []
    assert found["page"] <= viewport["width"]  # type: ignore[index]
    real.scroll_into_view_if_needed()
    _shot(page, "levels-" + ("phone" if phone else "desktop"))
    # The scanner knows the stock is held.
    page.goto(levels_url + "/")
    expect(page.locator("#list .held").first).to_be_visible()
    _shot(page, "held-" + ("phone" if phone else "desktop"))
    assert errors == []
    context.close()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["phone", "desktop"])
def test_report_a_sale(browser: Browser, orders_url: str, viewport: object) -> None:
    """The owner reports a sale filled at the broker; the position closes and RESULTS counts it."""
    phone = viewport == PHONE
    context = browser.new_context(
        viewport=viewport,  # type: ignore[arg-type]
        device_scale_factor=2,
        is_mobile=phone,
        has_touch=phone,
    )
    page, errors = _open(context, orders_url, path="/portfolio")
    form = page.locator("#report form")
    expect(form.locator("input[name=side][value=sell]")).to_be_checked()
    expect(form.locator("input[name=date]")).to_have_value("2026-11-23")
    # A typo first: refused with its reason, nothing reported.
    form.locator("input[name=symbol]").fill("RY")
    form.locator("input[name=shares]").fill("3")
    form.locator("input[name=price]").fill("270,00")
    page.locator("#report").scroll_into_view_if_needed()
    _shot(page, "report-" + ("phone" if phone else "desktop"))
    form.locator("button[type=submit]").click()
    expect(page.locator("#report .lede")).to_contain_text("RY: 3 shares sold, 1 held")
    expect(page.locator("#real")).to_be_visible()
    # Then the sale as filled.
    form = page.locator("#report form")
    form.locator("input[name=symbol]").fill("ry")
    form.locator("input[name=shares]").fill("1")
    form.locator("input[name=price]").fill("270,00" if phone else "270")
    form.locator("button[type=submit]").click()
    expect(page.locator("#report .lede")).to_contain_text("reported: sell 1 RY at 270.00")
    expect(page.locator("#real")).to_have_count(0)
    results = page.locator("#metrics")
    results.locator("summary", has_text="Closed trades").click()
    expect(results).to_contain_text("+$5.90")
    found = page.evaluate(OVERFLOW)
    assert found["wide"] == []
    assert found["page"] <= viewport["width"]  # type: ignore[index]
    results.scroll_into_view_if_needed()
    _shot(page, "reported-" + ("phone" if phone else "desktop"))
    assert errors == []
    context.close()
