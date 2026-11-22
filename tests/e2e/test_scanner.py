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
