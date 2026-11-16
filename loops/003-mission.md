# Loop 003 — Filings found without anyone asking, the final price read from the prospectus, and a repository that explains itself · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-16 · save as `loops/003-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-003` · Repository: existing — inspect before changing · Size: medium

## Objective
Before the first trade (reported for 2026-11-19), take the first step towards a dashboard that keeps itself current. The service notices by itself what Anthropic files with the SEC and says so on the page; when the final prospectus appears, it reads the final IPO price from its cover and the page switches to that price, only if every check passes. And the public GitHub repository explains itself to a visitor: the live link, what the page shows, how each change is checked and released, how the work is done.

## Context
- Live: https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev, version 0.3.2. The page reads one filing, Form S-1/A Amendment No. 2 (filed 2026-11-10), saved by hand by the owner and extracted by a script. The share price is already fetched by the service itself (Nasdaq.com, then Yahoo Finance).
- sec.gov refuses automated clients that do not give a contact address. The address is the owner's: only they can put it on the workstation (.env, ignored by git) and on the machine. Agent Manager cannot assign a secret to an existing machine; the workaround is a root-only file on /data typed by the owner.
- Pricing is reported for 2026-11-18 and the first trade for 2026-11-19. A final prospectus (Form 424B4) is normally filed within two business days after pricing: it may appear after the first trade.
- The repository is public. Its README has the live link and an old screenshot; the About box of the repository is empty; the page does not link to the repository.
- The rule of the product: a number is shown only with its source, and never if a check fails. The service keeps no state: code and data are in git.

## Request (user’s words)
> "ok. Donc on serait rendu a automatiser le dashbaord et le rendre autonome?" — then, to the plan proposed in answer (before the first trade: watch EDGAR and read the final prospectus; after it: deployment by itself, alerts, history): "ok go as tu des bloquant?" — asked whether each version whose checks all pass may go live without them: "Oui, déploie seul" — and while the work started: "oui, aussi, il faudrait bien documenter le repo public github. Mettre le lien, les workflows et etc. tu me suis ?"

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Every number is traced to its source: a price read by the service carries the passage of the prospectus and its link, like any filed figure.
- Never a number that failed a check: when in doubt the page keeps what it had and says what it could not read.
- The notices stay on every page: unofficial, not affiliated with Anthropic, not investment advice; the footer "Built with the Loop0 Method".
- No secret, contact address or internal access detail in the public repository, the devlog or the page.

## Decisions
### Confirmed by the user — requirements
- **Deploying while the owner is away (D-016):** A release whose checks all pass is deployed by the agent without asking; the owner is told afterwards; rollback if the site stops answering — Owner, 2026-11-16: "Oui, déploie seul". Access, exposure and infrastructure changes still need approval each time.
- **Order of the work:** Before the first trade: only the filings watch and the final prospectus. Deployment by GitHub, alerts and history come after it, in the next loop — Owner answered "ok go" to this plan. Changing how releases go live three days before the first trade is an avoidable risk.
- **Repository documentation:** Document the public repository well: the link, the workflows and the rest — Owner's words on 2026-11-16.

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Publishing without the owner:** The service publishes by itself only what passes every check; otherwise it keeps the previous page and says what it could not read — Stated in the plan the owner answered "ok go" to; the exact checks are the agent's.
- **How much of the final prospectus is read by itself:** Only the IPO price from the cover; the other figures wait for an extraction reviewed by hand — The document does not exist yet and its figures change across hundreds of pages; a price on a cover can be checked against the total stated beside it.
- **Press price against filed price:** The filed price replaces a price recorded from the press — The prospectus is the legal document.
- **Where the contact address lives on the machine:** A root-only file on /data, typed by the owner, read by the boot script for known names only — Agent Manager cannot assign a secret to an existing machine.
- **Decisions D-017 to D-022 of Loop 002:** Still waiting for the owner's answer — Charts on the server, axis ticks, layout by panel width, Nasdaq first, never the price of another company, market panel first once the stock trades.

### Assumed — revisit if the environment says otherwise
- **The About box of the repository:** The agent sets description, live link and topics — Read from "Mettre le lien". LOOP.md says not to change repository settings; this one is a description, asked for by the owner, and is easy to undo.

## Carried over — not finished
These items were not completed according to the previous report. They are not done.

- The owner's look at the page on a phone (acceptance criterion of Loop 002) and the 60-second test of Loop 001.
- The owner's answer on D-017 to D-022.
- The Nasdaq source after the close and at night: record real answers, fix what differs. Its answer for a stock listed but not yet traded has never been seen.
- The memory of the service after a full day of refreshes.
- Record the final IPO price when it is public (reported for 2026-11-18).
- Watch the first trade (reported for 2026-11-19) and look at the MARKET panel with real figures.
- Once the stock trades, a phone's first screen shows the market price, not the values at the IPO price (D-022, departure from the Loop 002 mission).
- The price line has one sourced mark, its last point. No history of market data beyond the current day.
- LOOP.md still says "never deploy"; branch protection is not set; the Reuters figure is quoted from a secondary article; no uptime monitoring.
- Still to build after this loop: "what changed", AI explanations, the "what you pay" slider, the "How We Build" page, automated deployment, storage and history.

## Scope
- Filings watch. On a timer, the service asks the SEC's EDGAR for the list of filings of the registrant (the company number already present in the source links of the facts), with the contact address the SEC requires, read from the secret SEC_CONTACT. Without the address the watch is off and everything else works as today. A failure of the watch never breaks the page or the market panel.
- On the page: the recent filings in plain words (form, what it means, date, link to the document on sec.gov), and a clear notice when a filing newer than the one the page reads exists. Visible near the top on a phone.
- The final price. When a Form 424B4 of the registrant appears, the service downloads its main document, reads the initial public offering price from the cover under strict checks (right form, right company, dollars, price times shares equals the total stated), and adds it as the fact pricing.ipo_price labeled FILED, with the passage quoted and the link. The page then uses the final price for its headline figures. If any check fails, no price is taken: the notice says the prospectus is filed and not read yet.
- A price recorded by hand from the press on pricing night stays possible. When the prospectus gives one, the filed price replaces it.
- Secrets on the machine: the boot script reads known names only from a root-only file on /data. Documents give names, never values. The address appears in no log, page, test output or repository file.
- /health and the logs report the state of the watch and the time of the last check.
- The public repository as a front page: README with the live link first, status badges, current screenshots (desktop and phone), what the page shows, how a number is traced, how a change is checked (the GitHub workflows, one by one), how a release goes live, how the work is done in loops; CONTRIBUTING brought up to date; every link checked.
- The link in both directions: the About box of the repository gets a description, the live link and topics; the page's footer links to the repository.
- Each release is deployed on the existing machine once every check passes (D-016, confirmed), then checked in a real browser against the public site.

## Out of scope
- Reading every figure of the final prospectus (share counts, cash and values at the real price): done with the owner's saved file and a review when the document exists.
- "What changed" between two filings.
- Deployment by GitHub itself, alerts when the site or a source fails, and a history of prices and facts: the next loop, after the first trade.
- AI explanations, the "what you pay" slider, the "How We Build" page on the site.
- Any new exposure, machine or access between GitHub and the machine.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

For this loop:
- **Discover:** Read how the market watcher is wired (market.py, web.py) and reuse its shape for the filings watch. Look at the cover of the saved Amendment No. 2 to see where the price row is and how it reads when blank.
- **Build:** Keep the SEC client separate from the market client: the contact address goes to sec.gov hosts only. Never print the value of a secret, not even in an error message about its format.
- **Validate:** Record real EDGAR answers once the address is on the workstation; until then mark every EDGAR check not_run. Use the real page as the owner would, on a phone width first.
- **Document:** README, CONTRIBUTING, INFRASTRUCTURE (secrets, outbound requests, diagram), ARCHITECTURE (the new source), DECISIONS, STATUS, BACKLOG, CHANGELOG, devlog.

## Acceptance criteria
- [ ] Experience: The owner never has to look at sec.gov to learn that Anthropic filed something: the page says it within minutes.
- [ ] Experience: On a phone, the notice of a new filing is on the first screen, and one tap opens the document on sec.gov.
- [ ] Experience: A visitor of the GitHub page understands in one screen what the project is, and reaches the live dashboard in one click.
- [ ] Experience: From the dashboard, one tap in the footer opens the source code.
- [ ] With SEC_CONTACT set, the live page lists Anthropic's latest filings as EDGAR gives them, with dates and links that open; /health reports the state of the watch and the time of the last check.
- [ ] Without SEC_CONTACT the service starts, no request goes to sec.gov, and the page says the filings watch is off.
- [ ] A real answer of EDGAR for the registrant is recorded and replayed by the tests. An answer containing a final prospectus produces the notice of a newer filing.
- [ ] The price is read from the cover of a real final prospectus of a recently listed company (recorded excerpt) and refused in each of these cases: another form, another company, a blank price as in Amendment No. 2, a total that is not price times shares.
- [ ] When a price is read, the page uses it with a FILED source card that quotes the cover, and every consistency check still passes. When it is not, the previous page stays and the notice says so.
- [ ] A test proves the contact address is in no log line and no page.
- [ ] With the new block: no sideways scroll at 360, 390 and 430 px, no serious accessibility issue (axe), no digit without a source or a label.
- [ ] README: live link in the first screen, badges that show the state of CI and CodeQL, current screenshots, each workflow described, the release path and the loop method explained; every link of README and CONTRIBUTING opens.
- [ ] The About box of the repository shows a description and the live link; the footer of the live page links to the repository.
- [ ] CI and CodeQL green on the released commits; the real-browser tests pass against the public site after each deployment; screenshots at 360 and 1280 px looked at one by one.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/003-mission.md` and the report as `loops/003-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-003.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- The contact address is not there: nothing can be asked from sec.gov, not even to record a real answer for the tests. The watch is then delivered switched off and unproven on real data.
- The cover of Anthropic's final prospectus may be laid out differently from what the reader expects: the price is then not taken and must be recorded by hand. This is the intended failure.
- EDGAR may list a filing some minutes after it is accepted, may limit or refuse the machine, or change its answer format.
- A change of the page three days before the first trade: the watch must be isolated so that its failure leaves the market panel untouched.
- The address is personal data: one careless log line would publish it.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/003-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-003"
}
```
