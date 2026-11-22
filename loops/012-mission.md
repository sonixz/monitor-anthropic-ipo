# Loop 012 — A guided AI portfolio of $4,000, simulated first, in public · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-22, privacy part updated with the owner before go · save as `loops/012-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-012` · Repository: existing — inspect before changing · Size: large

## Objective
Give the owner a guided portfolio agent: a dedicated $4,000 CAD envelope, managed first on paper for 3 to 4 weeks. Each evening Claude says, for each signal and each held position, buy, wait, pass, hold, trim or exit, with the reasons; code sizes every position by fixed rules and computes repeatable metrics against a TSX index fund; a weekly review proposes rule changes the owner approves. The simulated portfolio is a model portfolio shown in public on the site and in the repository; privacy (a private store, a login, the Fly.io lock) is decided before any real money.

## Context
- The scanner (v0.13.0) gives daily signals on the top 50 of the S&P/TSX Composite with stops and targets from ATR; the daily run waits for GitHub to be connected to the owner's Claude account.
- The owner trades by hand on Wealthsimple, swing trading, margin account; the $4,000 is a dedicated envelope, not the whole portfolio.
- Public repository and an open fly.dev address (D-046): the owner chose to keep the repository public; the simulated portfolio has nothing to hide.
- The Second Brain is unavailable (its archivist has no API credits); lessons go there when it is back.

## Request (user’s words)
> "Si je voulais me faire, par exemple, un portfolio, OK, puis là, je veux vraiment que ça soit AI analyzed, OK? Avec toutes des métriques repeatable, puis tout ça, puis je veux de l'apprentissage. On pourrait même utiliser un second brain dédié… donner à mon agent AI, donner à mon dashboard, à toi, un portfolio de comme 4000 $… tu me ferais des recommandations par rapport au signal. Est-ce que tu attends? Est-ce que tu l'achètes? … combien j'en achète? … je mettrais une authentification… ça serait privé… J'aimerais que ça soit guidé… moi, je fais le choix, de prendre les ordres sur WaySimple ou pas, puis je te le dis après. Fait que là, toi, tu mets tout ça à jour" Answers: simulation 3-4 weeks; "ca pourrais etre 10%. mais 4 ou 5 positions en meme temps. le 4000$ est dedier pour ca"; no leverage at first; private repo + login + lock, then: "le repo peux reste open. J'ai rien vraiment a cacher la dedans non?"

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Sizing is computed by code from versioned rules, never typed by the AI: at most 5 positions, each about 20% of the envelope's value, the loss at the stop never above 10% of the envelope, no leverage.
- Every recommendation names its signal, its size, its risk at the stop and its reasons; every simulated fill uses the next session's open from the same bars, so results are repeatable.
- Metrics are computed by code and shown with their sample size: return, against holding a TSX index fund (XIC) over the same days, win rate, average R, expectancy, worst drawdown.
- No real holdings of the owner reach the public repository or a public page; the simulated portfolio is labeled as simulated everywhere.
- The owner decides: rule changes are proposed by the AI with figures and applied only after the owner's yes; real orders are the owner's.

## Decisions
### Confirmed by the user — requirements
- **Start:** A paper portfolio of $4,000 CAD for 3 to 4 weeks, following every recommendation; real money after the owner reviews the metrics. — Owner's answer.
- **Sizing:** At most 5 open positions; each entry sized to about 20% of the envelope's current value; the loss at the stop capped at 10% of the envelope; whole shares; no leverage. — Owner: "10%… 4 ou 5 positions en meme temps… le 4000$ est dedier"; no leverage at first.
- **Public repository, public model portfolio:** The repository stays public; the simulated portfolio is shown on the site. — Owner, 2026-11-22: "le repo peux reste open. J'ai rien vraiment a cacher la dedans non?"

### Deferred — do not build now
- **Privacy for real money:** a private store, Cloudflare Access on the portfolio page and the Fly.io lock, decided with the owner before real money (the vision still refuses showing the owner's holdings).

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Entry rule:** Enter only on buy or strong buy at medium or high confidence, with a free slot, at most 2 positions per sector; exit at the stop, the target, after 20 sessions, or when the signal turns to sell.
- **Benchmark:** iShares Core S&P/TSX Capped Composite (XIC), bought with the whole envelope on the first day, from the same Yahoo bars.
- **Learning:** A weekly review by Claude (what worked, what did not, by level, confidence and sector), stored in the repository and in the Second Brain when available; rule changes versioned and applied only on the owner's yes.

### Assumed — revisit if the environment says otherwise
- **Public signals:** The scanner stays public.

## Carried over — not finished
These items were not completed according to the previous report. They are not done.

- The daily run: scheduled in this session (weekdays about 16:47 Toronto), session-only, 7-day expiry; a durable Windows task is an option.
- Second Brain unavailable (archivist out of API credits): decisions since 2026-11-22 to file when it is back.

## Scope
- Rules file (versioned) and a sizing module with hand-checked tests.
- Paper ledger: trades, positions, cash, fills at the next open; equity curve; XIC benchmark.
- Daily recommendations file written by Claude with the signals, checked by code (sizes come from code).
- Metrics module: return, vs XIC, win rate, average R, expectancy, drawdown, exposure, each with its sample size.
- Weekly review file written by Claude; rule-change proposals.
- A /portfolio page on the site, public, labeled simulated.
- ROUTINE.md extended with the portfolio steps.

## Out of scope
- Placing orders or reading the Wealthsimple account: the owner trades by hand and tells Claude, which is what the promise asks (real orders are the owner's).
- Leverage and short selling: refused for now by the owner's answer; the sizing rules forbid them.
- Assets outside the envelope: the $4,000 envelope is the agent's whole scope, so the sizing promise applies in full to it.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

For this loop:
- **Discover:** Fills, positions and metrics from the bars the scanner already reads; XIC's bars from the same source.
- **Plan:** Show the owner the rules file and a worked sizing example before building.
- **Validate:** Replay three weeks of recorded bars: recommendations, fills, metrics, by hand for one trade.

## Acceptance criteria
- [ ] Experience: On a phone, the first screen shows today's recommendations (action, stock, shares, price, stop, target, risk in dollars) and the envelope's value against XIC.
- [ ] Experience: Telling Claude "I bought 11 FTS at 85.10" in a session is enough to update the real ledger once real money starts; the page shows it within 15 minutes.
- [ ] Experience: Opening a recommendation shows the sizing arithmetic step by step.
- [ ] Each evening the portfolio page shows the recommendations with shares, risk in dollars, stop and target, sized by code from the rules.
- [ ] The paper portfolio follows them with fills at the next open; its value, open positions and closed trades are on the page.
- [ ] Metrics against XIC with sample sizes, recomputed the same way from the same data.
- [ ] A weekly review exists with any rule change proposed, not applied without the owner's yes.
- [ ] The simulated portfolio is labeled as simulated wherever it appears; no real holdings anywhere.
- [ ] All checks pass, screenshots to the owner before release.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/012-mission.md` and the report as `loops/012-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-012.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- Few trades in 3-4 weeks: metrics will be mostly noise; the page must say so.
- The daily run lives in a session on the owner's PC (cron, expires after 7 days): it stops if the session closes or the PC sleeps.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/012-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-012"
}
```
