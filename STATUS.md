# STATUS · monitor-anthropic-ipo

> Where the project stands, verified. Last reviewed: 2026-11-22 · loop-011

## Live

| | |
| --- | --- |
| Site | https://antipo.watch, private: a login page in front of every page, on both addresses (Loop 013) |
| Version | 0.17.0 (tag `v0.17.0`), under the name antipo.watch |
| Home page | The AI signal scanner: the 50 most traded stocks of the S&P/TSX Composite, ranked on 2026-11-20 |
| Signals | For the session of Fri 2026-11-20, 50 signals, written by Claude in a working session on 2026-11-22 (no strong signal; buys FTS and DOL at medium confidence) |
| Daily run | Scheduled in the working session on the owner's PC, weekdays about 16:47 Toronto (D-049); first run Mon 2026-11-23 |
| Simulated portfolio | `/portfolio`, $4,000 CAD from the Nov 20 decisions: buy 4 FTS and 1 DOL at the Nov 23 open (rules v2) |
| Closes | Yahoo Finance daily bars for 220 candidates, read at start and after each close; 0 failures on 2026-11-22 |
| IPO page | `/ant`, unlinked: Form 424B4 at $83.00, market panel on ANT, SEC watch |
| AI in the live service | None. The signals are JSON files written by a separate run and checked by code |

## What works (checked on 2026-11-22)

- The scanner: TODAY (strongest signals with entry, stop, target), LIST (50 stocks, entries and exits of the week), TRACK RECORD (by level and one by one), HOW.
- Every value is a button: a close opens its MARKET card, an indicator, stop or target its formula (CALC), a signal its reasons (AI) with their quoted sources.
- Signal files are checked in the run (`scan check`) and in the service; a refused file is named on the page and the last good signals stay (seen live on 2026-11-22, when a file reached the old release first).
- Signal files are read from GitHub every 15 minutes without a token (live: `signals_read.GitHub` in `/health`).
- Tests: 185 unit tests (indicators, ATR, stops and targets and the track record checked against arithmetic by hand), 16 real-browser tests at 390 and 1280 px; CI and CodeQL green on `v0.12.1`. The live site passes the browser tests that apply to it.

## Known limits

- The track record is empty: the first signals are from Nov 20; 5-session results arrive from Nov 27.
- No daily run yet (above). Until then signals are written by hand in a session.
- Yahoo Finance is unofficial and delayed; it gives no history for CDRs (D-040).
- Signals are public in the repository as soon as pushed; a login on the site alone would not hide them (D-046).
- The 256 MB machine: builds must install one package at a time (D-044). `/data/deploy.sh` on the machine is an older copy; deploys pass the limits on the command line.
- The page right after a restart says the closes are being read, for about two minutes.
- The legal side of public signals in Canada is the owner's to check (D-038).

## Not verified yet

- A full day of the service with the scanner: memory after the evening read of 220 series.
- Holiday handling: the service tries once per expected session; the run stops on its own if no new session.

Next steps are in [BACKLOG.md](BACKLOG.md).
