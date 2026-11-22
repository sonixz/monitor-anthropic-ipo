# Loop 014 — Discipline mode: a daily checklist and a clean journal · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-22 · save as `loops/014-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-014` · Repository: existing — inspect before changing · Size: medium

## Objective
Give the owner a trading discipline routine inside the private portal: a TODAY section at the top of the portfolio with a morning and an evening checklist, a mood and a note, saved on the server; and a journal page, one row per trading day since the simulation started, missed days included, with streaks, assiduity and the gaps between the plan and the owner's real orders computed by code.

## Context
- v0.16.0: private portal behind a login, results on the server in /data/results, a simulated portfolio, a ledger for the owner's real orders (empty).
- The daily run lives in the working session and uploads results.

## Request (user’s words)
> "on pourrait mettre peut-être un mode discipline… tous les jours, on vient checker… on vient comme cocher… j'aimerais ça avoir une discipline de trading" then "on aurait une section to-day avec les cases à cocher puis les trucs à mettre… on enverrait tout ça dans un log… un log vraiment clean… une table qu'on a accès à tout l'historique… Toute la discipline avec les jours. Puis genre les jours qu'on n'a pas été assidus." Then: "Go".

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Every trading day has a row, checked or not; a missed day stays missed: only today and yesterday can be filled in.
- Gaps (an order outside the plan, a size above the advice) are computed by code from the ledger, never typed.
- Everything stays on the server behind the login; nothing in the repository.

## Decisions
### Confirmed by the user — requirements
- **Place:** TODAY at the top of /portfolio; the journal at /journal, linked from the portfolio. — Owner: 'une section to-day… un log… une table'.

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Checklist:** Morning: read the orders; orders placed, skipped on purpose (with a reason) or none planned; a stop entered for each position. Evening: no trade outside the plan; read the evening analysis. Mood 1 to 5 and a one-line note, optional.
- **Status of a day:** Complete when all five items are checked; partial when something is; missed when nothing was saved and the day is over. Weekends and market holidays have no row.
- **Editing:** Only today and yesterday (Toronto time) can be saved; earlier days are fixed.

## Carried over — not finished
These items were not completed according to the previous report. They are not done.

- The first daily run with uploads and the first simulated fills (Mon 2026-11-23).
- A sign-out link on the pages.
- The session cron expires 2026-11-29.
- Second Brain unavailable.

## Scope
- discipline.py: the day's entry, storage in /data/results/discipline, the rows of trading days, streaks, assiduity, gaps from the ledger.
- TODAY section and POST /discipline; /journal page; a sign-out link.
- The evening run mentions an unchecked morning in its summary; ROUTINE.md.
- Tests by hand for statuses, streaks, missed days and gaps; e2e on a phone.

## Out of scope
- Phone notifications or e-mail reminders: not possible from the site alone; a later loop if wanted.
- Editing past days: the journal must stay honest, which the promise requires.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: On a phone, the checklist fits in two screens, with large tap targets and one save button; it works without JavaScript.
- [ ] Experience: The journal shows today's streak, the best streak and assiduity at the top, then one row per day, newest first.
- [ ] Saving the checklist on a phone shows it checked on reload and in the journal.
- [ ] A trading day with nothing saved appears as missed in the journal once it is over.
- [ ] Streak and assiduity match a hand count on test data.
- [ ] An order outside the plan or above the advised size shows as a gap.
- [ ] All checks pass; screenshots to the owner before release.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/014-mission.md` and the report as `loops/014-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-014.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- Market holidays are not known in advance: a weekday with no session in the bars, once later sessions exist, has no row.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/014-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-014"
}
```
