# Loop 015 — A price during the session for open positions · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-22 · save as `loops/015-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-015` · Repository: existing — inspect before changing · Size: small

## Objective
During market hours, the portfolio page shows a recent price for each open position (simulated and real), with its time, its change since entry and how far it stands from its stop and its target, so the owner sees at a glance when a position nears or reaches a level. Display only: the simulation and the track record still use daily closes.

## Context
- v0.17.0: private portal, simulated $4,000 portfolio from daily bars, a ledger of real orders (empty), discipline checklist and journal.
- The server reads daily closes once after 16:20 Toronto and result files every 15 minutes; nothing moves during the session.
- market.py already read a 5-minute Yahoo chart for ANT during the session (Loop 009), with the plain user agent.
- The simulation assumes stop and target are standing orders at the broker; the owner is told to place the stop in Wealthsimple.

## Request (user’s words)
> "Si a mettons il est 11h20 et que une position arrive a son tp. Il se passe quoi?" … "Mais mon dashboard en ligne se refresh plusieurs fois par jour ou quoi?" … "Oui jaime ca. Un prix en séance pour les postion ouverte". Notifications: "Pas d'alerte pour l'instant".

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- The price is labeled MARKET with its source, its time and that it may be delayed; it is never typed and never a placeholder (a price with no volume does not count).
- Outside the session or when the source fails, the page says so and shows the last close; it never shows an old price as current.
- Display only: no simulated fill, score or signal changes from a price during the session.
- Behind the login; no position or price in the repository.

(loop0 flagged "Using session prices in the simulation" as out of scope against these promises; it is a keyword overlap. Keeping session prices out of the simulation is what the third promise requires.)

## Decisions
### Confirmed by the user — requirements
- **Notifications:** None in this loop. — Owner: 'Pas d'alerte pour l'instant'.
- **Which stocks:** Open positions only: simulated positions and the owner's real holdings from the ledger; at most ten symbols. — Owner: 'pour les positions ouvertes'.

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Cadence:** Every 5 minutes on weekdays from 9:30 to 16:00 Toronto, one request per symbol, nothing outside the session. — Light on a 256 MB machine and on Yahoo; swing trading does not need seconds.
- **What a row shows:** Price and time, change since entry in % and in R, distance to stop and target in %, and a state: near stop (within half an ATR of it), target reached, stop reached (by the session's high or low so far).
- **Refresh of the page:** The page shows the time of the price; no automatic reload (the owner reloads). No JavaScript needed.

## Carried over — not finished
These items were not completed according to the previous report. They are not done.

- Real use of the discipline checklist on the live site by the owner (Mon 2026-11-23).
- The evening run reading the discipline status (Mon 2026-11-23).
- Watch Monday's first daily run end to end.
- The session cron expires about 2026-11-29.
- Second Brain unavailable: file D-047 to D-053.

## Scope
- A session watcher in the scanner: during market hours, read a recent price (5-minute chart, regular session) for the open positions' symbols; keep the last good one in memory with its time.
- On /portfolio, for each open position (simulated and real): price, time, change since entry, distance to stop and target, a state (near stop, target reached, stop reached during the session); a SESSION label and a 'may be delayed' note.
- /health: the session watcher's state (symbols, last read, failures).
- Tests on recorded answers; e2e on a phone and a desktop with a recorded session.

## Out of scope
- Notifications (push, SMS, e-mail): the owner said no for now.
- Using session prices in the simulation or the track record.
- Session prices for the 50 stocks of the scanner.
- Automatic page refresh.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: On a phone, each open position shows its price during the session, its time and its distance to stop and target in one row, without horizontal scrolling.
- [ ] Experience: A position at its target or near its stop stands out without reading numbers (a word and a mark, not colour alone).
- [ ] Experience: Outside market hours the owner sees 'session closed' and the last close, never a stale price presented as live.
- [ ] During a recorded session, the portfolio page shows each open position's price and time from the recorded answer, and the distances match a hand calculation.
- [ ] A recorded day where the low crosses the stop shows 'stop reached'; one where the high crosses the target shows 'target reached'.
- [ ] Outside the session, or when the source fails, the page says so and shows the last close.
- [ ] A price with zero volume is never shown.
- [ ] No session request is made outside 9:30 to 16:00 Toronto on weekdays, checked by a test.
- [ ] Memory on the 256 MB machine stays within its usual range during a live session (checked on the first trading day after release).
- [ ] All checks pass; screenshots to the owner before release.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/015-mission.md` and the report as `loops/015-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-015.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- Yahoo may delay TSX quotes or refuse frequent requests; the page names the delay and the source.
- No open position exists until the first simulated fills on Mon 2026-11-23: the live check waits for them.
- Market holidays: the watcher must not treat a closed day as a session (no new bar means closed).

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/015-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-015"
}
```
