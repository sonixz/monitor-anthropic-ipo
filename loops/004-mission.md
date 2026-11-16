# Loop 004 — A richer front: the IPO at a glance, where the shares go, when they unlock, who controls the company · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-16 · save as `loops/004-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-004` · Repository: existing — inspect before changing · Size: medium

## Objective
Before pricing (reported for 2026-11-18), enrich the page without losing what the owner likes (dense, clean, code-like): a header with the key figures and the stage of the IPO, a navigation that follows the reader, and four new views taken from the filing the page already reads: the timeline of the IPO, where the offered shares go, when existing shares may be sold, and who controls the company. Every new number opens its source, like the others.

## Context
- Live: https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev, version 0.4.2; the filings watch went on 2026-11-16 23:29 UTC. Commit 76b95cf (after-hours wording) is on main, not released.
- The page reads Form S-1/A Amendment No. 2 (filed 2026-11-10), saved by the owner in data/raw/sec/ and extracted by extract.py into data/facts/s1a2.json.
- Already extracted: shares sold by the company (801,351,354) and by existing stockholders (23,648,646), the underwriters' option (123,750,000), the private placement ($26.0 billion, 351,351,348 shares at the midpoint), shares after the offering by class.
- Found in the filing and not extracted yet: the schedule of shares eligible for sale after the offering (lock-up releases), the classes of stock and their rights (A, N, T, F; the Long-Term Benefit Trust elects the Class T directors), indications of interest of directors and affiliates (up to $303 million), the private placement investors, the list of underwriters. The allocation among underwriters is blank in this amendment.
- The dates of pricing and first trade come from the press (CNBC), labeled PRESS; the filing dates come from EDGAR's list, which the service reads live.

## Request (user’s words)
> "est-ce qu'on pourrait enrichir un peu le header, enrichir un peu la navigation? J'aime en ce moment le site, là, il est vraiment bien, il est dense, il est clean, il est très code-like, j'aime ça. Est-ce que on pourrait mettre plus de stats en haut, tu sais, la date prévue [...] mettons une bar chart des distributions officielles. T'sais, où s'en vont ces 825 000 actions? [...] Quelle autre information on pourrait ajouter qu'on est capable de valider [...] un petit peu plus de visuel" — then, to the six proposals: "Ouais, t'as-tu des bloquants pour faire de 1 à 6? Let's go! Si c'est toute l'info que tu peux valider puis qui est dans l'input, dans le document, c'est bon, là."

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Every number is traced to its source: each new figure is a FILED fact copied by extract.py with its page and passage, or a CALC with its inputs.
- Nothing that is not in the filing or an opened source: no guessed allocation, no estimate of who sells.
- The notices stay: unofficial, not affiliated with Anthropic, not investment advice; footer "Built with the Loop0 Method". No Anthropic logo or brand colors: the mark is the project's own.
- The phone stays first: nothing scrolls sideways, the first screen still answers the main question.

## Decisions
### Confirmed by the user — requirements
- **Scope:** The six proposals: header stats, IPO timeline, where the shares go, lock-up schedule, who controls the company, indications of interest; plus a project mark and a navigation that follows the reader — Owner, 2026-11-16: "Let's go! Si c'est toute l'info que tu peux valider puis qui est dans l'input, dans le document, c'est bon"

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Stage of the IPO instead of a clock countdown:** The header shows the stage reached (filed, priced, trading) from events the service sees (filings, final prospectus, first quote), and the reported dates; no ticking countdown — The page is rendered on the server and cached until something changes; a countdown would be stale or need script, and an event is verifiable where a clock is not.
- **Lock-up chart:** Shares that may be sold, step by step, with relative dates as the filing words them ("27th day after the prospectus"), not converted into calendar dates — The prospectus date is not known yet and the later steps hang on the FY26 earnings release: a calendar date would be invented.
- **Project mark:** A small SVG wordmark drawn for the project, in the page's own palette — A little more visual identity without imitating Anthropic.

## Carried over — not finished
These items were not completed according to the previous report. They are not done.

- Release the after-hours wording (commit 76b95cf) and record the Nasdaq source at night.
- The owner's answer on D-017 to D-025; acceptance of Loop 003; About box of the repository.
- Record the final IPO price (reported 2026-11-18); watch the first trade (2026-11-19).
- After the first trade: deployment by GitHub, alerts, history.

## Scope
- Header: a project mark and a strip of key figures (price range, shares offered, amount raised, value at the range, reported pricing and trading dates) and a stage bar (S-1 filed, priced, trading) driven by what the service has seen.
- Navigation: a bar that stays at the top while scrolling, with the panels including the new ones, and shows where the reader is; works without script, keys kept on desktop.
- TIMELINE: the filings from EDGAR's list in order, then the reported pricing and trading dates, then the first lock-up steps.
- SHARES: where the offered shares go, as bars: new shares from the company, shares from existing stockholders, the underwriters' option, the private placement; the underwriters listed, their allocation shown as not filed yet.
- UNLOCK: the schedule of shares that may be sold after the offering, as a step chart and a table, with the filing's wording for each step.
- CONTROL: the classes of stock and what each can do, the role of the Long-Term Benefit Trust, the shares by class after the offering; and the indications of interest of insiders (up to $303 million).
- New facts copied by extract.py with page and passage; new calculations in calc.py with tests; new cross-checks in reconcile.py where figures can be compared.
- Release, deploy under D-016, check in a real browser against the live site.

## Out of scope
- Calendar dates for the lock-up steps.
- Allocation among underwriters (not filed yet).
- Any figure not in the filing or an opened article.
- Anthropic logos or brand colors.

Note on loop0's warnings: the three out-of-scope lines above are exclusions that the promise itself requires (no figure without a source, no brand imitation); they do not drop any promise.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: On a phone, the stage of the IPO and the next reported date are visible on the first screen.
- [ ] Experience: From anywhere on the page, one tap reaches any panel.
- [ ] Every new number on the page opens a source card; the test that forbids digits without a source still passes.
- [ ] Shares in the SHARES bars add up to the offering total stated in the filing, checked by reconcile.py.
- [ ] The lock-up steps match the filing's table, each with its wording.
- [ ] At 360 px nothing scrolls sideways; the header strip and the navigation fit; the first screen still shows the value at the IPO price.
- [ ] Unit and real-browser tests pass locally, on GitHub and against the live site; no serious accessibility issue.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/004-mission.md` and the report as `loops/004-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-004.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- The page gets long on a phone: fold the new tables behind their charts as the existing ones are.
- The lock-up table has many steps and footnotes: copy the steps, quote the footnotes, do not interpret them.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/004-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-004"
}
```
