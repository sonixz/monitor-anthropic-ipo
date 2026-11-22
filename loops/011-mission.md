# Loop 011 — Top 50 of the Composite, stops and targets, the daily run · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-22 · save as `loops/011-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-011` · Repository: existing — inspect before changing · Size: medium

## Objective
Make the scanner fit short-to-medium-term swing trading on a margin account: scan the 50 most traded stocks of the S&P/TSX Composite, give every buy a stop, a target and a holding period computed by code from the stock's volatility, score whether the stop or the target came first, and have Claude write the signals every weekday after the close with nobody in the session.

## Context
- Loop 010 (v0.11.0, live 2026-11-22): top 25 of the S&P/TSX 60, indicators, AI signal files with rules, track record after 5 and 20 sessions, the IPO page at /ant.
- Production is a 256 MB machine: a release build froze it once (2026-11-22); builds now run with uv's concurrency limited.
- The scheduled run needs GitHub linked to the owner's Claude account; not done yet.
- Signal files live in the public repository, and the Fly.io address answers without Cloudflare: a login on antipo.watch alone would not make signals private.

## Request (user’s words)
> "Quel genre de trading on fait avec ca? Jaimerais plus d'action, un plus gros listing. Aussi, ce serait pas du day trading mais court moyen terme. J'utiliserais un compte marge avec des frais mensuels. Aussi, on pourrais mettre une auth sur le portal au besoin." Answers: top 50 of the Composite; yes, stop and target; yes, scanner protected.

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Stops and targets are computed by code (ATR over 14 sessions and fixed multiples written in the code), never typed by the AI; each opens its formula.
- The track record scores every buy and sell against its stop and target, wins and losses alike, including signals that hit neither yet.
- Everything from Loop 010 holds: no typed number in a signal, every reason sourced, refused files never shown, the disclaimer visible.

## Decisions
### Confirmed by the user — requirements
- **Trading style:** Swing trading on daily closes, holding a few days to a few weeks; no intraday signals. — Owner: "pas du day trading mais court moyen terme".
- **List size:** Top 50 of the S&P/TSX Composite by 20-day value traded, close at least $5, weekly. — Owner's answer.
- **Stops and targets:** Every buy and sell gets a stop and a target from ATR(14) computed by code, with a holding period of up to 20 sessions; the track record checks which came first. — Owner's answer.

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **ATR multiples:** Stop at 2 × ATR from the entry close, target at 3 × ATR (reward to risk 1.5), holding up to 20 sessions. — Common swing-trading defaults; written in one place in the code and shown on every card.
- **Daily run:** A cloud routine on weekdays at 21:45 UTC (16:45 Toronto in winter; 17:45 in summer) that builds the dossier, writes the signal file, runs the check and pushes.

### Deferred — do not build now
- **Login on the scanner:** Cloudflare Access with a one-time e-mail code in front of the scanner, the IPO page public; built only after the owner chooses how to handle the public repository and the Fly.io address. — Owner wants it; but signal files in the public repo and the open fly.dev address would leave signals readable. Owner refused the origin lock on 2026-11-17.

## Carried over — not finished
These items were not completed according to the previous report. They are not done.

- Docs for Loop 010 (ARCHITECTURE, PRODUCT, INFRASTRUCTURE, DECISIONS D-038+, HOW-IT-WORKS), the Loop 010 report and devlog; Loop 009 paperwork.
- deploy.sh: limit uv concurrency so a build cannot freeze the machine.
- market.py still sends a Chrome user agent that Yahoo refuses.
- The live e2e test that expects "awaiting listing" on /ant; the /ant canonical address.
- CDRs: Yahoo has no daily history for them.

## Scope
- Candidate list: the S&P/TSX Composite members, from an opened source, with Yahoo symbols checked.
- Universe of 50; the page and the dossier adapt.
- ATR(14) indicator; stop, target and risk/reward computed in code for buys and sells.
- Track record: for each signal, whether the stop or the target was hit first within 20 sessions, or neither yet, from the daily highs and lows.
- The routine: prompt, schedule, and its first run observed live (needs GitHub linked).
- deploy.sh concurrency limits; market.py plain user agent; carried-over test fixes.

## Out of scope
- Position sizing or margin calculations for the owner: the site gives no personal advice and knows nothing of the owner's account.
- Short-selling advice: a sell means exit or avoid; the page says so.
- The login: deferred until the owner chooses how to close the two holes; the disclaimer stays.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: On a 390×844 phone, each of the strongest signals shows its level, confidence, entry close, stop and target without scrolling past the first two cards.
- [ ] Experience: The list of 50 is readable on a phone: the table scrolls inside itself, the page never scrolls sideways.
- [ ] Experience: Opening a buy shows the risk per share (entry minus stop) and the reward per share (target minus entry), each with its formula.
- [ ] antipo.watch lists 50 stocks of the S&P/TSX Composite ranked by value traded, with the ranking date and entries and exits.
- [ ] Every buy and sell shows entry, stop and target, each opening its formula; the multiples are visible.
- [ ] The track record shows, per signal, stop hit, target hit or still open, and a summary by level.
- [ ] A weekday run with nobody in the session wrote, checked and pushed a signal file, and the site showed it within 15 minutes.
- [ ] A build on the 256 MB machine no longer stops the site.
- [ ] All checks pass: format, lint, types, unit, e2e at 390 and 1280 px, CI; screenshots to the owner before release.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/011-mission.md` and the report as `loops/011-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-011.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- Yahoo may limit 60+ requests a day from one address.
- The routine depends on GitHub being linked and on the owner's plan quota.
- Margin magnifies losses; the track record is still empty.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/011-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-011"
}
```
