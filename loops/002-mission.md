# Loop 002 — Charts, a phone-first layout and a market panel ready for the first trade · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-16 · save as `loops/002-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-002` · Repository: existing — inspect before changing · Size: large

## Objective
Make the dashboard readable at a glance, above all on a phone: add charts and curves, and rework the layout so that nothing has to be scrolled sideways or pinched. Then have a market panel in place before the first trade (reported for 2026-11-19), so that the real share price appears and flows into VALUE and EV BRIDGE as soon as the stock lists. The page keeps its promise: every number can be traced, and no price is ever invented.

## Context
- Loop 001 delivered version 0.1.0, live at https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev: five panels, 125 numbers, each a button that opens its source. The owner's reaction on 2026-11-16: they love it and find it clean; they ask for a better layout, better behaviour on phones, and charts.
- Seen in a real browser on 2026-11-16: the page has no chart apart from thin bars, and those are hidden on a phone. On a 390 px screen the quarterly table needs sideways scrolling, row labels wrap over three lines, the status block fills a third of the first screen, and the panel bar shows keyboard keys that a phone does not have. The page is six screens long on a phone.
- The data already holds what charts need: seven quarters of revenue, compute cost and operating result; four annual periods of the income statement; payments due by year from 2026 to after 2030; the value at three prices for three share counts.
- The filing says the company applied to list on the Nasdaq Global Select Market under the symbol ANT. CNBC reported pricing for 2026-11-18 and the first trade for 2026-11-19. No share price exists before that.
- The production machine has 256 MB of memory; the service uses about 50 MB today. The Content-Security-Policy forbids inline styles and scripts, so charts are drawn with SVG attributes.

## Request (user’s words)
> « J'adore. C'est clean. On pourrais améliorer la mise en page et le côté "responsive" sur mobile. Mais sinon, cest vraiment bien. Go! /loop » — then, a few minutes later: « Aussi, peux etre des graphique, des courbe, chart et etc? » (2026-11-16)

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Numbers you can trace: every value a chart shows is also in a table with its source button, and selecting a chart mark or label opens the same source card.
- No digit on the page without a source. Axis ticks are the only exception: they are scale marks, flagged as such in the markup and checked by a test.
- Never invent a price: the market panel shows only what the source returned, with the source's name and the time of the quote, labeled delayed and unofficial. When the source returns nothing, the page says so.
- The notices stay visible: unofficial, not affiliated with Anthropic, not investment advice; the footer link 'Built with the Loop0 Method' stays.
- The core of the page works without JavaScript, makes no external request from the browser, and stays fast on a phone.

## Decisions
### Confirmed by the user — requirements
- **Go on this loop:** The owner said 'Go!' on 2026-11-16 after asking for a better layout and better phone behaviour, then added charts. — The owner's own words, quoted above.
- **Market data source:** A free unofficial source such as yfinance, labeled delayed and unofficial. — The owner's words in Loop 0 (DECISIONS D-013).
- **Style and language:** Calm terminal style, not neon; all user-facing text in English; the owner's words reworded in English in repository files. — Owner's directive.

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **How charts are drawn:** SVG rendered on the server by a small Python module; no chart library and no external request. — The Content-Security-Policy forbids inline styles; the page must stay light and work without JavaScript; every mark must carry a source id.
- **Chart size on screens:** Charts are designed at phone width and shown side by side on wider screens, so their text is the same size everywhere. — A wide chart shrunk to a phone makes its labels unreadable.
- **Reaching the market source:** A plain HTTP call to Yahoo Finance chart data behind an adapter, rather than the yfinance package, unless memory allows the package. — yfinance brings pandas and numpy, heavy for a 256 MB machine. The adapter keeps the source replaceable.
- **Label for market data:** A fourth label, MARKET, next to FILED, CALC and PRESS. — A delayed quote is not a filed figure, not our arithmetic and not a press report; the reader must see the difference.
- **The quarterly table:** Split into two narrow tables (revenue and growth; cost and margin) at every screen size. — Eight columns cannot fit a phone; one layout for all sizes is simpler and the charts carry the overview.

### Assumed — revisit if the environment says otherwise
- **One loop for three things:** Charts, layout and the market panel are one Loop 002, built in that order and released twice (0.2.0, then 0.3.0). — The owner is away. Their 'Go!' followed a message that announced the market panel for Loop 002; their two wishes were added. Splitting would need a second go before 2026-11-19.
- **Deploying:** Each release is deployed on the existing, already exposed machine once all checks pass, with the tested script and its rollback. — The owner approved deploying on this machine in Loop 001 and wants to be online before the listing. No new exposure or infrastructure is involved.

### Deferred — do not build now
- **AI explanations and the EDGAR watcher:** Not in this loop. — Blocked until the two secrets can be put on the machine.

## Carried over — not finished
These items were not completed according to the previous report. They are not done.

- The owner's 60-second test on the live page (acceptance criterion of Loop 001, not run).
- Several explanatory lines run to three lines on desktop and more on a phone; Loop 001 asked for two at most.
- LOOP.md says 'never deploy' (Loop0 template) while the owner approved deploying: ask Loop0 for a version that allows deployment within approved limits.
- Branch protection on main is documented in CONTRIBUTING.md but not set (the owner's action).
- The Reuters valuation is quoted from a secondary article that relays it.
- Options and RSUs are counted in full in the diluted figure; a treasury-stock view is not shown.
- Deployment is manual; there is no uptime monitoring from outside the machine.
- Blocker: Agent Manager cannot assign a secret to an existing Online machine (the capped AI key, a contact address for sec.gov).
- Blocker: CI cannot reach the machine; automated deployment needs a design with the owner.
- Still to build after this loop: EDGAR watcher and 'what changed', AI explanations, the 'what you pay' slider, the 'How We Build' page, automated deployment, storage and history.

## Scope
- Charts drawn on the server as SVG, in the same calm terminal style, without a chart library: quarterly revenue; growth over the prior quarter; revenue per compute dollar against the one-dollar line; operating margin; the value across the price range for the three share counts, with the two press figures; the enterprise value bridge as a waterfall; payments due by year; loss by year, operating against net.
- A chart module in Python with tests: scales, round axis ticks, label placement that cannot overlap, one sourced id per mark. Colors chosen for the dark surface and checked for color-blind safety with a validator, not by eye.
- Each chart keeps a table twin on the page. Marks and labels are reachable by keyboard and open the source card; a hover readout on desktop.
- Phone layout from 360 to 430 px: no sideways scrolling anywhere, including tables; the wide quarterly table is split into narrow tables; row labels shortened so they do not wrap over three lines; a compact status block; a panel bar made for thumbs; source cards as a bottom sheet; touch targets of at least 24 px.
- Tablet and desktop layout reviewed at 768, 1024, 1280 and 1680 px: consistent spacing, charts beside their tables where the width allows, wide screens used.
- Market panel behind a replaceable adapter, from a free unofficial source (Yahoo Finance chart data): last price, change against the IPO price, day range, volume, and a price chart once the stock trades. States: awaiting listing, trading, market closed, source unavailable (with the time of the last good quote).
- When a market price exists, VALUE and EV BRIDGE also show their figures at that price, as calculations whose price input carries a MARKET label, its source and its time.
- The IPO price: the page switches from the price range to the final price once a sourced fact records it (PRESS from an opened article, or FILED from the final prospectus when the owner saves it).
- The market data is refreshed on the server on a timer and cached; the page is never slowed by the source, and a failure of the source never breaks the page. Memory measured on the 256 MB machine.
- Two releases deployed on the existing machine once all checks pass: 0.2.0 (charts and layout), then 0.3.0 (market panel), each with the tested deploy script and its rollback.
- Documents kept current: CHANGELOG, DECISIONS, ARCHITECTURE, PRODUCT, STATUS, BACKLOG, CLAUDE.md; a devlog page with before and after screenshots; the report.

## Out of scope
- AI explanations: the owner's capped key cannot reach the machine yet.
- EDGAR watcher and the 'what changed' panel: they need a contact address for sec.gov as a secret on the machine.
- The 'what you pay' slider.
- The 'How We Build' page.
- Automated deployment from CI and uptime monitoring from outside the machine.
- History of market data in a database beyond what the price chart needs; comparables with other listed companies.
- A light theme.
- Any new exposure, machine or infrastructure change: the existing machine and URL only.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

For this loop:
- **Discover:** Look at the live page at 360, 390, 768, 1280 and 1680 px and list what is hard to read before changing anything. Check what the market source returns today for a listed symbol and for ANT, from this workstation and from the production machine.
- **Plan:** Choose the chart form by the job of the data (trend, comparison, part of a whole, bridge) before choosing colors; validate the palette with the validator.
- **Build:** Charts and layout first (release 0.2.0), then the market panel (release 0.3.0). Keep every FILED fact coming from extract.py and every calculation in calc.py with a hand-checked test.
- **Validate:** Real-browser tests at phone and desktop sizes, with and without JavaScript, locally and against the live URL after each deployment. Look at every screenshot before calling a layout done.
- **Document:** Devlog page with before and after screenshots at phone and desktop sizes. Record the assumed and proposed decisions in DECISIONS.md so the owner can confirm or reject them.

## Acceptance criteria
- [ ] Experience: A reader on a phone never scrolls sideways and never pinches to read a figure.
- [ ] Experience: One tap on a number or a chart mark opens its source; one tap outside closes it.
- [ ] Experience: A reader never needs a keyboard shortcut: the panel bar works by touch and shows where they are.
- [ ] Experience: Each panel answers its question first with a chart or a large figure, then gives the detail.
- [ ] Experience: A chart is readable without relying on color, and without hovering.
- [ ] Experience: When the stock starts trading, the reader does not have to do anything: the price appears on the next visit.
- [ ] In a real browser at 360, 390 and 430 px wide: the page does not scroll sideways, no table or chart scrolls sideways, and no text is cut.
- [ ] On a 390x844 phone the first screen shows, without scrolling, the value at the IPO price (shares outstanding, diluted) and the enterprise value; once the stock trades it also shows the market price.
- [ ] At least eight charts are on the page. For each one a test proves that every value it draws comes from a fact or a calculation with a source card, and that the same values are in a table on the page.
- [ ] The test 'no number without a source' still passes, extended to chart text; axis ticks are accepted only inside elements flagged as scale marks.
- [ ] In a real browser: selecting a chart mark with the mouse, by touch and with the keyboard opens its source card; without JavaScript the charts still show and the tables still open their sources.
- [ ] Chart colors pass the color-blind validator against the dark panel surface, and no information is carried by color alone (labels, legend or table).
- [ ] Screenshots at 360, 390, 768, 1280 and 1680 px were looked at one by one: no overlapping labels, no orphan gaps, no clipped chart.
- [ ] axe finds no serious or critical issue on desktop and phone.
- [ ] The page weighs under 60 KB compressed and loads in under 1 second in the browser test.
- [ ] Market adapter: unit tests parse a recorded response of a listed symbol (price, time, volume, candles), a response with no data, and an error; a check run from the production machine against a listed symbol proves the source can be reached from there.
- [ ] With no data for the symbol ANT (the situation before the listing) the live page says 'awaiting listing' and shows no price. With the source failing, the page still renders and says the source is unavailable.
- [ ] No market value appears on the page without its source name and the time of the quote; the words 'delayed' and 'unofficial' are next to it.
- [ ] The service stays under 200 MB of resident memory on the machine with the market refresh running, measured and reported.
- [ ] uv run ruff format --check, ruff check, mypy, pytest, pytest -m e2e and pre-commit all pass locally; CI and CodeQL are green on the released commits.
- [ ] Each release is deployed, /health shows its version, and the real-browser tests pass against the live URL.
- [ ] Real-people test: the owner opens the live page on their phone and says whether the layout and the charts are good; and the 60-second test carried over from Loop 001.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/002-mission.md` and the report as `loops/002-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-002.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- The symbol returns no data until the first trade, so the market panel can only be proven on other listed symbols beforehand. On an IPO day the first trade often comes hours after the market opens.
- The free source is unofficial: it can change, limit requests or refuse the machine's address. The adapter is replaceable and the panel degrades to 'source unavailable'.
- A figure computed from a delayed quote can be mistaken for an official value. It must carry its label, source and time everywhere it appears.
- Chart labels can collide or become too small on narrow screens; this is only caught by looking at real screenshots.
- Memory: 256 MB leaves little room; a background refresh must not grow.
- Each deployment makes the site unreachable for a few seconds.
- Reworking the layout can break what Loop 001 verified (keyboard keys, no-JavaScript mode, accessibility): the existing real-browser tests must keep passing.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/002-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-002"
}
```
