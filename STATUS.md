# STATUS · monitor-anthropic-ipo

> Where the project stands, verified. Last reviewed: 2026-11-15 · after loop-001

## Live

| | |
| --- | --- |
| Site | https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev |
| Version | 0.1.0 (tag `v0.1.0`) |
| Data | Anthropic, PBC, Form S-1/A, Amendment No. 2, filed 2026-11-10 |
| Market data | None: the stock is not listed yet (first trade reported for 2026-11-19) |
| AI | None yet |

## What works (checked on 2026-11-15)

- Five panels on one page: VALUE, EV BRIDGE, CONTRACTS, GROWTH, LOSSES.
- 125 numbers on the page, each a button that opens its source: 276 facts extracted from the filing with page and quote, 80 calculations with formula and inputs, 4 press figures with their articles.
- 129 consistency checks pass; the service refuses to start if one fails (verified on the machine with a deliberately wrong figure: the deploy script put the previous release back).
- Keyboard navigation, phone layout, source cards, no JavaScript needed for the core: verified in a real browser against the live site, with no serious accessibility issue (axe).
- Deploy and rollback on the machine: both exercised.
- CI on GitHub: format, lint, strict types, 56 unit tests, 4 real-browser tests, secret scan, CodeQL: all green on the released commit.

## Measured

| | |
| --- | --- |
| Page weight | 144 KB of HTML, 16 KB compressed; one stylesheet, one script, no external request |
| Load | About 0.2 s to fetch from the public URL; under 1 s in the browser test |
| Memory | The service uses about 50 MB of the machine's 256 MB |
| Disk | 62 MB used of the 1 GB volume |

## Known limits

- The data is one filing, saved and extracted by hand. A new amendment or the final prospectus does not appear by itself.
- Values are shown for the price range ($70 to $78), not for a final price.
- "Diluted" and "enterprise value" follow choices explained in [ANALYSIS.md](ANALYSIS.md) and [DECISIONS.md](DECISIONS.md) (D-010, D-011). They are our arithmetic, not filed figures.
- Two press figures (the Reuters valuation and its basis) are quoted from a secondary article that relays them.
- Deployment is manual, from the coding agent's session on the machine.
- `LOOP.md` still says "never deploy" (Loop0's Loop 001 template); the owner approved deploying in Loop 001.
- Browsers from before 2024 show the numbers but cannot open the source cards.

## Not verified yet

- The owner's 60-second test on the live page (acceptance criterion of Loop 001).
- Branch protection on `main`: recommended in CONTRIBUTING.md, to be set by the owner.

Next steps are in [BACKLOG.md](BACKLOG.md).
