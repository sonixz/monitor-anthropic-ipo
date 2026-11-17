# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [0.5.1] - 2026-11-16

### Added

- **OVERVIEW** at the top of the page, asked by the owner: the phase of the IPO in words
  ("WAITING FOR THE IPO", then "PRICED", then "TRADING"), the stage bar with the reported dates,
  the time of the last check of the SEC's list and of the share price, and what comes next.
  The reader's browser counts the days to the reported pricing date ("pricing in 2 days");
  the page itself has no clock.

## [0.5.0] - 2026-11-16

A richer front (Loop 004). The owner asked for more figures at the top, a better navigation,
a chart of where the offered shares go, and anything else that can be checked in the filing.

### Added

- **A strip of key figures at the top**: price range, shares offered, amount raised, value at
  the range, and the reported dates of pricing and first trade. Below it, the stage of the IPO
  (filed, priced, trading, first unlock), driven by what the service has seen, not by a clock.
- **SHARES**: where the shares of the deal come from (new shares, existing stockholders, the
  underwriters' option, the private placement), who holds the shares after the IPO, the 22
  banks named as underwriters, and the insiders' indicated interest (up to $303 million, not
  binding). The allocation among banks is blank in this filing and shown as such.
- **UNLOCK**: the filing's schedule of shares that may be sold after the IPO, 23 steps, as a
  chart and as the filing's table with its wording. No calendar date is invented: the steps count
  from the final prospectus or from results releases.
- **CONTROL**: votes by class (Class F 50.1%, Class A 49.9%, of which the IPO shares about 5.5%),
  and what Classes T, N and E can do.
- **TIMELINE**: the filings from the SEC's list in order, then the reported dates and the first
  unlock step.
- A mark of the project's own (a frame and a line climbing in steps) and a new favicon.
- 56 facts copied from the filing by `extract.py`, 3 calculations, 30 consistency checks
  (159 in all): the underwriters' total equals the shares offered; existing holders, IPO buyers
  and the private placement add up to all shares after the IPO; stated percentages match.

### Changed

- The panel bar has ten panels and scrolls by itself on a phone; the page never does.
- On a phone, the "offer" and "listing" lines of the status block are hidden (the strip gives
  the same figures) and the label legend shows the tags alone, so the value at the IPO price
  stays on the first screen.
- Worded values (for example "a majority") wrap instead of running past the screen.

Also in this release, found by recording the Nasdaq source after the close on 2026-11-16:

### Changed

- **A trade made outside regular hours is named as such.** After the close and before the open,
  the source's first figure is a trade of the extended hours, not the close. The page said
  "market closed" beside it, which read as the closing price. It now says "traded after the
  close" or "traded before the open" on the status line, in the MARKET panel and in the source
  card of the price.
- **The close of the regular session is its own number**, with its own time and source card,
  when the source gives it beside a later trade: the row "Close of regular hours" in the table
  of the day.

### Fixed

- The source card of a market value named the stock twice in one sentence.
- A test of the service passed only between 9:30 and 16:00 in New York, the hours of the
  recorded answer it replays. It no longer depends on the hour at which it runs.

### Added

- A real answer of the Nasdaq source at 16:12 in New York, replayed by the tests.

## [0.4.2] - 2026-11-16

### Changed

- In the FILINGS panel, filings of the same form made on the same day share one line, each
  document with its own link. On the real list, five documents for investors filed the same
  day read as five identical lines.

## [0.4.1] - 2026-11-16

### Changed

- The FILINGS panel lists eight filings, not six: on the real list, five documents for investors
  filed on the same day would have pushed the registration statements out of sight.

### Added

- A real answer of EDGAR for the registrant (2026-11-16, reduced to the columns the reader
  uses) is replayed by the tests. It confirmed the shape the reader was written for.

## [0.4.0] - 2026-11-16

The first step towards a dashboard that keeps itself current (Loop 003).

### Added

- **Filings watch.** Every ten minutes the service asks the SEC's EDGAR for the list of the
  company's filings. The page gets a "filings" line at the top (the latest filing, or a notice
  when a prospectus newer than the one the page reads exists) and a FILINGS panel with the
  latest filings in plain words, each linked to sec.gov (key `f`).
- **The final price, read by the service.** When a final prospectus (Form 424B4) appears, the
  service reads the offering price from its cover and the page switches to it, as a FILED number
  whose source card quotes the cover. The price is taken only if the cover names the company, is
  not preliminary, gives dollars and cents, and states a total equal to that price times the
  shares on the same cover. Otherwise nothing is taken and the page says the prospectus is filed
  and not read yet.
- `SEC_CONTACT`, the contact address the SEC asks automated clients for, and `IPO_FILINGS`
  (`auto`, `off`). Without the address the watch is off, nothing is asked from the SEC and the
  page says so. On the machine the address lives in a root-only file read by the boot script.
- `/health` reports the state of the filings watch.
- `HOW-IT-WORKS.md`: the whole system in plain language, including where AI is involved (at build
  time, as the coding agent) and where it is not (the live service runs no model). The README is
  rewritten as a front page: badges, screenshots, panels, labels, workflows, release path.

### Notes

- **The watch has not talked to the real EDGAR yet.** The address is the owner's and is not on
  the machine. The code follows the published shape of EDGAR's answer and is tested on test data
  and on the real cover of Amendment No. 2. Until the address is there, the live page says "not
  watched".
- If the page cannot be drawn with what the filing list brought, it is drawn without it: the
  figures and the market panel never depend on the SEC answering.

## [0.3.2] - 2026-11-16

Found by checking the Nasdaq source with the market open.

### Fixed

- The line of the price through the day now ends at the last trade the source states. The
  source's series lags its last price by a minute or two (and at the open it still ended on an
  early trade), so the last point was drawn beside the price it named.
- A "previous close" is no longer shown on a first trading day, whatever the source puts in that
  field. Nasdaq.com's own is not read: before the open it was the close of an older session.

### Changed

- "Range of the day" is now "Range in regular hours", and the panel says that the line can also
  show trades made before the open and after the close. Seen on a real answer: Nasdaq.com's range
  leaves early trades out, its series includes them.

### Added

- A real answer of Nasdaq.com with the market open (a listed symbol, 9:34 in New York) is
  replayed by the tests: state, price, time, range, volume and the 335 points of the day.

## [0.3.1] - 2026-11-16

### Fixed

- Minutes after 0.3.0 went live, Yahoo Finance answered "too many requests" to the production
  machine, as it had to the workstation. The page said so and showed no price, as designed, but
  it would have had no quote on the listing day.

### Changed

- The first market source is now the quote service behind nasdaq.com, the exchange where the
  stock lists; Yahoo Finance is asked only if it fails. `IPO_MARKET` accepts `auto` (the
  default), `nasdaq`, `yahoo`, `off` and `file:<path>`.
- The page names the source that answered. A source card of a MARKET value quotes what that
  source gave.

## [0.3.0] - 2026-11-16

A market panel ready for the first trade (Loop 002, second release).

### Added

- A market source behind a replaceable adapter: Yahoo Finance chart data, free, unofficial and
  delayed. The service asks it on a timer (every five minutes before the listing, every two
  minutes while the market is open) and renders the page again only when the answer changed.
- Four states, shown in the status line: awaiting listing, trading, market closed, source
  unavailable. Before the listing the page shows no price. If the source fails, the last quote
  stays with a warning, or no price is shown at all.
- A MARKET panel that appears with the first quote: last price, change against the IPO price,
  the value of the shares outstanding and the diluted value at that price, the enterprise value
  and its multiple, the range of the day, the volume and a line of the price through the day.
- A fourth label, MARKET, for values that come from a quote. Each one names its source and the
  time of the quote, with the words "delayed, unofficial". Values computed from a quote show it
  among their inputs.
- A price is shown only if the source names the company as expected, in dollars: the price of
  another company under the same symbol is refused.
- The final IPO price becomes the headline price once a sourced fact records it
  (`pricing.ipo_price`): tiles, bridge, multiples and the comparison with the market use it.
- A quiet notice when newer figures exist ("New figures are in · reload"); the page never reloads
  by itself. `/health` reports the state of the market source.
- `IPO_MARKET` chooses the source: `yahoo`, `off`, or `file:<path>` to replay a recorded answer.

### Changed

- The page is rendered again when the market data changes; a rendering that fails leaves the
  previous page in place.

## [0.2.0] - 2026-11-16

Charts and a phone-first layout (Loop 002, first release). The owner asked for a better layout,
better behaviour on phones, and charts.

### Added

- Nine charts drawn on the server as SVG, without a chart library: the value across the price
  range for three share counts with the two press figures; the enterprise value bridge as a
  waterfall; diluted value against enterprise value; payments due by year; revenue by quarter;
  growth over the prior quarter; revenue against compute cost; operating margin; operating loss
  against net loss by period.
- Every mark on a chart opens the same source card as its number. One tab stop per chart, arrow
  keys between its marks, a readout on hover and on focus.
- New figures on the page, all from the filing: payments already running by year, operating loss
  and net loss for 2023, 2024, 2025 and the first nine months of 2026, and what the revenue of
  those nine months went to.
- On a phone: a panel bar made for thumbs that shows where the reader is, source cards that rise
  from the bottom with a close button, bars under their labels, and the tables behind the charts
  folded until asked for.

### Changed

- No sideways scrolling anywhere from 360 px up, tables included: the eight-column quarterly table
  became two narrow tables.
- Layout breakpoints follow the width of a panel, not of the screen, so two panels side by side on
  a laptop get the same treatment as one panel on a phone.
- The page uses wider screens (up to 1360 px).
- Chart colors were checked for color-blind safety against the panel surface.

## [0.1.0] - 2026-11-15

The first real dashboard (Loop 001).

### Added

- Five panels: VALUE, EV BRIDGE, CONTRACTS, GROWTH and LOSSES, in a calm terminal style.
- Every number is a button that opens its source: the passage of the filing (FILED), the formula
  and inputs (CALC) or the article (PRESS).
- Extraction of 276 figures from Anthropic's Form S-1/A, Amendment No. 2 (filed 2026-11-10), each
  with its page and quote.
- 129 consistency checks that stop the service if the figures do not agree.
- An explanation of why press valuations differ, with the share count behind each.
- Keyboard navigation (`v` `e` `c` `g` `l`, `?`), a phone layout, and a page that works without
  JavaScript.
- `/health`, JSON logs, security headers.
- Deployment and rollback scripts for the Agent Manager machine.
- CI (format, lint, types, tests, real-browser tests, secret scan), CodeQL, Dependabot,
  pre-commit hooks.
- Project documents, the devlog and the Loop0 files.

### Removed

- The placeholder page that held the address since 2026-11-15.

[0.1.0]: https://github.com/sonixz/monitor-anthropic-ipo/releases/tag/v0.1.0
