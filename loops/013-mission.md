# Loop 013 — A private portal: a clean login, results on the server only · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-22 · save as `loops/013-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-013` · Repository: existing — inspect before changing · Size: medium

## Objective
Put the whole antipo.watch portal behind a clean login page in the site's style (one username, one password), and keep every result (signals, portfolio decisions, the owner's real orders) on the server only, delivered by the daily run through a token-protected upload; the repository keeps the code, tests and documents.

## Context
- v0.15.0: scanner, simulated portfolio, an HTTP Basic password on /portfolio not yet set by the owner.
- Signal and decision files are committed to the public repository and read from GitHub.
- The daily run lives in the working session on the owner's PC.

## Request (user’s words)
> "le repo… on peut le laisser public… mais le portail web… il pourrait avoir un login, là, un beau login épuré avec mon style… juste un username et un password… Est-ce que les données sont sur le repo automatiquement ou on peut les publier juste sur le serveur… laisser le repo clean avec le code… puis juste les résultats sur le serveur web?" Then: "Go".

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- Nothing behind the login is reachable without it, on antipo.watch and on the Fly.io address; /health shows no result.
- No result file is added to the repository from now on; uploads are checked by the same rules before they are stored.
- Credentials and the upload token are never printed, logged or committed.

## Decisions
### Confirmed by the user — requirements
- **Login:** A login page with a username and a password from the machine's secrets; a signed, HttpOnly, Secure session cookie for 30 days; everything but /login, /static and /health behind it. — Owner's words and go.
- **Results on the server:** Signals, decisions and the ledger live in /data on the machine; the daily run uploads them to a token-protected endpoint that checks them; GitHub is no longer read for results. — Owner: 'laisser le repo clean avec le code… juste les résultats sur le serveur'.
- **Signals no longer public:** The vision's 'signals are public' becomes 'signals are private to the owner'. — Follows from the whole portal behind a login; to be written into VISION.md with the owner's words.

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Brute force:** After ten failed logins in ten minutes, logins are refused for five minutes.

## Carried over — not finished
- From Loop 012: the first scheduled run and the first simulated fills (Mon 2026-11-23); the session cron expires after 7 days; the Second Brain is unavailable; the ledger code (0.15.0) awaits the owner's first real order.

## Scope
- Login page (template, style), POST /login, /logout, the session cookie and the gate on every route.
- Upload endpoint for signal, decision and ledger files, with the same checks; storage in /data; the scanner reads /data.
- CLI upload command; ROUTINE.md and the daily run switched from git push to upload.
- Move the existing result files from the repository to the server.
- start.sh reads SITE_USER, SITE_PASSWORD and UPLOAD_TOKEN; the owner sets the credentials in a hidden prompt.
- Tests: gate, login, cookie, rate limit, upload checks; e2e login on a phone.

## Out of scope
- Several users or roles: one owner account is enough for a private portal.
- Removing old result files from git history: they stay as they were; nothing new is added.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: On a phone, the login page shows the mark, two fields and a button, nothing else; one login keeps the owner signed in for weeks.
- [ ] Experience: A wrong password says so plainly; repeated wrong attempts are slowed down.
- [ ] Visiting antipo.watch or the Fly.io address without a session shows the login page; after login the scanner and the portfolio show.
- [ ] Results added after this loop exist only on the server; the repository has no new result file.
- [ ] An upload that breaks a rule is refused with its problems; a good one shows on the site at once.
- [ ] All checks pass; screenshots of the login page to the owner before release.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/013-mission.md` and the report as `loops/013-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-013.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- A mistake in the gate could lock the owner out or leave a page open: tests on every route, and a check from outside after release.
- Live browser tests need credentials: they will log in with test credentials only locally.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/013-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-013"
}
```
