# DECISIONS · monitor-anthropic-ipo

> Significant choices, newest last. Status is **confirmed** only when the owner confirmed it; otherwise **proposed** (the agent's recommendation, applied until the owner says otherwise). Last reviewed: 2026-11-15 · Loop: loop-001

| Id | Date | Decision | Status |
| --- | --- | --- | --- |
| D-001 | 2026-11-15 | A smooth dashboard of a few panels, not an analyst book | confirmed |
| D-002 | 2026-11-15 | Terminal, code-like style, calm, not neon | confirmed |
| D-003 | 2026-11-15 | Python, FastAPI, SQLite; server-rendered HTML, small vanilla JS | confirmed |
| D-004 | 2026-11-15 | MIT license; public repository from the first commit | confirmed |
| D-005 | 2026-11-15 | Hosted on the Agent Manager machine; Loop 001 deploys there | confirmed |
| D-006 | 2026-11-15 | Four labels: FILED, CALC, PRESS, AI | proposed |
| D-007 | 2026-11-15 | Facts are extracted by a script into versioned JSON; the raw filing stays out of git | proposed |
| D-008 | 2026-11-15 | The page is rendered once at startup; inconsistent data stops the service | proposed |
| D-009 | 2026-11-15 | Strict Content-Security-Policy; source cards use the browser's popover | proposed |
| D-010 | 2026-11-15 | "Diluted" counts what is owed or granted, not what is reserved | proposed |
| D-011 | 2026-11-15 | Enterprise value treats the Amazon notes as shares, not debt | proposed |
| D-012 | 2026-11-15 | A fifth panel, LOSSES, beyond the four in the mission | proposed |
| D-013 | 2026-11-15 | Market data from a free source such as yfinance, behind an adapter | confirmed, not built |
| D-014 | 2026-11-15 | AI by OpenAI with the owner's capped key, plus an app-level budget | confirmed, not built |
| D-015 | 2026-11-15 | The owner's words appear in English, reworded, in repository documents | confirmed |

## D-001 · A smooth dashboard of a few panels
**Context.** The reference dashboard the owner looked at has 14 sections. **Decision.** A few panels, each answering a plain question: worth, contracts, valuation, growth. **Owner:** "I'd rather keep mine smoother"; "the five cards, and more". **Alternative.** Match the reference's depth; rejected as not what the owner wants. **Consequence.** Governance, competition and strategy are left to the filing for now.

## D-002 · Terminal style, not neon
**Decision.** Monospace, dark, one discreet accent, green and red only for changes. **Owner:** "a terminal, code-like look — not neon". **Consequence.** No decorative animation; contrast is checked automatically.

## D-003 · Stack
**Decision.** Python 3.12, FastAPI, SQLite; server-rendered HTML; plain CSS and a small script. **Owner:** "let's stay efficient and light". **Alternatives.** A JavaScript framework with a build step; rejected as heavier than the product needs. **Consequence.** SQLite is part of the stack but unused in Loop 001: nothing changes at runtime yet.

## D-004 · MIT, public from the first commit
**Owner:** "MIT". **Consequence.** No secret, contact address or internal access detail may enter the repository, the devlog or the page. Secret scanning runs in CI and in the pre-commit hooks.

## D-005 · Hosting, and deploying in Loop 001
**Context.** The Loop0 template says Loop 001 never deploys, and proposes a `fly.toml`. The owner's directive says "go live early", and the machine was already exposed with their approval. **Decision.** Loop 001 updates the service on that machine; no new exposure, no infrastructure change, no `fly.toml`, because Agent Manager owns the Fly.io app. **Owner:** "go, ok for the two arbitrations". **Consequence.** `LOOP.md` still carries the template's "never deploy" line; a later loop should ask Loop0 for a version that allows deployment within approved limits.

## D-006 · Four labels
**Decision.** FILED (copied from a filing), CALC (our arithmetic), PRESS (reported by news media), AI (an explanation written by a model; not used yet). **Why.** The reader must never guess what kind of statement a number is. **Deviation from the mission.** The mission planned FILED and CALC only for Loop 001; PRESS was needed for four reported figures (two valuations, two dates).

## D-007 · Extraction into versioned JSON
**Context.** sec.gov refuses automated downloads without a declared contact address, which cannot be in a public repository. **Decision.** The owner saves the filing by hand into `data/raw/` (ignored by git); `python -m ipo_monitor.extract` writes `data/facts/s1a2.json`, which is committed. Each fact has its value, page, section and the exact passage. A figure that cannot be found stops the extraction. **Alternatives.** Download at runtime (needs the contact as a secret; planned for the watcher). Type the numbers by hand (rejected: unverifiable). **Consequence.** A new amendment needs a manual save and a re-run until the watcher exists.

## D-008 · Render once, fail early
**Decision.** At startup the service loads the facts, runs 129 consistency checks, computes and renders the page once. Any failure stops the start, and the deploy script keeps the previous release. **Why.** "A failed check blocks the build instead of publishing a wrong figure." **Consequence.** A data change needs a restart.

## D-009 · Strict CSP, native popovers
**Decision.** `default-src 'none'`, scripts and styles from the site only, no inline style. Source cards are `popover` elements opened by `popovertarget`, so they work without JavaScript; the script only adds keys, hover and placement. **Consequence.** Bars are SVG with width attributes. Browsers older than 2024 show the numbers but cannot open the cards.

## D-010 · What "diluted" means here
**Context.** The press quotes about $1.02 trillion and up to $1.405 trillion from the same filing. **Decision.** Three counts are shown. *Outstanding*: shares that exist after the IPO. *Diluted*: plus everything already owed or granted (the remaining Amazon notes, stock options, RSUs, shares issued since September 30). *Press basis*: our reconstruction of the reported "fully diluted" figure, which adds 2.05 billion shares reserved for future grants and leaves out the 1.56 billion shares owed to Amazon. **Why.** A reserved share has no holder; an owed share does. **Open point.** Options and RSUs are counted in full, vested or not; this is the conservative reading.

## D-011 · Enterprise value
**Decision.** Enterprise value = diluted value − cash after the offering (filed, pro forma as adjusted) − cash from option exercises + borrowings drawn (none). The Amazon convertible notes are already counted as shares, so they are not added as debt. Lease and compute commitments are shown in CONTRACTS and are not treated as debt. **Alternative.** Add lease liabilities; left out because the filing's $900.9B is mostly future spending, not a balance-sheet debt.

## D-012 · A fifth panel, LOSSES
**Context.** The owner asked why people call the company overvalued "given the 80 billion of losses". **Decision.** Add a small panel splitting the nine-month net loss into the fair-value accounting charge and the operating loss. **Deviation from the mission**, which listed four panels; the owner asked for "the five cards, and more".

## D-013 · Market data (not built)
**Owner:** "a free provider, like yfinance". **Plan.** Behind a replaceable adapter, labeled delayed and unofficial. **Risk.** yfinance is not an official API and Yahoo's terms limit redistribution.

## D-014 · AI provider (not built)
**Owner:** use the capped key already held in Agent Manager. **Blocked.** Agent Manager cannot yet assign a secret to an existing Online machine.

## D-015 · The owner's words in English
**Owner:** asked that their dictated French be corrected and put in English in the mission file. **Decision.** Repository documents give the owner's words reworded in English, with the meaning unchanged; the exact French quotes stay in the owner's notes.
