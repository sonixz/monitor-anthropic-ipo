# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

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
