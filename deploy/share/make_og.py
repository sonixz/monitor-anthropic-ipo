"""Turn deploy/share/og.svg into src/ipo_monitor/static/og.png (1200x630), with Chromium.

Run after changing og.svg:  uv run python deploy/share/make_og.py
X does not accept SVG for a card, so the PNG is committed.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SVG = ROOT / "deploy" / "share" / "og.svg"
PNG = ROOT / "src" / "ipo_monitor" / "static" / "og.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1200, "height": 630})
    page.set_content(
        '<body style="margin:0;background:#0e1116">' + SVG.read_text("utf-8") + "</body>"
    )
    page.screenshot(path=str(PNG), clip={"x": 0, "y": 0, "width": 1200, "height": 630})
    browser.close()
print(PNG, PNG.stat().st_size, "bytes")
