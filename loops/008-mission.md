# Loop 008 — Amendment No. 3 on the page, and versions you can see: which filing, since when, what changed · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-17 · save as `loops/008-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-008` · Repository: existing — inspect before changing · Size: medium

## Objective
Before pricing (reported 2026-11-18), the page takes its figures from Form S-1/A Amendment No. 3, filed 2026-11-17, instead of Amendment No. 2. Nothing is wiped in silence: the top of the page says which filing the figures come from and since when, and a CHANGES panel lists every figure that changed between the two filings, the old and the new value each in the filing's own words with its source.

## Context
- Live: v0.7.1 at https://antipo.watch, figures from Amendment No. 2 (data/facts/s1a2.json, 340 facts, 159 checks).
- The owner saved Amendment No. 3 into data/raw/sec/. A sentence diff shows: same price range ($70-$78), same shares offered (825,000,000), same symbol; Nasdaq listing now approved; the lock-up table now splits each step into Class A, Class N and a total; 3.6 billion became 3.7 billion shares eligible before 180 days; stock-based compensation now estimated (about $3.5B and $3.0B at $74); a new paragraph on Amazon and Google holdings; the 2026 Plan reserve reworded.
- The extractor stops on three changed wordings (listing, 2026 Plan reserve, lock-up table). Two are adapted, uncommitted: each new pattern anchored on its own sentence, no check loosened.
- The code names the document 's1a2' in render.py and web.py; Facts.load reads data/facts/*.json, not subfolders.

## Request (user’s words)
> "Ouais, ok. [loop 008: Amendment No. 3] Puis j'aimerais ça, genre, si je ferais une petite section en haut, mettons pour faire du versioning. Tu sais, on viendrait mettre une date en haut tu sais, je sais pas où on wipe, on réécrit. J'aimerais peut-être ça avoir un versioning. Je sais pas si c'est simple à faire."

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Every number opens its source: an old value in CHANGES opens the Amendment No. 2 passage, the new one the Amendment No. 3 passage.
- No figure is changed in silence: a value that changed between filings is listed with both sides.
- A comparison never mixes meanings: each side is shown in the filing's own words (e.g. Class A only, or Class A and Class N).
- The notices stay visible; phone first: the value at the IPO price stays on the first screen.

## Decisions
### Confirmed by the user — requirements
- **Loop 008:** Move the page to Amendment No. 3 before pricing — Owner: "Ouais, ok."
- **Versioning:** A line at the top naming the filing and its date, and a list of what changed — Owner asked for a date at the top and versioning instead of wiping and rewriting.
- **Show before deploying:** Screenshots of the new top line and CHANGES go to the owner before release — Owner, Loop 007: "Modifie pas trop vite".

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Keeping old figures:** Earlier fact files move to data/facts/history/; the page compares them with the current file by fact id, at rendering — Nothing to write by hand; each side keeps its source.
- **Lock-up steps:** unlock.NN becomes the filing's total of Class A and Class N; the class columns become facts of their own; CHANGES shows each side's wording — Amendment No. 2 gave one column; No. 3 gives three, and the totals are what is comparable to what the page drew.

### Deferred — do not build now
- **New facts (stock compensation estimate, Amazon and Google holdings):** Not in this loop — Pricing is tomorrow: the switch and the versions first.

Note on loop0's warning: deferring new facts does not break "every number opens its source": the page shows no figure from those passages, so there is nothing unsourced; the promise applies to the values CHANGES shows, which are in scope.

## Carried over — not finished
These items were not completed according to the previous report. They are not done.

- A small empty space under CONTROL beside the taller CONTRACTS panel on a desktop.
- VISION.md still says ANT IPO Monitor: the owner's to change.
- A first-screen e2e case with a new-filing notice and a priced state.
- Owner looks at the live page (not run in Loop 007).

## Scope
- extract.py reads Amendment No. 3: listing approved, 2026 Plan reserve, the three-column lock-up table; tests on both wordings.
- data/facts/s1a3.json from the extractor; s1a2.json moves to data/facts/history/.
- The current filing found from the facts, not the name 's1a2' in code.
- versions: compare current FILED facts with each history file by id; changed, added, removed; document facts (date, accession, title) left out.
- Top line: figures from <filing>, filed <date>, with a link to CHANGES; a CHANGES panel listing changes with old and new as filed, each opening its source.
- The timeline and the filings notice follow the new current filing.
- Consistency checks pass on Amendment No. 3 (reconcile.py updated only where the filing changed).
- Release 0.8.0 after the owner sees screenshots; deploy under D-016; CHANGELOG, STATUS, ARCHITECTURE, DECISIONS, devlog loop-008, Second Brain.

## Out of scope
- New facts from Amendment No. 3 beyond those the page already shows.
- Reading filings automatically from EDGAR (the owner saves them).
- Colors and layout of other panels.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: A reader sees at the top, without scrolling on a phone, which filing the figures come from and its date.
- [ ] Experience: A reader who opens CHANGES sees each changed figure as before and after, and can open the source of either in one tap.
- [ ] The page states Amendment No. 3, filed Nov 17, 2026, and every FILED number opens a passage of Amendment No. 3.
- [ ] CHANGES lists the unlock steps and every other fact whose value differs, with both sides' wording and sources; unchanged facts are not listed.
- [ ] No new-filing notice for Amendment No. 3 itself.
- [ ] All consistency checks pass; unit and real-browser tests pass locally, in CI and against antipo.watch; the first-screen test passes.
- [ ] The owner saw the screenshots before release.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/008-mission.md` and the report as `loops/008-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-008.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- The three-column table may have rows where Class N is a dash or a total is cut across pages.
- Facts whose meaning changed (Class A only vs. A and N) could read as a change of value: each side shows its own wording.
- Pricing may happen during the loop: the price path must keep working with the new document.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/008-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-008"
}
```
