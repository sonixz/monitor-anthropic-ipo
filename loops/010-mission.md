# Loop 010 — AI signal scanner on the most traded CAD stocks · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-22 · save as `loops/010-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-010` · Repository: existing — inspect before changing · Size: large

## Objective
Turn antipo.watch into a public scanner: every trading day after the close, the most traded Canadian-dollar stocks each get a signal (strong buy, buy, neutral, sell, strong sell) with a confidence and reasons, written by Claude running on a schedule, every reason citing a figure computed by code, a filing or an article. Every signal is kept and scored afterwards. The ANT IPO page becomes one card, its detailed page archived.

## Context
- Owner decisions of 2026-11-21 and 2026-11-22 (Second Brain): an AI judges the signals; the signals are public; technical, fundamental and news signals; ANT goes into the scanner; the AI is Claude on a schedule, updating the site; the most traded stocks, ideally in CAD.
- Today the service (FastAPI, Jinja, v0.10.2) shows one stock, ANT, from SEC filings and a market watcher (Nasdaq.com, then Yahoo Finance, delayed and unofficial). Production is a Fly.io machine behind a Cloudflare Worker at antipo.watch; deploys go through an Agent Manager session.
- TSX companies file on SEDAR+, not with the SEC; SEDAR+ has no simple open feed. US companies behind CDRs file with the SEC.
- Free market data for the TSX and Cboe Canada (CDRs) is Yahoo Finance's unofficial, delayed chart data (.TO and .NE symbols); it may refuse requests without a browser session.

## Request (user’s words)
> "Hey, j'aimerais garder ma page, mais j'aimerais me faire un scanner pour des signaux d'achat et etc. Donc, on garde le domaine, la sandbox et tout. C'est juste au lieu de focus sur la IPO de ant on elargi et on focus sur plusieur stock, ce serais 100% AI. Ensuite, moi de mon cote quand les signaux sort fort je pourrais gerer un porte feuille manuellement sur mon wealth simple." / "Là, je prendrais les actions avec le plus de volume, ceux-là qui sont plus propices à faire du trading." / "Puis pour le process AI, c'est toi, là. C'est toi qui vas tout faire ça. C'est toi qui vas être cadencé. Puis c'est toi qui vas mettre à jour le site, là." / "Idéalement, on prendrait des actions en CAD." / "Ok go!"

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Every signal names its inputs: each reason cites a computed indicator (by id), a filing or an article (link and quoted words). A signal that cites nothing is refused by the code and not published.
- Prices, volumes and indicators come only from code reading a named source; the signal file written by Claude holds no typed price: numbers in its reasons are refs to facts.
- The track record is complete: every published signal is kept with the close on the day it was given, and the return after 5 and 20 trading days is computed by code, wins and losses alike.
- "Unofficial · not affiliated · not investment advice" and the signals' AI label are visible on every page that shows a signal.
- The site updates without the owner: a scheduled run scans, judges and publishes after each close; if a run fails, the site says the signals are from the last good run, with its date.

## Decisions
### Confirmed by the user — requirements
- **Who judges:** Claude, in a scheduled cloud run, writes the signal, the confidence and the reasons; no AI API key in the service. — Owner: "c'est toi qui vas tout faire ça… cadencé… mettre à jour le site".
- **Visibility:** Signals are public on antipo.watch. — Owner's answer, 2026-11-21.
- **ANT IPO page:** ANT becomes one card; the IPO page moves to /ant, unchanged. — Owner chose "it goes into the scanner"; the archive keeps its sources and HISTORY.

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Universe:** The 25 stocks with the highest 20-day average dollar volume (CAD) among a candidate list: the S&P/TSX 60 members and the CDRs on Cboe Canada; common shares and CDRs only, price at least $5; rebuilt weekly, entries and exits shown with dates. — Owner wants the most traded stocks, ideally in CAD; dollar volume avoids penny stocks; a sourced candidate list keeps the ranking checkable.
- **Signal scale:** Five levels (strong buy, buy, neutral, sell, strong sell) and a confidence of low, medium or high.
- **Signal timing:** One run per trading day, about 16:45 Toronto time, on the day's closes. — Delayed free data; the owner trades by hand, so a daily signal fits.
- **How a run reaches production:** The run commits a dated signal file to the repository; the service reads new signal files from the public repository on a timer and validates them before showing them. No new inbound access. — A cloud run has no access to the production machine. This is an infrastructure change and needs the owner's approval before it is built.
- **Fundamentals:** Loop 010 uses SEC filings for CDR companies and ANT, and the company's own results releases (cited as articles) for TSX names; reading SEDAR+ filings is deferred.

### Deferred — do not build now
- **Legal check on public signals:** The owner checks whether publishing general signals is allowed in Canada; until then the disclaimer is prominent. — Raised on 2026-11-21; not the agent's to decide.

## Carried over — not finished
These items were not completed according to the previous report. They are not done.

- Loop 009 paperwork: report, devlog and the 0.9.x and 0.10.x fixes (market placeholder, market panel before the first trade) not yet in a loop report.
- Stock compensation and Amazon/Google holdings facts not on the ANT page.
- Cloudflare token permission cleanup; X composer card check.
- Later SEC filings for ANT (8-K, 10-Q) listed but not read.

## Scope
- Candidate list (S&P/TSX 60 and Cboe Canada CDRs) as a data file with its sources; weekly ranking by 20-day dollar volume, computed by code.
- Daily bars from Yahoo Finance for each stock in the list (named, delayed, unofficial), with recorded answers for tests.
- Indicators computed in calc code with formulas and hand-checked tests: moving averages (20, 50, 200 days), RSI 14, 20-day return, volume against its 20-day average, distance from the 52-week high and low.
- A per-stock dossier the service publishes (JSON): the indicators, recent filings and results dates, all as sourced facts.
- A signal file format (data/signals/YYYY-MM-DD.json) and its validator: allowed levels, every reason with a ref to a fact or a source with link and quote, no typed numbers outside refs.
- The scheduled routine: a cloud Claude run each trading day that reads the dossiers, looks up news, writes and validates the signal file, and commits it.
- The service reads validated signal files (method per the decision above, after the owner's approval) and shows them.
- Track record: each signal with its close, and the return after 5 and 20 trading days, computed by code; a summary by level.
- New home page: today's signals, the list with entries and exits, the track record; one card per stock; ANT's card links to /ant.
- The first real run, done by hand in a session, then the first scheduled run observed live.

## Out of scope
- Orders or any link to Wealthsimple: the owner trades by hand (the vision refuses being a broker).
- Intraday or real-time signals: the free data is delayed and the owner trades by hand; a daily signal keeps the promise.
- Reading SEDAR+ filings: no simple open feed; results releases cited as articles keep every reason sourced.
- Alerts (e-mail, phone): asked for later ("quand les signaux sortent forts"); the page itself shows strong signals first.
- US-listed shares in USD (other than ANT's card): the owner prefers CAD; CDRs cover the large US names.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

For this loop:
- **Discover:** Check what Yahoo Finance answers for .TO and .NE symbols from the production machine and from a cloud run (rate limits, fields, delay). Find the sources for the S&P/TSX 60 members and the CDR list; open them; record their links. Check what the schedule tooling allows: cron in Toronto time, repository write access, how long a run may take.
- **Plan:** Present the publishing method (cloud run → repository → service) to the owner for approval before building it.
- **Validate:** Replay a whole day from recorded answers: universe, indicators, dossier, a signal file, the page. A signal file with a typed price, a reason without a source, or an unknown level is refused, and the page keeps the last good signals. Real browser at 390 px and 1280 px; screenshots to the owner before release.
- **Document:** VISION.md as approved by the owner; PRODUCT, ARCHITECTURE (new flow diagram: schedule → dossier → Claude → signal file → service), INFRASTRUCTURE (the routine), DECISIONS (D-038 onward), HOW-IT-WORKS (where AI is now involved).

## Acceptance criteria
- [ ] Experience: On a 390×844 phone, the first screen shows today's strongest signals (stock, signal, confidence, one-line reason) without scrolling.
- [ ] Experience: One tap on a signal opens its reasons, each with its source card (computed figure, filing or article link).
- [ ] Experience: The track record shows, for each past signal, the date, the signal, the close then, and the change after 5 and 20 trading days, plus a summary by signal type.
- [ ] Experience: The page says when the signals were written and by whom ("Claude, scheduled run"), and when the next run is due.
- [ ] Experience: The ANT IPO page is still reachable from ANT's card, unchanged.
- [ ] antipo.watch shows today's signals for the 25 most traded CAD stocks, each with a level, a confidence and at least one sourced reason.
- [ ] Every reason opens a source card: a computed indicator with its formula and inputs, or a filing or article with its link and quoted words.
- [ ] The list of 25 is computed by code from the candidate list, and the page shows the ranking date and the latest entries and exits.
- [ ] A scheduled run produced and published a day's signals with nobody in the session, and the page names that run and its time.
- [ ] The track record lists every published signal with its close, and the return after 5 and 20 trading days once they have passed.
- [ ] A malformed signal file is refused, and the page says the signals are from the last good run.
- [ ] The ANT IPO page is reachable at /ant and unchanged; ANT has a card in the scanner.
- [ ] "Not investment advice" and the AI label are visible on the first screen of the home page on a phone.
- [ ] All checks pass: format, lint, types, unit tests, e2e at 390 px and 1280 px, CI; screenshots shown to the owner before the release.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/010-mission.md` and the report as `loops/010-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-010.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- Legal: public buy/sell signals may count as investment advice in Canada; the owner's check is pending.
- Yahoo Finance may refuse requests or change its answers; the site must say the data is missing rather than show stale prices as current.
- AI judgment is not proven to beat the market; the track record is the honest answer, and early results will be noise.
- A scheduled run can fail (quota, outage) or write a bad file; validation and the "last good run" notice cover it.
- Cost: each daily run uses the owner's Claude plan.
- Large loop: it may be split (scanner and page first, schedule and publishing second) if the publishing method waits on approval.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/010-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-010"
}
```
