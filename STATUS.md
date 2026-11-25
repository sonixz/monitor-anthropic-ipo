# STATUS · monitor-anthropic-ipo

> Where the project stands, verified. Last reviewed: 2026-11-23 · loop-016

## Live

| | |
| --- | --- |
| Site | https://antipo.watch, private: a login page in front of every page, on both addresses (Loop 013) |
| Version | 0.21.0 (tag `v0.21.0`, built 2026-11-25), under the name antipo.watch |
| Home page | The AI signal scanner: the 50 most traded stocks of the S&P/TSX Composite, ranked on 2026-11-20 |
| Signals | For the session of Fri 2026-11-20, 50 signals, written by Claude in a working session on 2026-11-22 (no strong signal; buys FTS and DOL at medium confidence) |
| Daily run | Scheduled in the working session on the owner's PC, weekdays about 16:47 Toronto (D-049); first run Mon 2026-11-23 |
| Session prices | `/portfolio` IN SESSION: open positions' prices every five minutes, 9:30 to 16:00 Toronto, display only (Loop 015) |
| Levels at the broker | `/portfolio` REAL: the owner's stop market and alerts beside the plan's, kept in `/data/results/levels.json`; HELD on the scanner (Loop 016) |
| Discipline | TODAY checklist at the top of `/portfolio`, journal at `/journal`, starting Mon 2026-11-23; entries kept in `/data/results/discipline` (Loop 014) |
| Simulated portfolio | `/portfolio`, $4,000 CAD from the Nov 20 decisions: buy 4 FTS and 1 DOL at the Nov 23 open (rules v2) |
| Closes | Yahoo Finance daily bars for 220 candidates, read at start and after each close; 0 failures on 2026-11-22 |
| IPO page | `/ant`, unlinked: Form 424B4 at $83.00, market panel on ANT, SEC watch |
| AI in the live service | None. The signals are JSON files written by a separate run and checked by code |

## What works (checked on 2026-11-22)

- The scanner: TODAY (strongest signals with entry, stop, target), LIST (50 stocks, entries and exits of the week), TRACK RECORD (by level and one by one), HOW.
- Every value is a button: a close opens its MARKET card, an indicator, stop or target its formula (CALC), a signal its reasons (AI) with their quoted sources.
- Signal files are checked in the run (`scan check`) and in the service; a refused file is named on the page and the last good signals stay (seen live on 2026-11-22, when a file reached the old release first).
- Result files (signals, decisions, real orders) are uploaded by the daily run with a token and kept on the server only (`signals_read.server` in `/health`, Loop 013).
- Tests: 266 unit tests (indicators, ATR, stops and targets, the track record, the portfolio, the gate and the discipline journal checked against counts by hand), 23 real-browser tests at 390 and 1280 px; CI and CodeQL green on `v0.19.1`.

## Known limits

- The track record is empty: the first signals are from Nov 20; 5-session results arrive from Nov 27.
- No daily run yet (above). Until then signals are written by hand in a session.
- Yahoo Finance is unofficial and delayed; it gives no history for CDRs (D-040).
- Live browser tests against antipo.watch meet the login: they run locally only.
- The 256 MB machine: builds must install one package at a time (D-044), and a build during the session froze it on 2026-11-23: build with the service paused, outside market hours. `/data/deploy.sh` on the machine is an older copy; deploys pass the limits on the command line.
- The page right after a restart says the closes are being read, for about two minutes.
- The legal side of public signals in Canada is the owner's to check (D-038).

## Not verified yet

- A full day of the service with the scanner: memory after the evening read of 220 series.
- The discipline checklist saved on the live site from a phone (tested locally in a real browser; the owner's first save is Mon 2026-11-23).
- Session prices: read live on 2026-11-23 for DOL and FTS (0 failures). Memory: only 15 MB available at 14:20 before a deploy; the service grows during the day. To watch.
- The owner's real levels saved on the live site.
- Holiday handling: the service tries once per expected session; the run stops on its own if no new session.

Next steps are in [BACKLOG.md](BACKLOG.md).
