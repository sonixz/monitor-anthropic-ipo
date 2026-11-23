# Loop 016 — Your levels at the broker, and signals that know what you hold · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-23 · save as `loops/016-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-016` · Repository: existing — inspect before changing · Size: small

## Objective
The owner records, on /portfolio, the levels actually entered at the broker for each real position (stop market price, target alert, optional near-stop alert); the page shows that table as theirs next to the plan's, and the session panel uses them. The scanner and the orders show which stocks are already held (real or simulated), so a buy signal on a held stock reads as a position to manage, not a new entry.

## Context
- v0.18.0: real holdings come from the ledger (first fills Mon 2026-11-23: 1 DOL at 220.48, 4 FTS at 84.21); their stop and target are the plan's.
- The owner placed stop market orders (90 days) and price alerts in Wealthsimple; the exact prices differ a little from the plan.
- The scanner page is rendered when the board changes; the ledger upload already triggers a rebuild.

## Request (user’s words)
> "le prix etait pas exact, alors, il faudrait que je puisse modifier un peu dans l'interface pour me donner le bon tableau de stop market et des alertes." … "comment on gere les signal qui existe et ceux que nous avons deja place? Il faudrait afficher la position non? Comme en ce moment, on vois les signals buy et etc. meme si les position sont prise."

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Levels typed by the owner are labeled as theirs (YOURS) and never presented as computed or as a market value; the plan's levels stay visible beside them.
- Behind the login; levels and holdings stay on the server, never in the repository.
- Display only: the simulation and the track record do not read the owner's levels.
- A typo is refused with a reason (not a number, a stop above the target, a level far from the last close), never stored silently.

(loop0 flagged "Changing the simulation's rules or its stops" as out of scope against the third promise; it is a keyword overlap. Leaving the simulation untouched is what that promise requires.)

## Decisions
### Confirmed by the user — requirements
- **Levels form:** One form in the REAL section with, per position, stop market price, target alert and near-stop alert; empty means the plan's level applies. — Owner: 'modifier un peu dans l'interface pour me donner le bon tableau'.
- **Held stocks:** Show held positions on the scanner and the orders. — Owner: 'Il faudrait afficher la position non?'

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Storage:** A separate file /data/results/levels.json, written by the form; the ledger stays the record of fills. — An upload of the ledger must not erase the owner's levels.
- **How a held stock shows:** A HELD badge (REAL shares at price, SIM shares) on the scanner's TODAY and LIST rows; in TODAY a held buy says it is already held and shows the levels in force; in NEXT OPEN an order for a stock held for real says so.
- **Checks on a level:** Positive number, comma or dot accepted, within half of the last close either way, stop below the target alert, near-stop alert between them.
- **Near stop in session:** For a real position with a near-stop alert, 'near stop' means at or below that alert; otherwise half an ATR as before.

## Carried over — not finished
These items were not completed according to the previous report. They are not done.

- Monday's first daily run end to end (2026-11-23 about 17:17).
- Session prices and memory checked during a live session: requests seen on 2026-11-23 at 10:49 with zero failures; memory still to check (Tue 11:23).
- The daily cron expires about 2026-11-29.
- Second Brain unavailable: file D-047 to D-054.

## Scope
- Levels file and model, form POST /levels behind the login, refusals with a reason.
- REAL section: the table to enter at the broker (yours, plan beside it), and the form.
- Session panel: real rows use the owner's stop, target and near-stop alert.
- Scanner: HELD badge on TODAY and LIST; held buys read as positions to manage.
- NEXT OPEN: an order for a stock held for real is marked.
- Tests and e2e on a phone and a desktop.

## Out of scope
- Notifications.
- Reading orders from Wealthsimple.
- Changing the simulation's rules or its stops.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: On a phone, the owner sees for each real position the stop market price and the alerts to enter, in one table, without horizontal scrolling.
- [ ] Experience: Changing a level takes one field and one save; the page says saved, or why it was refused.
- [ ] Experience: On the scanner, a held stock is recognisable at a glance by a word, not colour alone.
- [ ] Saved levels show as YOURS in the REAL table with the plan's level beside them; empty fields fall back to the plan.
- [ ] Refused inputs (text, a stop above the target, a level more than half away from the last close) leave the file unchanged and show the reason.
- [ ] The session panel flags a real position with the owner's levels (tested with a recorded session).
- [ ] A held stock carries a HELD badge on the scanner's TODAY and LIST, with real shares and price.
- [ ] An upload of the ledger does not erase the levels.
- [ ] All checks pass; screenshots to the owner before release.
- [ ] Real use in a real browser on a phone and a desktop, screenshots in the devlog.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/016-mission.md` and the report as `loops/016-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-016.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- The scanner page is cached: it must be redrawn when the levels or the ledger change.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/016-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-016"
}
```
