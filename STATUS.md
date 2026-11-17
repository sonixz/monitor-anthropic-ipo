# STATUS · monitor-anthropic-ipo

> Where the project stands, verified. Last reviewed: 2026-11-16 · after loop-004

## Live

| | |
| --- | --- |
| Site | https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev |
| Version | 0.5.1 (tag `v0.5.1`) |
| Data | Anthropic, PBC, Form S-1/A, Amendment No. 2, filed 2026-11-10 |
| Market data | Awaiting listing. The service asks Nasdaq.com every five minutes (Yahoo Finance if it fails); neither has a price for ANT yet. First trade reported for 2026-11-19 |
| SEC filings | **Watched** since 2026-11-16 23:29 UTC: the service asks EDGAR every ten minutes (latest seen: Form FWP, filed Nov 12, 2026). The owner's contact address is on the machine only |
| IPO price | Not final: the page shows the filed range, $70 to $78. Pricing reported for 2026-11-18 |
| AI | None yet |

## What works (checked on 2026-11-16)

- Nine panels on one page: VALUE, EV BRIDGE, SHARES, UNLOCK, CONTROL, CONTRACTS, GROWTH, LOSSES, TIMELINE; MARKET appears with the first quote and FILINGS with the SEC's list. A strip of key figures at the top and an OVERVIEW with the phase of the IPO, the stage bar, the time of the last checks and the next step (Loop 004).
- 207 numbers on the page, each a button that opens its source. Eleven charts drawn by the server; every mark opens the same source card, and every value a chart draws is also in a table.
- On a phone (360 to 430 px): nothing scrolls sideways, tables included; a panel bar made for thumbs; source cards rise from the bottom; the tables behind the charts are folded until asked for.
- The market panel in its four states (awaiting listing, trading, market closed, source unavailable), tested on recorded answers of the two sources, one of them a real answer with the market open. Live, the page says "awaiting listing" and shows no price.
- The filings watch on test data: the list of filings, the notice of a newer prospectus, the final price read from a cover and refused in eight cases (another form, a preliminary cover, a blank price, a wrong total, and so on). The contact address appears in no log and on no page (tested).
- 159 consistency checks pass at every rendering; the service refuses to start if one fails.
- Keyboard navigation (one key per panel, arrows inside a chart), no JavaScript needed for the core, no serious accessibility issue (axe), on desktop and phone.
- CI on GitHub: format, lint, strict types, 120 unit tests, 13 real-browser tests, secret scan, CodeQL: green on the released commit.
- Deploy and rollback on the machine: eight deployments on 2026-11-16 and 17, each healthy within seconds.
- **Seen by the owner on a phone** (2026-11-16, version 0.4.2): asked to find what the company is worth, what it owes and how fast it grows, to check that nothing scrolls sideways and to open a source card, they reported that everything looked fine and made no remark. No time was recorded.

## Measured

| | |
| --- | --- |
| Page weight | 23 KB compressed; one stylesheet, one script, no external request from the browser |
| Load | About 0.15 s to fetch from the public URL; under 1 s in the browser test |
| Memory | The service uses 57 MB of the machine's 256 MB, the same a few seconds after start and after an hour of market checks |
| Disk | 110 MB used of the 1 GB volume (five releases kept) |
| Phone page length | About nine screens at 390 px, with nine charts (six screens and no chart in 0.1.0) |

## Known limits

- **The service's own client first talked to EDGAR on 2026-11-16 at 23:29 UTC** and read the same list as below. Before that: A real answer for the registrant was read on 2026-11-16 through a web fetch tool and is replayed by the tests: it has the shape the reader expects (14 filings, the latest five are documents for investors filed on 2026-11-12). The client itself, with the contact address, runs for the first time when the owner has put the address on the machine.
- The cover of Anthropic's final prospectus does not exist yet. The reader is built on the cover of Amendment No. 2, where the price is blank. If the final cover is laid out differently, the price is not taken and must be recorded by hand: the intended failure.
- After a final prospectus, the page uses the final price with share counts and cash still taken from Amendment No. 2, until a full extraction reviewed by hand.
- The About box of the GitHub repository (description, live link) is empty: the agent's GitHub access cannot change repository settings.
- **No real quote of ANT has been seen yet**: the stock does not trade. The MARKET panel is proven on recorded answers, including invented prices that name themselves as test data.
- The Nasdaq source was checked before the open and with the market open (2026-11-16), on a long-listed symbol and on a stock listed the Friday before. After the close (16:12 on 2026-11-16) its first figure is a trade of the extended hours and the close comes apart: the page will name both from the next release. Its answer at night has not been seen, nor its answer for a stock that is listed but has not traded yet.
- With the market open, the day's line can show trades made before the open; the range next to it counts regular hours only. The page says so.
- Yahoo Finance refuses the production machine ("too many requests") after a handful of questions; it is only the second source.
- Market values are unofficial and delayed by up to a few minutes: the page says so next to each one.
- The final IPO price is not recorded. When it is, a fact file must be added by hand from an opened article or from the final prospectus; until then the market price is compared with the middle of the filed range.
- The data is one filing, saved and extracted by hand. A new amendment or the final prospectus does not appear by itself.
- "Diluted" and "enterprise value" follow choices explained in [ANALYSIS.md](ANALYSIS.md) and [DECISIONS.md](DECISIONS.md) (D-010, D-011). They are our arithmetic, not filed figures.
- Deployment is manual, from the coding agent's session on the machine; each one makes the site unreachable for a few seconds.
- `LOOP.md` still says "never deploy" (Loop0's template); the owner approved deploying in Loop 001 and, on 2026-11-16, every release whose checks all pass (D-016).
- Browsers from before 2024 show the numbers and charts but cannot open the source cards.

## Not verified yet

- The decisions taken while the owner was away: D-017 to D-022 in [DECISIONS.md](DECISIONS.md). D-016 is confirmed.
- The Nasdaq source at night; the memory of the service after a full day of refreshes.
- **What the source calls the time of the last trade may be the time of its answer.** After the close on 2026-11-16, for a thinly traded stock, that time was the minute of the question while the last point of its series was two minutes older. One observation, not a proof; the answer at night will tell. Until then the page keeps the label "last trade".
- Branch protection on `main`: recommended in CONTRIBUTING.md, to be set by the owner.

Next steps are in [BACKLOG.md](BACKLOG.md).
