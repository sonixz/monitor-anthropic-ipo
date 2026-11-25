# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [0.20.0] - 2026-11-24

### Changed

- **The envelope is the owner's own money** (D-056). Owner: "there is no simulation; the 4,000 is
  mine, my envelope at my broker." With the owner's ledger, `/portfolio` no longer keeps a paper
  copy beside the real orders: positions open and close only with the orders the owner reports,
  at the prices they got; cash, value, results and the comparison with the TSX fund come from
  them. The evening's orders are advice for the owner to place at the next open; a stop reached
  is flagged (asking for the sale to be reported), a target or the holding period reached becomes
  advice to sell at the next open. One POSITIONS table (price of the moment, gain, R, day of the
  holding period); IN SESSION shows one row a stock, no SIM rows. Without a ledger the code still
  simulates, as before (tests).
- The scanner names how long a stock has been held: "since Nov 23 · day 2 of 20".
- Rules version 3: the same figures, the envelope marked as real.

## [0.19.1] - 2026-11-23

### Fixed

- The REAL table's price and gain used the last daily close (Friday's on Monday) without saying
  so. During the session they now use the session price with its time; otherwise the column
  names the close it shows ("close Nov 20"). Owner: "are these numbers right?"

## [0.19.0] - 2026-11-23

### Added

- **Your levels at the broker** (Loop 016): on `/portfolio`, an "At the broker" table for each
  real position: stop market, target alert and near-stop alert, the owner's level marked YOURS with
  the plan's beside it; without one, the plan's applies. A form changes them (comma or dot);
  a typo is refused with its reason (not a price, too far from the last price, stop above the
  target, near-stop alert outside them) and nothing is stored. Kept in `levels.json` next to the
  ledger, so an upload of the ledger keeps them. The IN SESSION panel uses them for real
  positions; the simulation never reads them.
- **Held stocks**: a HELD badge on the scanner's TODAY and LIST, with real shares and price and
  simulated shares; a buy signal on a held stock reads as a position to manage, with the stop
  and target in force. NEXT OPEN marks an order for a stock already held for real.

## [0.18.0] - 2026-11-22

### Added

- **Prices during the session** (Loop 015): on `/portfolio`, an IN SESSION panel for each open
  position, simulated and real: a recent price and its time (MARKET, Yahoo Finance, may be
  delayed), the change since entry in % and in R, how far the stop and the target are, and a flag
  with a word and a mark: target reached, stop reached (by the session's high or low), near stop
  (within half an ATR). Read every five minutes from 9:30 to 16:00 Toronto, at most ten symbols,
  nothing outside those hours. Outside the session or without today's price, the last close,
  named as such. Display only: the simulation and the track record still use daily closes.
- `/health` reports the session watcher (`session`); `IPO_SESSION` (auto, off, file:<folder>).

## [0.17.0] - 2026-11-22

### Added

- **Discipline mode** (Loop 014): a TODAY checklist at the top of the portfolio (morning: read the
  orders, placed or skipped on purpose or none planned, stops entered; evening: no trade outside
  the plan, read the analysis; a mood and a note), saved on the server; works without JavaScript.
- **The journal** (`/journal`): one row per trading day since the simulation started, missed days
  included, newest first; streak, best streak, assiduity over 30 days and overall; the owner's
  orders of the day and the gaps from the plan (outside the plan, above the advised size), by code.
  Only today and the trading day before can be filled in.
- Sign-out links on the pages; the evening run reads today's checklist status by token.

## [0.16.0] - 2026-11-22

### Added

- **A private portal** (Loop 013): a clean login page in the site's style, one username and one
  password from the machine's secrets, a session of 30 days, wrong logins slowed down. Every page
  is behind it, on antipo.watch and on the Fly.io address; `/health` shows no result.
- **Results on the server only:** `PUT /api/upload/<signals|decisions|ledger>/<name>` with a
  token, checked by the same rules before it is stored in `/data/results`;
  `python -m ipo_monitor.scan upload <file>`. The repository ignores result files.

### Changed

- The daily run uploads its files instead of pushing them (ROUTINE.md step 9).
- The scanner no longer reads result files from GitHub.

### Removed

- The HTTP Basic password on `/portfolio` (0.15.0), replaced by the login.

## [0.15.0] - 2026-11-22

### Added

- **A password on `/portfolio`** (owner: "a small login, very simple, just to say it's private"):
  HTTP Basic checked by the service itself, so it also holds on the Fly.io address; the password
  comes from `PORTFOLIO_PASSWORD` in the machine's secrets file and is never printed. The scanner
  stays public. Private pages are sent with `Cache-Control: private, no-store` and `noindex`.
- **The owner's real orders** (`IPO_LEDGER`, `/data/ledger.json` on the machine, outside git): a
  REAL section beside the simulation, with the price paid against the advice, the stop and target
  of the recommendation followed, and the gain.

## [0.14.1] - 2026-11-22

### Changed

- **Rules version 2** (owner's choice): the slot follows the signal's confidence, 20% of the
  envelope at high confidence and 10% at medium. Applied from the start, before the first fill:
  the Nov 23 orders become 4 FTS and 1 DOL. The rules page lists each version and its change.

## [0.14.0] - 2026-11-22

### Added

- **The simulated portfolio** (Loop 012), at `/portfolio`: a dedicated envelope of $4,000 CAD that
  follows the AI signals by versioned rules (`data/portfolio/rules.json`): at most 5 positions,
  about 20% of the envelope each, the loss at the stop capped at 10% of it, no leverage.
- Claude's decision files (`data/portfolio/decisions/<session>.json`): buy, wait or pass for each
  signal the rules allow; hold or exit for each position; reasons without numbers, checked by code.
- `scan/portfolio.py`: sizing step by step, fills at the next open, stops, targets, holding period
  and sell signals applied by code; metrics against XIC (return, win rate, average R, drawdown,
  exposure) with their sample size.
- `python -m ipo_monitor.scan portfolio`; ROUTINE.md steps for the decisions and a weekly review.
- The first decisions, after Nov 20: buy 9 FTS and 3 DOL at the next open.
- A link from the scanner to the simulated portfolio.

## [0.13.0] - 2026-11-22

### Added

- **A status strip** under the title, at the owner's request: the date and time of the last
  analysis (with its session), when the closes were last read and how many stocks, and the next
  analysis. A green dot when up to date, amber when the analysis lags the last session or closes
  could not be read.

### Changed

- **A denser phone layout** for the scanner: smaller title, margins and text, tighter signal cards
  and table rows; about six signals with their entry, stop and target on the first screen.

## [0.12.1] - 2026-11-22

### Removed

- ANT is no longer in the scanner, at the owner's request: no ANT card, no link to the IPO page.
  The IPO page still answers at `/ant` for those who have the address.

## [0.12.0] - 2026-11-22

### Added

- **Top 50 of the S&P/TSX Composite** (Loop 011): 220 candidates (`data/scan/candidates.json`,
  with sectors), ranked weekly by value traded; the list size comes from the candidate file.
- **Stops and targets** for every buy and sell (`scan/levels.py`): stop at 2 × ATR(14) and target
  at 3 × ATR(14) from the entry close, risk and reward per share, each opening its formula. A
  sell means exit or avoid, not advice to sell short.
- ATR(14), Wilder's average true range, among the indicators.
- The track record follows each buy and sell for up to 20 sessions: target hit, stop hit (a day
  that reaches both counts as the stop), expired or open.
- `ROUTINE.md`: the steps the scheduled run follows to write, check and push a signal file.
- The Nov 20 signals cover the 50 stocks of the new list.

### Fixed

- Builds on the 256 MB machine install one package at a time (`deploy.sh`): a parallel build
  froze it on 2026-11-22.
- The ANT market watcher asks Yahoo Finance with a plain client name, which it answers.
- The IPO page's canonical address is `/ant`.

## [0.11.0] - 2026-11-22

### Added

- **The scanner is the home page** (Loop 010). The 25 stocks of the S&P/TSX 60 with the highest
  average value traded a day over 20 sessions, ranked each week, with entries and exits named;
  ANT stays as a pinned card in US dollars.
- Daily bars from Yahoo Finance (`scan/bars.py`), read after each close; a session still trading
  is left out.
- Indicators with their formulas (`scan/indicators.py`): averages over 20, 50 and 200 sessions,
  RSI over 14, change over 20 sessions, volume against its average, value traded, 52-week range.
- AI signal files (`data/signals/YYYY-MM-DD.json`) and their rules (`scan/signals.py`): five
  levels, a confidence, reasons that name indicators as `{key}` or quote a source with its link.
  A file that types a number, cites nothing or names a stock outside the list is refused whole.
- The track record (`scan/track.py`): every signal with its close, and the change after 5 and 20
  sessions, wins and losses alike.
- Signal files are read from the release and from the public repository on GitHub, every 15
  minutes, without a token (`scan/watch.py`).
- `python -m ipo_monitor.scan dossier` and `check`, for the scheduled run; `/scan/dossier.json`.
- The first signals, for Friday Nov 20, written by Claude in a working session.

### Changed

- The Anthropic IPO page moves to `/ant`, unchanged.

## [0.10.2] - 2026-11-19

### Added

- **The MARKET panel before the first trade**, at the owner's request. It says "no trade yet", when
  the source was last asked, and shows the values at the IPO price that the market price will
  replace: value outstanding and diluted, and enterprise value. With the first trade the full panel
  takes its place by itself. On a phone these values stay on the first screen.

## [0.10.1] - 2026-11-19

### Fixed

- **No market price before the first trade.** On the morning of the listing, Yahoo Finance gave
  the offering price, $83.00, as ANT's price, with a volume of zero and no first trading day. The
  page showed it as a last quote at 10:08 in New York, then "source unavailable" once Nasdaq.com
  answered that nothing had traded. A Yahoo Finance price now counts only once some shares have
  changed hands; until then the panel stays "awaiting". Test on the recorded answer
  (`tests/fixtures/market/yahoo-ant-no-trade.json`).

## [0.10.0] - 2026-11-19

### Changed

- **The final prospectus is the page's filing** (Loop 009): Form 424B4, dated Nov 18, 2026,
  read in full by the same extractor (`data/facts/p424b4.json`, 335 facts). The page computes
  at the $83.00 IPO price with the prospectus's own figures: 956,351,354 shares sold by the
  company, 13,219,642,276 shares outstanding after the offering, $104.8 billion of net
  proceeds, $232.4 billion of cash after the offering. All 159 consistency checks pass on it.
- Amendment No. 3 moves to `data/facts/history/`. HISTORY lists what changed from it, the
  price range included ("no longer given"), each side opening its own filing.
- The views across the price range (range charts, implied value by price) leave the main page
  (D-037). The filing's "dated" Nov 18 is written as such; it was filed with the SEC on Nov 19.
- The lock-up steps keep the prospectus's words, which now give the date of the first steps.

### Added

- The extractor reads the final prospectus's wording beside the amendments': the prospectus
  date, the single price, figures "based upon the initial public offering price", the banks'
  allocations (checked to add up to the total), and two reworded sentences. Tests reproduce
  all three filings.

## [0.9.1] - 2026-11-19

### Fixed

- Once the final prospectus is read, the glance showed the offer at the filed 825 million
  shares ($68.5B) while the prospectus's cover gives 980,000,000 shares and $81,340,000,000.
  The two numbers beside the price on that cover, already checked against each other by the
  service, are now FILED facts (`final.shares_offered`, `final.total`), and the glance shows them.
- Phone, final prospectus filed: the "filings" line keeps the notice and the link and drops
  the repeat about other figures (the header says it), so the enterprise value stays on the
  first screen. Real-browser test added for that state.

## [0.9.0] - 2026-11-18

### Added

- **The IPO price, as the press reported it** (pricing night): `pricing.ipo_price` is recorded
  as a PRESS fact, $83 a share, from the Associated Press article of Nov 18 (opened and quoted),
  with the reported offer of 980 million shares and $81 billion of proceeds. The page switches to
  its priced state: values at $83, the IPO price in the glance. The glance shows the reported
  offer size and says the values below still count the filed shares until the final
  prospectus. When the service reads the price on the cover of the final prospectus, that FILED
  price replaces the press one by itself.

### Changed

- Priced state on a phone: the countdown to pricing is gone once a price is recorded, and the
  "next" line is shorter, so the enterprise value stays on the first screen.
- The enterprise value at the middle of the range is written beside the range chart once
  priced, so every value a chart draws is still a number on the page.
- Tests: most read the page as it was before the price (`facts`); `tests/test_reported.py`
  reads it with the press price (`reported`). Real-browser tests check the first screen in
  either state.

## [0.8.2] - 2026-11-17

### Fixed

- When the final prospectus is filed and its price is read from the cover, the header says
  "final price read" instead of "new filing · not read yet" (found on review before pricing).

## [0.8.1] - 2026-11-17

### Added

- **Up to date, at a glance** (Loop 008a): a line in the header says "up to date", the time of
  the SEC's last check and the filing the figures come from. It says "up to date" only when the
  SEC's list was read and holds no newer prospectus; otherwise it names the new filing ("not read
  yet"), a failed check, or an unavailable list. The page's script asks `/health` every minute
  for the time of the last check, since the page is rendered again only when what it shows
  changes.

## [0.8.0] - 2026-11-17

### Added

- **Versions you can see** (Loop 008): the overview names the filing the figures come from and
  its date, with a link "what changed"; a **HISTORY** panel (key `h`) lists every figure that
  differs between two filings in a row, before and after, each opening its own filing's passage.
  The lock-up steps that changed are folded until asked for. Earlier filings are kept in
  `data/facts/history/`, extracted by the same code; nothing is overwritten in silence.
- A fact for the listing: "applied for" in Amendment No. 2, "approved" in Amendment No. 3.

### Changed

- **The page reads Form S-1/A, Amendment No. 3, filed 2026-11-17.** Same price range, shares
  offered and symbol; Nasdaq approved the listing; the lock-up table now gives Class A, Class N
  and their total for each step, and UNLOCK shows the total (20 of 23 steps moved by a few
  million shares).
- The extractor reads the wordings of both amendments (listing, 2026 Plan reserve, lock-up table)
  and takes the amendment number from the cover.

### Fixed

- A list of filings older than the filing the page reads no longer shows earlier filings as new.

## [0.7.1] - 2026-11-17

### Fixed

- On a phone, the hero is tighter: with a new-filing notice in the overview (a Form S-1/A was
  filed on 2026-11-17), the enterprise value had slipped a few pixels below the first screen.
  Found by the real-browser tests run against antipo.watch after the 0.7.0 deployment.

## [0.7.0] - 2026-11-17

### Added

- **A light, centered hero** (Loop 007): the project's mark, the name ANTHROPIC IPO WATCH, one
  line on what the page does, and the notices.
- **A line that teaches the keys** under the panel bar on a desktop: press a letter to jump to a
  panel, `?` for all keys, select any number to see its source. Next to it, **open all · fold
  all** for the tables behind the charts (shown only when the script runs).
- **Two rings (pie charts)**, drawn by the server like the other charts, each slice opening its
  source: votes by class in CONTROL (one Class F share holds about half the votes), and who holds
  the shares after the IPO in the overview, on wide screens. A new calculation,
  `control.class_a_other_pct`, gives the votes of Class A shares other than those sold in the IPO.

### Changed

- **One name everywhere:** Anthropic IPO Watch in the header, the app title, the client name
  sent to the SEC, the README and the docs (ANT IPO Monitor is gone).
- **UNLOCK spans the full width**, its chart staying in view beside its long table; CONTROL now
  sits beside CONTRACTS.
- On a phone the keys line and open/fold all are hidden, so the value at the IPO price stays on
  the first screen.

## [0.6.2] - 2026-11-17

### Added

- **The page at https://antipo.watch** (Loop 005), the owner's domain. Cloudflare holds the
  certificate and a Worker ([`deploy/cloudflare/worker.js`](deploy/cloudflare/worker.js)) relays
  to the Fly.io app; `www` and `http://` redirect to `https://antipo.watch`. The fly.dev address
  keeps working. Cloudflare's analytics beacon, e-mail rewriting and browser check are kept out
  of the page.
- **A share card for X and other networks** (Loop 006): Open Graph and `twitter:card`
  (`summary_large_image`) tags, and a 1200×630 image (`static/og.png`, drawn from
  `deploy/share/og.svg` by `deploy/share/make_og.py`) with the project's mark, the name
  Anthropic IPO Watch, the notices and the domain. No figure in the image: X keeps a card for
  days, and a price would go stale. The tab title takes the new name.
- The page names `https://antipo.watch/` as its canonical address, so search engines and link
  previews prefer it to the Fly.io address, which stays as a fallback.

### Changed

- README and SECURITY give antipo.watch only; the Fly.io address is documented in
  INFRASTRUCTURE.md, where operations need it.

## [0.6.1] - 2026-11-16

### Added

- **A VISITS panel** at the bottom of the page, asked by the owner: today, the total, and a line
  of the visits in time, per hour for the first days, then per day. Reachable from the panel bar
  (key `w`). The line is drawn by the page's script from `/stats`, which now gives every day and
  every hour of the last 48, those without a visit at zero.
- A real answer of the Nasdaq source at 20:14 in New York, replayed by the tests. It settles the
  question left open after the close: the time the source gives is the last trade's (19:59),
  not the time of its answer.

### Changed

- The visit counts move from the footer to the VISITS panel.

## [0.6.0] - 2026-11-16

### Added

- **Visits, shown in the footer**, asked by the owner to measure the audience: "visits: N today
  · M since Nov 16". The page's script tells the service once per browser session; the service
  adds one to the count of the day (New York time) and keeps only that number per day, in
  `/data/visits.json` on the machine. No cookie, no address, nothing about the reader. A burst
  above 120 in a minute is ignored. `GET /stats` gives the counts of the last 14 days;
  `/health` gives today and the total.
- The browser tests mark their sessions as already counted, so a run against the live site does
  not add visits.

### Changed

- `deploy/start.sh` passes `IPO_VISITS=/data/visits.json`.

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
