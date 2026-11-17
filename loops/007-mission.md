# Loop 007 — Branding pass: Anthropic IPO Watch everywhere, a light centered hero, rings for control and ownership, a calmer layout · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-17 · save as `loops/007-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-007` · Repository: existing — inspect before changing · Size: medium

## Objective
Make the page feel like one finished product under one name, without touching what the owner loves (colors, the dense code-like look, the mechanics): the name Anthropic IPO Watch everywhere, a light centered hero, a line that explains the keys, open/fold all for the tables, UNLOCK across the full width, and two clean rings (pie charts): who controls the votes, in CONTROL, and who owns the shares after the IPO, in the overview. Screenshots go to the owner before deployment.

## Context
- Live: https://antipo.watch, version 0.6.2 (Loop 006): share card for X, tab title Anthropic IPO Watch. The header still says ANT IPO MONITOR; the SEC client name, the app title and comments too.
- Charts are server-side SVG (charts.py, figures.py), 320 units wide, values through Numbers.mark and also in a table on the page.
- CONTROL shows votes as a stacked bar: Class F 50.1%, Class A 49.9%, of which IPO shares about 5.5%. SHARES shows holders after the IPO: existing 91.0%, IPO buyers 6.3%, private placement 2.7%.
- UNLOCK and CONTROL sit side by side in a two-column grid; UNLOCK is much taller.
- On a phone the tables behind charts start folded (app.js); the value at the IPO price must stay on the first screen (PRODUCT.md).

## Request (user’s words)
> "J'aimerais peut-être travailler un peu la mise en page. J'aimerais ça peut-être mettre une introduction en haut [...] un petit hero, mais vraiment léger [...] épuré en haut. On viendrait changer ça pour Anthropic, IPO, Watch. [...] mettre une petite ligne en dessous juste pour expliquer press [a letter] to move directly into the right place [...] un petit menu, mettons, reduce everything, ou extract all. [...] la tuile, là, unlock à côté de control. Unlock est super longue [...] on pourrait la mettre plus large [...] je vois dans le nom de la page, c'est Ant IPO Monitor, Anthropic IPO. J'aimerais ça faire une bonne passe pour tout consolider ça, puis que ça soit vraiment un produit fini et uniforme [...] Modifie pas trop vite." — "le petit hero en haut centré. Vraiment peut-être centré." — "j'aimerais ça peut-être dans l'overview avoir [...] pas une bar chart, une pie chart!" — "Control the Company. Ça serait un beau candidat, ça, pour une pie chart, non? Comment qu'on pourrait optimiser nos graphiques?" — "oui prépare et lance la loop 7"

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Every number on a chart opens its source and is also in a table on the page.
- The notices stay visible: unofficial, not affiliated with Anthropic, not investment advice.
- Phone first: nothing scrolls sideways; the value at the IPO price stays on the first screen.
- No Anthropic logo or brand colors.

## Decisions
### Confirmed by the user — requirements
- **Name:** Anthropic IPO Watch everywhere a reader or the SEC sees a name; the repository keeps its name — Owner, 2026-11-17
- **Hero:** Light and centered: the mark, the name, one line, the notices — Owner: "le petit hero en haut centré"
- **Pie charts:** Rings (donuts): votes by class in CONTROL; holders after the IPO in the overview, on wide screens — Owner asked for a pie in the overview and named CONTROL; parts of one whole, three slices
- **Show before deploying:** Screenshots at phone and desktop width go to the owner before release — Owner: "Modifie pas trop vite"

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Open/fold all:** Two small text buttons for the tables behind the charts, next to the keys hint; shown only when the script runs — Panels are not foldable; the tables are, and fold on phones.
- **Overview ring on phones:** Hidden under 640 px — The value at the IPO price must stay on the first screen; the same figures are in SHARES.
- **UNLOCK:** Full width under the other panels of its grid, chart beside its table — It is the tallest panel; side by side with CONTROL it leaves a hole.

## Scope
- Name: header wordmark ANTHROPIC IPO WATCH, app title, SEC client name, code comments, README title and docs that name the product.
- Centered light hero; tagline and notices under the name.
- Keys hint on desktop: press a letter to jump to a panel, ? for all keys; open all / fold all for the tables.
- UNLOCK spans both columns, chart beside its table; CONTROL beside CONTRACTS.
- charts.donut: a ring of slices, each a mark with its source, 2-unit gaps, a value in the centre; tests.
- CONTROL: ring of votes beside its table, replacing the stacked bar; overview: ring of holders after the IPO on wide screens.
- Screenshots at 390 and 1280 px sent to the owner before release; release 0.7.0 after the owner's look, deploy under D-016.
- Docs: CHANGELOG, STATUS, README screenshots if they change, DECISIONS, devlog loop-007, Second Brain.

## Out of scope
- Colors, fonts, the data and the mechanics.
- Renaming the repository.
- The origin lock (left to the DNS expert).

Note on loop0's warning: "colors" are out of scope because the page keeps its own palette unchanged; that palette has no Anthropic color, so the promise "no Anthropic logo or brand colors" holds and stays checked.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: On a phone, the first screen still shows the value at the IPO price, under a centered name.
- [ ] Experience: On a desktop, a new reader learns the keys from one line without opening help.
- [ ] Experience: CONTROL tells at a glance that one share holds half the votes.
- [ ] The name ANT IPO Monitor appears nowhere a reader or the SEC sees it.
- [ ] Each ring slice opens the same source card as the number in its table.
- [ ] At 360, 390 and 430 px nothing scrolls sideways; the first-screen test passes.
- [ ] UNLOCK spans the width on a desktop; no panel leaves a tall empty hole beside it.
- [ ] Unit and real-browser tests pass locally, in CI and against antipo.watch.
- [ ] The owner saw the screenshots before the release.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/007-mission.md` and the report as `loops/007-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-007.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- The full name may not fit at 360 px: check and shorten the letter spacing, not the name.
- A ring with a thin slice (2.7%) needs its label in the table, not on the slice.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/007-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-007"
}
```
