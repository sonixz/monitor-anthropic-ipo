# STATUS · monitor-anthropic-ipo

> Where the project stands, verified. Last reviewed: 2026-11-16 · after loop-002

## Live

| | |
| --- | --- |
| Site | https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev |
| Version | 0.3.1 (tag `v0.3.1`) |
| Data | Anthropic, PBC, Form S-1/A, Amendment No. 2, filed 2026-11-10 |
| Market data | Awaiting listing. The service asks Nasdaq.com every five minutes (Yahoo Finance if it fails); neither has a price for ANT yet. First trade reported for 2026-11-19 |
| IPO price | Not final: the page shows the filed range, $70 to $78. Pricing reported for 2026-11-18 |
| AI | None yet |

## What works (checked on 2026-11-16)

- Five panels on one page: VALUE, EV BRIDGE, CONTRACTS, GROWTH, LOSSES, and a sixth, MARKET, that appears with the first quote.
- 141 numbers on the page, each a button that opens its source. Nine charts drawn by the server; every mark opens the same source card, and every value a chart draws is also in a table.
- On a phone (360 to 430 px): nothing scrolls sideways, tables included; a panel bar made for thumbs; source cards rise from the bottom; the tables behind the charts are folded until asked for.
- The market panel in its four states (awaiting listing, trading, market closed, source unavailable), tested on recorded answers of the two sources. Live, the page says "awaiting listing" and shows no price.
- 129 consistency checks pass at every rendering; the service refuses to start if one fails.
- Keyboard navigation (one key per panel, arrows inside a chart), no JavaScript needed for the core, no serious accessibility issue (axe), on desktop and phone.
- CI on GitHub: format, lint, strict types, 92 unit tests, 12 real-browser tests, secret scan, CodeQL: green on the released commit.
- Deploy and rollback on the machine: three deployments on 2026-11-16, each healthy within seconds.

## Measured

| | |
| --- | --- |
| Page weight | 23 KB compressed; one stylesheet, one script, no external request from the browser |
| Load | About 0.15 s to fetch from the public URL; under 1 s in the browser test |
| Memory | The service uses 56 MB of the machine's 256 MB a few seconds after start, market timer included |
| Disk | 110 MB used of the 1 GB volume (five releases kept) |
| Phone page length | About nine screens at 390 px, with nine charts (six screens and no chart in 0.1.0) |

## Known limits

- **No real quote of ANT has been seen yet**: the stock does not trade. The MARKET panel is proven on recorded answers, including invented prices that name themselves as test data.
- The Nasdaq source was recorded before the market opened. Its answer during regular hours is read by the same code but has not been checked against a real one.
- Yahoo Finance refuses the production machine ("too many requests") after a handful of questions; it is only the second source.
- Market values are unofficial and delayed by up to a few minutes: the page says so next to each one.
- The final IPO price is not recorded. When it is, a fact file must be added by hand from an opened article or from the final prospectus; until then the market price is compared with the middle of the filed range.
- The data is one filing, saved and extracted by hand. A new amendment or the final prospectus does not appear by itself.
- "Diluted" and "enterprise value" follow choices explained in [ANALYSIS.md](ANALYSIS.md) and [DECISIONS.md](DECISIONS.md) (D-010, D-011). They are our arithmetic, not filed figures.
- Deployment is manual, from the coding agent's session on the machine; each one makes the site unreachable for a few seconds.
- `LOOP.md` still says "never deploy" (Loop0's template); the owner approved deploying in Loop 001, and Loop 002 assumed the same (D-016).
- Browsers from before 2024 show the numbers and charts but cannot open the source cards.

## Not verified yet

- The owner's look at the page on a phone (acceptance criterion of Loop 002) and the 60-second test (Loop 001).
- The decisions taken while the owner was away: D-016 to D-022 in [DECISIONS.md](DECISIONS.md).
- The Nasdaq source while the market is open; the memory of the service after a day of refreshes.
- Branch protection on `main`: recommended in CONTRIBUTING.md, to be set by the owner.

Next steps are in [BACKLOG.md](BACKLOG.md).
