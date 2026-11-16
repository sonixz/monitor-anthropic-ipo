# BACKLOG · monitor-anthropic-ipo

> What is left, in order. Recommendations until the owner turns them into a mission. Last reviewed: 2026-11-16 · after loop-002

## Before the first trade (reported for 2026-11-19)

1. **Check the Nasdaq source after the close and at night** (after 16:00 and after 20:00 New York time): record real answers, add them to the tests, fix what differs. Done with the market open on 2026-11-16; the fix it led to is version 0.3.2.
2. **Record the final IPO price** as soon as it is public (pricing reported for 2026-11-18): the fact `pricing.ipo_price` in `data/facts/`, from an article opened and quoted, or from the final prospectus (424B4) saved by the owner. The page then switches its headline figures to that price.
3. **Watch the first trade**: the MARKET panel must appear by itself. Look at it on a phone, with real figures, and fix what real data breaks.
4. **Measure the memory** of the service after a day of market refreshes.
5. **The final prospectus (424B4).** When it is filed, save it, extend the extractor and replace the range by the final figures everywhere (share counts and cash at the real price).

## Next

6. **EDGAR watcher and "What changed".** Detect a new filing without anyone asking and show what moved. Needs a contact address for sec.gov as a secret on the machine.
7. **AI explanations**, following [ANALYSIS.md](ANALYSIS.md), labeled AI, each citing the figures it uses, with a daily budget in the application. Needs the owner's capped OpenAI key on the machine.
8. **The "what you pay" slider.** If growth slows to a chosen rate, how many years until the price is covered?
9. **A price history** beyond the current day: daily closes since the listing, kept by the service.

## Blocked on something outside this repository

- **Secrets on the machine.** Agent Manager cannot yet assign a secret to an existing Online machine. Workaround: the owner types it into the machine's session with a hidden prompt, into a root-only file on `/data`.
- **Automated deployment.** CI cannot reach the machine: Agent Manager owns access. Needs a design with the owner (a pull-based updater on the machine is the simplest candidate).

## After the listing

10. **"How We Build" page**: loops, features per loop, release history and screenshots, linking to the Loop0 site (owner's directive).
11. **Automated deployment** after tests pass, with deployment logs and rollback outside the machine (owner's directive).
12. **Storage and history** (SQLite): market data over time, and each version of the facts, so that "what changed" has a memory.
13. **Uptime monitoring** from outside the machine.
14. **More of the filing**: who controls the company (share classes, the Long-Term Benefit Trust), customer concentration, risk factors, cost mix by quarter.
15. **Comparables**: the same multiples for a few listed companies, from market data.
16. **Quarterly reports** (10-Q, 10-K) once the company files them: these are tagged in XBRL, which is easier to extract than the S-1.

## Smaller things

- Ask Loop0 for a `LOOP.md` that allows deployment within approved limits; the current file carries the template's "never deploy" line (see DECISIONS D-005).
- The owner to apply the branch protection recommended in CONTRIBUTING.md.
- Count options with the treasury-stock method as an alternative view, and say how much it changes the diluted figure.
- A light theme for print and bright rooms.
- A second look at the long phone page: about nine screens. Which charts does the owner actually read?
- The line of the price is the source's series; give each point its own source card if the owner wants to inspect it.
- Explanatory lines still run over two lines in places (carried from Loop 001).
- Older browsers (before 2024) cannot open source cards: offer a plain list of sources as a fallback.
- Refuse to start when `uv.lock` and the installed packages differ (deploy safety).
