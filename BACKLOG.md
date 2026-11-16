# BACKLOG · monitor-anthropic-ipo

> What is left, in order. Recommendations until the owner turns them into a mission. Last reviewed: 2026-11-15 · after loop-001

## Before the first trade (reported for 2026-11-19)

1. **Market panel.** Price, change against the IPO price, volume and candles once the stock trades, from a free source behind a replaceable adapter (owner: "like yfinance"), labeled delayed and unofficial. VALUE and EV BRIDGE then recompute at the real price. Measure memory on the 256 MB machine first; fall back to a lighter HTTP call or 512 MB if needed.
2. **The final price.** The pricing is reported for 2026-11-18. When the final prospectus (424B4) is filed, save it, extend the extractor and switch the page from a range to one price.
3. **EDGAR watcher and "What changed".** Detect a new filing without anyone asking and show what moved. Needs a contact address for sec.gov as a secret on the machine.
4. **AI explanations**, following [ANALYSIS.md](ANALYSIS.md), labeled AI, each citing the figures it uses, with a daily budget in the application. Needs the owner's capped OpenAI key on the machine.
5. **The "what you pay" slider.** If growth slows to a chosen rate, how many years until the price is covered?

## Blocked on something outside this repository

- **Secrets on the machine.** Agent Manager cannot yet assign a secret to an existing Online machine. Workaround: the owner types it into the machine's session with a hidden prompt, into a root-only file on `/data`.
- **Automated deployment.** CI cannot reach the machine: Agent Manager owns access. Needs a design with the owner (a pull-based updater on the machine is the simplest candidate).

## After the listing

6. **"How We Build" page**: loops, features per loop, release history and screenshots, linking to the Loop0 site (owner's directive).
7. **Automated deployment** after tests pass, with deployment logs and rollback outside the machine (owner's directive).
8. **Storage and history** (SQLite): market data over time, and each version of the facts, so that "what changed" has a memory.
9. **Uptime monitoring** from outside the machine.
10. **More of the filing**: who controls the company (share classes, the Long-Term Benefit Trust), customer concentration, risk factors, cost mix by quarter.
11. **Comparables**: the same multiples for a few listed companies, from market data.
12. **Quarterly reports** (10-Q, 10-K) once the company files them: these are tagged in XBRL, which is easier to extract than the S-1.

## Smaller things

- Ask Loop0 for a `LOOP.md` that allows deployment within approved limits; the current file carries the template's "never deploy" line (see DECISIONS D-005).
- The owner to apply the branch protection recommended in CONTRIBUTING.md.
- Count options with the treasury-stock method as an alternative view, and say how much it changes the diluted figure.
- A light theme for print and bright rooms.
- Older browsers (before 2024) cannot open source cards: offer a plain list of sources as a fallback.
- Refuse to start when `uv.lock` and the installed packages differ (deploy safety).
