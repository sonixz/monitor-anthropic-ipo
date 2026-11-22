# DECISIONS · monitor-anthropic-ipo

> Significant choices, newest last. Status is **confirmed** only when the owner confirmed it; otherwise **proposed** (the agent's recommendation, applied until the owner says otherwise). Last reviewed: 2026-11-16 · Loop: loop-002

| Id | Date | Decision | Status |
| --- | --- | --- | --- |
| D-001 | 2026-11-15 | A smooth dashboard of a few panels, not an analyst book | confirmed |
| D-002 | 2026-11-15 | Terminal, code-like style, calm, not neon | confirmed |
| D-003 | 2026-11-15 | Python, FastAPI, SQLite; server-rendered HTML, small vanilla JS | confirmed |
| D-004 | 2026-11-15 | MIT license; public repository from the first commit | confirmed |
| D-005 | 2026-11-15 | Hosted on the Agent Manager machine; Loop 001 deploys there | confirmed |
| D-006 | 2026-11-15 | Four labels: FILED, CALC, PRESS, AI | proposed |
| D-007 | 2026-11-15 | Facts are extracted by a script into versioned JSON; the raw filing stays out of git | proposed |
| D-008 | 2026-11-15 | The page is rendered once at startup; inconsistent data stops the service | proposed |
| D-009 | 2026-11-15 | Strict Content-Security-Policy; source cards use the browser's popover | proposed |
| D-010 | 2026-11-15 | "Diluted" counts what is owed or granted, not what is reserved | proposed |
| D-011 | 2026-11-15 | Enterprise value treats the Amazon notes as shares, not debt | proposed |
| D-012 | 2026-11-15 | A fifth panel, LOSSES, beyond the four in the mission | proposed |
| D-013 | 2026-11-15 | Market data from a free source such as yfinance, behind an adapter | confirmed, not built |
| D-014 | 2026-11-15 | AI by OpenAI with the owner's capped key, plus an app-level budget | confirmed, not built |
| D-015 | 2026-11-15 | The owner's words appear in English, reworded, in repository documents | confirmed |
| D-016 | 2026-11-16 | One Loop 002 for charts, layout and the market panel; each release deployed once checks pass | confirmed by the owner |
| D-017 | 2026-11-16 | Charts are SVG drawn on the server, at phone width, without a library | proposed |
| D-018 | 2026-11-16 | Axis ticks are the only digits without a source | proposed |
| D-019 | 2026-11-16 | Layout follows the width of a panel; detail tables fold away on a phone | proposed |
| D-020 | 2026-11-16 | Market data: Nasdaq.com's quote service first, Yahoo Finance second, behind an adapter, asked sparingly | proposed |
| D-021 | 2026-11-16 | A price is shown only when the source names the company; otherwise nothing | proposed |
| D-022 | 2026-11-16 | Once the stock trades, the market panel comes first on the page | proposed |
| D-023 | 2026-11-16 | The service publishes by itself only what passes every check; from a final prospectus, only the price on its cover | proposed |
| D-024 | 2026-11-16 | A price read from the final prospectus replaces a price recorded from the press | proposed |
| D-025 | 2026-11-16 | The SEC contact address lives in a root-only file on the machine; an unusable address switches the watch off, it does not stop the service | proposed |
| D-026 | 2026-11-16 | The repository says how the system works and where AI is involved | confirmed by the owner |

## D-001 · A smooth dashboard of a few panels
**Context.** The reference dashboard the owner looked at has 14 sections. **Decision.** A few panels, each answering a plain question: worth, contracts, valuation, growth. **Owner:** "I'd rather keep mine smoother"; "the five cards, and more". **Alternative.** Match the reference's depth; rejected as not what the owner wants. **Consequence.** Governance, competition and strategy are left to the filing for now.

## D-002 · Terminal style, not neon
**Decision.** Monospace, dark, one discreet accent, green and red only for changes. **Owner:** "a terminal, code-like look — not neon". **Consequence.** No decorative animation; contrast is checked automatically.

## D-003 · Stack
**Decision.** Python 3.12, FastAPI, SQLite; server-rendered HTML; plain CSS and a small script. **Owner:** "let's stay efficient and light". **Alternatives.** A JavaScript framework with a build step; rejected as heavier than the product needs. **Consequence.** SQLite is part of the stack but unused in Loop 001: nothing changes at runtime yet.

## D-004 · MIT, public from the first commit
**Owner:** "MIT". **Consequence.** No secret, contact address or internal access detail may enter the repository, the devlog or the page. Secret scanning runs in CI and in the pre-commit hooks.

## D-005 · Hosting, and deploying in Loop 001
**Context.** The Loop0 template says Loop 001 never deploys, and proposes a `fly.toml`. The owner's directive says "go live early", and the machine was already exposed with their approval. **Decision.** Loop 001 updates the service on that machine; no new exposure, no infrastructure change, no `fly.toml`, because Agent Manager owns the Fly.io app. **Owner:** "go, ok for the two arbitrations". **Consequence.** `LOOP.md` still carries the template's "never deploy" line; a later loop should ask Loop0 for a version that allows deployment within approved limits.

## D-006 · Four labels
**Decision.** FILED (copied from a filing), CALC (our arithmetic), PRESS (reported by news media), AI (an explanation written by a model; not used yet). **Why.** The reader must never guess what kind of statement a number is. **Deviation from the mission.** The mission planned FILED and CALC only for Loop 001; PRESS was needed for four reported figures (two valuations, two dates).

## D-007 · Extraction into versioned JSON
**Context.** sec.gov refuses automated downloads without a declared contact address, which cannot be in a public repository. **Decision.** The owner saves the filing by hand into `data/raw/` (ignored by git); `python -m ipo_monitor.extract` writes `data/facts/s1a2.json`, which is committed. Each fact has its value, page, section and the exact passage. A figure that cannot be found stops the extraction. **Alternatives.** Download at runtime (needs the contact as a secret; planned for the watcher). Type the numbers by hand (rejected: unverifiable). **Consequence.** A new amendment needs a manual save and a re-run until the watcher exists.

## D-008 · Render once, fail early
**Decision.** At startup the service loads the facts, runs 129 consistency checks, computes and renders the page once. Any failure stops the start, and the deploy script keeps the previous release. **Why.** "A failed check blocks the build instead of publishing a wrong figure." **Consequence.** A data change needs a restart.

## D-009 · Strict CSP, native popovers
**Decision.** `default-src 'none'`, scripts and styles from the site only, no inline style. Source cards are `popover` elements opened by `popovertarget`, so they work without JavaScript; the script only adds keys, hover and placement. **Consequence.** Bars are SVG with width attributes. Browsers older than 2024 show the numbers but cannot open the cards.

## D-010 · What "diluted" means here
**Context.** The press quotes about $1.02 trillion and up to $1.405 trillion from the same filing. **Decision.** Three counts are shown. *Outstanding*: shares that exist after the IPO. *Diluted*: plus everything already owed or granted (the remaining Amazon notes, stock options, RSUs, shares issued since September 30). *Press basis*: our reconstruction of the reported "fully diluted" figure, which adds 2.05 billion shares reserved for future grants and leaves out the 1.56 billion shares owed to Amazon. **Why.** A reserved share has no holder; an owed share does. **Open point.** Options and RSUs are counted in full, vested or not; this is the conservative reading.

## D-011 · Enterprise value
**Decision.** Enterprise value = diluted value − cash after the offering (filed, pro forma as adjusted) − cash from option exercises + borrowings drawn (none). The Amazon convertible notes are already counted as shares, so they are not added as debt. Lease and compute commitments are shown in CONTRACTS and are not treated as debt. **Alternative.** Add lease liabilities; left out because the filing's $900.9B is mostly future spending, not a balance-sheet debt.

## D-012 · A fifth panel, LOSSES
**Context.** The owner asked why people call the company overvalued "given the 80 billion of losses". **Decision.** Add a small panel splitting the nine-month net loss into the fair-value accounting charge and the operating loss. **Deviation from the mission**, which listed four panels; the owner asked for "the five cards, and more".

## D-013 · Market data (not built)
**Owner:** "a free provider, like yfinance". **Plan.** Behind a replaceable adapter, labeled delayed and unofficial. **Risk.** yfinance is not an official API and Yahoo's terms limit redistribution.

## D-014 · AI provider (not built)
**Owner:** use the capped key already held in Agent Manager. **Blocked.** Agent Manager cannot yet assign a secret to an existing Online machine.

## D-015 · The owner's words in English
**Owner:** asked that their dictated French be corrected and put in English in the mission file. **Decision.** Repository documents give the owner's words reworded in English, with the meaning unchanged; the exact French quotes stay in the owner's notes.

## D-016 · One Loop 002, deployed as it goes
**Owner (2026-11-16):** loves the result, asks for a better layout and better behaviour on phones, says "Go!", then adds charts. **Assumed while the owner is away:** charts, layout and the market panel announced for the listing are one Loop 002, released twice (0.2.0, then 0.3.0), and each release is deployed on the existing machine once every check passes, as approved for Loop 001. No new exposure or infrastructure. **Confirmed by the owner (2026-11-16).** Asked whether each version whose checks all pass (local tests, GitHub, the health check on the machine) may go live without them, also while they are away, the owner answered: "Yes, deploy on your own." **Consequence.** The agent deploys when everything is green, tells the owner afterwards and rolls back if the site stops answering. Changes of access, exposure or infrastructure still need the owner's approval each time.

## D-017 · Charts drawn on the server
**Context.** The owner asked for charts and curves; the Content-Security-Policy forbids inline styles; the page must stay light and work without JavaScript; every value must keep its source. **Decision.** A small Python module (`charts.py`) writes SVG with attributes only. Each mark carries the id of its fact or calculation and opens the same source card as the number. Charts are designed 320 units wide and shown side by side on wider screens, so their text stays readable on a phone. **Alternatives.** A JavaScript chart library (heavier, needs script to show anything, harder to tie to sources); one wide chart per panel shrunk on phones (unreadable labels). **Colors.** Two series colors, `#5a8fd6` and `#cf7a3a`, passed the color-blind validator against the panel surface; green and red stay reserved for the sign of a value.

## D-018 · Axis ticks are scale marks
**Context.** The rule of Loop 001: no digit on the page without a source. A chart axis needs round values that are not facts. **Decision.** Tick labels are the single exception. They carry `data-tick`, and a test accepts them only inside the axis of a chart. Values printed on a chart are not ticks: they carry `data-ref` and open their source card.

## D-019 · Layout by panel width, tables folded on a phone
**Context.** On a phone the owner had to scroll a table sideways; on a laptop two panels side by side are each as narrow as a phone. **Decision.** Breakpoints are container queries on the panel. Below 540 px of panel width, bars go under their labels and a chart sits above its table. The eight-column quarterly table is two tables at every size. On a phone, the tables that repeat a chart start folded behind a line that names them; without JavaScript they stay open. **Trade-off.** A phone page is longer than before (about nine screens instead of six) because it now carries nine charts; the panel bar and the folded tables keep it navigable.

## D-020 · The market source
**Owner (Loop 0):** "a free provider, like yfinance". **Decision.** The service asks Yahoo Finance's chart data directly over HTTP, the feed that yfinance reads, with the Python standard library: no pandas or numpy on a 256 MB machine. The source sits behind a small interface (`market.Source`) and is chosen by `IPO_MARKET`. **Found on 2026-11-16.** The source already lists ANT as "Anthropic, PBC" on Nasdaq, without a price. It limits how often one address may ask: it answered "too many requests" to this workstation after about ten questions in a quarter of an hour. So the service asks every five minutes before the listing, every two minutes while the market is open, every thirty minutes when it is closed, and waits longer and longer while the source fails. **Changed the same day (0.3.1).** Minutes after the first deployment the source refused the production machine too, with the same "too many requests". The quote service behind nasdaq.com answered from both places, for a listed symbol and for ANT ("Symbol not exists" today). It is now asked first, and Yahoo Finance only if it fails. The page names the source that answered. **Risk.** Unofficial data, Yahoo's terms limit redistribution; every market value is labeled delayed and unofficial with its source.

## D-021 · Never the price of someone else
**Context.** A symbol can belong to another company at a given source, or change. **Decision.** A price is shown only if the source's answer is for the symbol, names a company containing "Anthropic", is in dollars and is a positive number. Anything else is "source unavailable" and no price is shown. Once a quote has been shown, an answer without a price is treated as a failure of the source, and the last quote stays with a warning.

## D-022 · The market first, once it exists
**Context.** The mission asked that the first screen of a phone show the value at the IPO price and, once the stock trades, the market price too. Both do not fit one screen. **Decision.** When a quote exists, the MARKET panel comes first: price, change against the IPO price, value and enterprise value at that price. The values at the IPO price follow. **Departure from the mission**, to confirm by the owner. Until the final IPO price is recorded, the comparison uses the middle of the filed range and says so.

## D-023 · What the service may publish by itself
**Context.** The owner asked to make the dashboard automatic, and answered "ok go" to a plan whose limit was stated: the page must never show a wrong figure. **Decision (proposed).** The service publishes by itself only what passes every check; otherwise it keeps the page it had and says what it could not read. From a final prospectus it reads one figure, the offering price on the cover, and only if the form is a final prospectus of the registrant, the cover names the company, is not preliminary, gives the price in dollars and cents, states a total equal to the price times the shares on the same cover, and the price is not far from the filed range. **Alternative.** Extract every figure of the new filing automatically; rejected for now: the document does not exist yet, its figures change across hundreds of pages, and no check as simple as "price times shares" exists for them. **Consequence.** After the final prospectus the page shows the final price with share counts and cash still taken from Amendment No. 2, and says so, until an extraction reviewed by hand replaces them.

## D-024 · Filed price over press price
**Decision (proposed).** A price recorded by hand from the press on pricing night is replaced by the price of the final prospectus when the service reads it. **Why.** The prospectus is the legal document. **Consequence.** The source card of the price changes from PRESS to FILED on its own.

## D-025 · Where the contact address lives
**Context.** sec.gov asks automated clients for a contact address. It is the owner's, and Agent Manager cannot assign a secret to an existing machine. **Decision (proposed).** The owner types it into a root-only file on the machine's volume; the boot script reads known names only. The address is sent to sec.gov hosts only, never logged, never shown. An address that is not one e-mail address switches the filings watch off and logs why, without the value. **Departure.** Elsewhere an invalid setting stops the service at startup; here it does not, because a typing mistake in an optional secret must not take the public page down.

## D-027 · A richer front, from the filing only (Loop 004)
**Owner (2026-11-16):** asked for more figures at the top, a better navigation, a chart of where the offered shares go and other information that can be checked; then, to six proposals: "let's go, if it is all information you can validate and that is in the document." **Decision (confirmed).** Header strip, stage bar, SHARES, UNLOCK, CONTROL, TIMELINE, a project mark. Every new figure is a FILED fact or a CALC.

## D-028 · The stage of the IPO, not a countdown (proposed)
The header shows the stage reached from events the service sees (filings, final prospectus, first quote) and the dates the press reported. A countdown would be stale on a page rendered on the server, or need a script, and a clock proves nothing.

## D-029 · Lock-up steps as the filing words them (proposed)
No calendar date for the steps: they count from the final prospectus, not dated yet, or from results releases. The chart shows each step's maximum; no total, because the filing does not say the steps add up (their sum, 15.5 billion, is larger than the 13.1 billion shares outstanding plus those that options and RSUs could add).

## D-030 · On a phone, the strip replaces two status lines (proposed)
The strip at the top gives the offer and the dates, so the "offer" and "listing" lines are hidden on a phone, and the legend keeps its tags only. This keeps the value at the IPO price on the first screen, as PRODUCT.md requires. The panel bar scrolls inside itself.

## D-031 · The project's own mark (proposed)
A frame and a line that climbs in steps, in the page's palette. Nothing from Anthropic's logo or colors: the page is unofficial and must look it.

## D-032 · The overview counts days in the browser (owner, 2026-11-16)
**Owner:** asked for an overview section: "waiting for IPO", an approximate timeline, the share price, the last fetch. **Decision.** The phase and the stage bar come from events the server sees (D-028 stands). The number of days to the reported pricing date is counted by the reader's browser, from the date on the page, because the page is cached on the server and cannot count days. Without script, the date alone is shown.

## D-033 · Counting visits without tracking anyone (owner asked; the method is proposed)
**Owner (2026-11-16):** wants to measure visits and show a live count, public, in the footer or a log tab. **Proposed method.** The page's script calls `POST /seen` once per browser session (a flag in the session storage of the reader's own browser); the service keeps a number per day and nothing else: no cookie, no address, no user agent, no third-party analytics. Robots that do not run scripts are not counted; a burst above 120 a minute is ignored. The counts are approximate and the footer says how they are made. Alternatives: a hosted analytics service (sends readers' data to a third party), counting requests in the logs (counts robots and reloads).

## D-026 · The repository explains the system, AI included
**Owner (2026-11-16):** asked for the public repository to be well documented, with the link and the workflows, then asked where AI is involved and whether a hosted AI service is used, and to document how the system works directly in the repository. **Decision.** [HOW-IT-WORKS.md](HOW-IT-WORKS.md) tells it in plain language: the path of a figure, who does what, where AI is involved (at build time, as the coding agent) and where it is not (the live service runs no model), what runs by itself, the workflows. The README is the front page and links to it.

## D-034 · antipo.watch through Cloudflare and a Worker (Loop 005)
**Owner (2026-11-16):** bought antipo.watch, moved its name servers to Cloudflare and asked to set up the DNS and the certificate, with only a Cloudflare API token; every step to be recorded in the Second Brain so that Loop0 can make a DNS expert of it. **Decision (domain confirmed; routing proposed).** Proxied DNS records and a Worker that relays to the fly.dev address. **Why.** Fly.io terminates TLS only for names it has a certificate for, and adding one needs Fly.io access that Agent Manager does not give; the Worker calls the app by its fly.dev name. **Alternatives.** `fly certs add` and a CNAME (needs Fly.io access); Cloudflare Origin Rules rewriting the host and SNI (depends on the plan). **Consequences.** About half a second more before the first byte; the page must reach readers unchanged, so the Worker adds `no-transform` and the browser check and e-mail rewriting are off. antipo.watch is the main address; fly.dev stays.

## D-035 · Rings for parts of one whole; a centered hero; UNLOCK full width (Loop 007)
**Owner (2026-11-17):** asked for a light, centered hero under the name Anthropic IPO Watch, a line that explains the keys, a way to open or fold everything, UNLOCK wider, and "not a bar chart, a pie chart" in the overview, naming CONTROL as a good candidate; and to see screenshots before anything is deployed. **Decision (hero, name, rings confirmed; placement proposed).** Rings (donuts) with three slices where the figures are parts of one whole: votes by class in CONTROL, holders after the IPO in the overview. The value in the centre is a sourced number; thin slices are labeled in the table, not on the ring. The overview ring is hidden on phones and narrow windows, so the value at the IPO price stays on the first screen; the same figures are in SHARES. UNLOCK spans both columns. **Alternatives.** A pie without a hole (no room for the centre value); keeping the stacked bar in CONTROL (the owner preferred a pie). **Consequences.** A small hole remains under CONTROL beside the taller CONTRACTS panel on a desktop; shown to the owner, who approved the release.

## D-036 · Earlier filings are kept and compared, never overwritten (Loop 008)
**Owner (2026-11-17):** asked to move the page to Amendment No. 3, and for versioning: a date at the top and a record of what changed instead of wiping and rewriting; then to fold the lock-up steps. **Decision (versioning and folding confirmed; method proposed).** The latest filing is `data/facts/<id>.json`; earlier ones move to `data/facts/history/`, extracted by the same code. At rendering, each pair of filings in a row is compared fact by fact; a fact whose value or wording differs is listed with both sides, each side added to the page under its own id (`s1a2:unlock.02`) so its card opens its own filing. Facts about the document itself (its date) are left out: the top line says it. When a filing counts a figure another way (the lock-up table split into Class A and Class N), the comparison shows each filing's words instead of hiding the change. **Alternatives.** A changelog written by hand (can drift from the data); showing only the latest figures (the owner's "wipe and rewrite"). **Consequences.** A new filing needs its old wording kept in the extractor; tests reproduce every filing.

## D-037 · The final prospectus is the page's filing; the range goes to HISTORY (Loop 009)
**Owner (2026-11-19):** saved the final prospectus (Form 424B4) and asked to put it all online ("mets-moi tout ça en ligne"), after the proposal to read it fully and to take the views across the price range off the main page. **Decision (owner's go; method proposed).** `data/facts/p424b4.json` is the current filing, extracted by the same code; Amendment No. 3 moves to `history/`. The final prospectus gives one price, so the page computes at the IPO price only: no range charts, no "implied value by price" table, no "each $1.00" adjustment. The range stays in HISTORY ("no longer given") with its sources. The ids `offering.price_mid`, `offering.net_proceeds_mid` and `offering.private_placement_shares_mid` keep their names but mean "at the price the filing's figures use": the assumed $74.00 in an amendment, the $83.00 IPO price in the final prospectus (each fact's title and period say which). The prospectus is dated Nov 18 and filed with the SEC on Nov 19: the page says "dated". The service's own reading of a final prospectus's cover is used only while the page's figures come from an amendment. **Alternatives.** Keeping the range views beside the final price (two prices on one page, confusing after pricing); new ids for the final figures (HISTORY would list them as removed and added instead of changed). **Consequences.** A later filing (a 10-Q, an 8-K) is listed by the watch but not read: the page's figures are the prospectus's until a new loop teaches the extractor that filing.

## D-038 · From one IPO to an AI signal scanner (owner, 2026-11-21 and 2026-11-22)
**Owner:** "keep my page, but build a scanner for buy signals… widen it to several stocks, 100% AI"; then "for the AI process, it's you… you run on a schedule… you update the site"; the most traded stocks, "ideally in CAD"; signals public; ANT goes into the scanner. **Decision (confirmed).** VISION.md rewritten (promise: AI trading signals on the most traded Canadian-dollar stocks, every reason sourced, every past signal scored). The earlier refusal "no buy or sell recommendation" is withdrawn at the owner's request. The home page becomes the scanner; the IPO page moves to `/ant`. **Consequences.** The legal side of public signals in Canada is the owner's to check; until then "not investment advice" and the AI label stay on the first screen.

## D-039 · Code computes, Claude judges, code checks (Loop 010)
**Decision (owner: "c'est toi"; method proposed).** Prices, volumes and indicators come only from code (`scan/bars.py`, `scan/indicators.py`). Claude writes one signal file per session (`data/signals/YYYY-MM-DD.json`): level, confidence, summary, reasons. A reason never types a digit: it names an indicator as `{key}`, which the page fills with the computed value, or it quotes an opened source with its link. `scan/signals.py` refuses a whole file that breaks a rule; the page keeps the last good file. **Alternatives.** An AI API called by the service (needs a key and a budget on the machine, and its text cannot be checked before it shows); free text from the AI (numbers could be invented). **Consequences.** No AI key in production; every published word of the AI passed the checks.

## D-040 · The candidates and the weekly list (Loop 010, widened in Loop 011)
**Decision (owner: the most traded, in CAD; then "a bigger list", top 50).** The list is the top N of a sourced candidate list by average value traded a day over 20 sessions (close × volume), close at least $5, ranked on the last session of each complete week, entries and exits named. Loop 010: top 25 of the S&P/TSX 60. Loop 011: top 50 of the S&P/TSX Composite (220 members, Wikipedia after TMX, April 20, 2026); the size is in the candidate file. **Alternatives.** Shares traded (favours penny stocks); a hand-picked list (not checkable). **Deviation.** CDRs (Canadian depositary receipts) were in the mission; Yahoo Finance gives them no daily history, so they wait for a source.

## D-041 · Signal files reach production through the public repository (Loop 010)
**Decision (owner's go, 2026-11-22).** The scheduled run commits the file to `main`; the service reads `data/signals/` from GitHub every 15 minutes without a token, as well as the files shipped with the release, and checks each file before showing it. No new inbound access to the machine. **Consequences.** A signal file is public as soon as it is pushed. A file must not name stocks the running release does not know: on 2026-11-22 a file for the new list of 50 reached the old release first and was refused, and the page showed no signals for about ten minutes. Deploy the code before pushing a file that depends on it.

## D-042 · Swing trading: stops and targets from ATR (Loop 011)
**Owner (2026-11-22):** "not day trading but short to medium term", on a margin account; chose stops and targets computed by code. **Decision (confirmed; multiples proposed).** For every buy and sell: entry = the session's close; stop = entry ∓ 2 × ATR(14); target = entry ± 3 × ATR(14); followed for up to 20 sessions. A sell means exit or avoid, not advice to sell short. The track record says which came first, from each later session's high and low; a session that reaches both counts as the stop. **Alternatives.** Percent stops (ignore each stock's volatility); stops written by the AI (numbers typed by the AI).

## D-043 · Yahoo Finance is asked with a plain client name (Loop 010)
**Decision.** Yahoo answers HTTP 429 to a request that claims to be desktop Chrome without behaving like one, and answers `antipo.watch/1.0 (+https://antipo.watch)`. The scanner and the ANT market watcher's Yahoo requests use the plain name; Nasdaq.com keeps the browser name it needs. Observed on 2026-11-22.

## D-044 · Builds install one package at a time (Loop 011)
**Decision.** On 2026-11-22 `deploy.sh` froze the 256 MB machine while building v0.11.0: the site was down about 12 minutes (14:13–14:25 UTC) until the machine was stopped and started; the previous release came back by itself. `deploy.sh` now sets `UV_CONCURRENT_INSTALLS=1`, `UV_CONCURRENT_DOWNLOADS=1` and `UV_CONCURRENT_BUILDS=1`; later builds kept the site up. **Alternative (owner's call).** A larger machine.

## D-045 · ANT leaves the scanner (owner, 2026-11-22)
**Owner:** asked to remove the elements tied to the Anthropic IPO from the scanner. **Decision (confirmed).** No ANT card, no link to the IPO page. The IPO page and its watchers keep running at `/ant`, unlinked, its canonical address `/ant`.

## D-046 · A login on the scanner waits for two holes to close (proposed, 2026-11-22)
**Owner:** wants the scanner behind a login (Cloudflare Access, a code by e-mail). **Proposal.** Before it means anything, two holes must close: the signal files are in the public repository, and the Fly.io address answers without Cloudflare (the origin lock the owner refused on 2026-11-17). Options for the owner: a private repository or another store for signals, and the origin lock or an equivalent. Deferred until the owner chooses.

## D-047 · A guided portfolio, simulated first (owner, 2026-11-22)
**Owner:** wants a portfolio of about $4,000 that the AI guides (buy, wait, how many), with repeatable metrics and learning, the orders placed by the owner. Answers: a simulation of 3 to 4 weeks first; "10%… 4 or 5 positions at the same time… the $4,000 is dedicated"; no leverage at first. **Decision (confirmed).** A paper envelope of $4,000 CAD from the Nov 20 decisions. Sizing by code: shares = the smallest of slot (20% of the envelope's value) ÷ close, loss allowed (10% of it) ÷ (close − stop), cash ÷ close. Fills at the next open; stop, target, 20 sessions and a sell signal close a position. **Proposed.** Entry only on buy or strong buy at medium or high confidence, two per sector at most; XIC as the benchmark; a weekly review on Fridays.

## D-048 · The repository stays public; the model portfolio is public (owner, 2026-11-22)
**Owner:** "the repo can stay open. I have nothing really to hide in there, right?" **Decision (confirmed).** The simulated portfolio is shown at `/portfolio` and its files are in the repository, labeled simulated everywhere. Privacy (a private store, Cloudflare Access, the Fly.io lock) is decided before any real money; the vision still refuses showing the owner's holdings.

## D-049 · The daily run lives in a session on the owner's PC (owner, 2026-11-22)
**Owner:** "can't it be here? We have everything we need." **Decision (confirmed).** A cron job in the working Claude Code session runs ROUTINE.md on weekdays about 16:47 Toronto time and pushes with the session's deploy key. **Consequences.** It runs only while that session is open and the PC awake, and expires after 7 days (re-armed by the agent). A durable Windows task, or a cloud routine after `/web-setup`, remain options.
