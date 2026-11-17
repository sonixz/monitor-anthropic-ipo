# Loop 008a — Up to date, at a glance: the last check and the filing in the header · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-17 · save as `loops/008a-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-008a` · Repository: existing — inspect before changing · Size: small

## Objective
A reader sees in the header, without looking for it, that the page is up to date: when the SEC's list was last checked and which filing the figures come from; and, when a newer filing exists, that it is not read yet.

## Context
- v0.8.0 live: the overview says the filing and its date and, under filings, 'watching the SEC · latest: ... · checked HH:MM ET'.
- The page is rendered again after each check of the SEC's list (every ten minutes) and of the market.
- The phone's first screen must keep the value at the IPO price; the hero was tightened in 0.7.1.

## Request (user’s words)
> "Est-ce qu'on pourrait mettre en haut, mettons, last time field, mettons, qu'on voit que c'est à jour, là. Là, on le voit pas tant que c'est à jour. [...] on le voit dans Filings. Dans Overview, mais peut-être qu'on pourrait le mettre dans le header."

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Never claim more than the source said: 'up to date' only when the SEC's list was read and holds no newer prospectus than the filing the page reads.
- The notices stay visible; phone first: the value at the IPO price stays on the first screen.

## Decisions
### Confirmed by the user — requirements
- **Place:** One short line in the header, under the notices — Owner: 'peut-être qu'on pourrait le mettre dans le header'.
- **Show before deploying:** Screenshots first — Owner, Loop 007.

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Wording:** Watched, nothing newer: 'up to date · SEC checked HH:MM ET · figures: Amendment No. N, <date>'. Newer filing: 'new filing <form>, <date> · not read yet'. List unavailable: says so. Not watched: the filing and its date only. — Short enough for one or two phone lines; each state says only what the source said.

## Carried over — not finished
From loops/008-report.json, not in this loop's scope: the health fact count includes history values; stock compensation and Amazon/Google facts; the hole under CONTROL; VISION.md name; e2e fixtures for new-filing and priced states; the owner's look at the live page.

## Scope
- The header line in its four states, with tests for each.
- Phone first-screen test still passes; screenshots at 390 and 1280 px to the owner; release 0.8.1 under D-016.
- CHANGELOG, STATUS, devlog entry loop-008a, Second Brain.

## Out of scope
- The market price in the header (MARKET appears with the first quote).
- Changing the overview.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: On a phone, the first screen shows the name, the notices, the up-to-date line and the value at the IPO price.
- [ ] Each of the four states renders the right words, tested.
- [ ] Unit and real-browser tests pass locally, in CI and against antipo.watch.
- [ ] The owner saw the screenshots before release.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/008a-mission.md` and the report as `loops/008a-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-008a.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- The line pushes the value at the IPO price below the first screen on a phone.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/008a-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-008a"
}
```
