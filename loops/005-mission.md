# Loop 005 — antipo.watch: the dashboard on its own domain, through Cloudflare, with the expertise recorded for a Loop0 expert · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-17 · save as `loops/005-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-005` · Repository: existing — inspect before changing · Size: small

## Objective
Serve the dashboard at https://antipo.watch (and redirect www) with a valid certificate, before pricing (reported 2026-11-18), without touching the Fly machine. The domain is a zone on Cloudflare (Free plan); Cloudflare terminates TLS and a Worker relays each request to the existing Fly app. Every step, decision, command shape and pitfall is recorded in the Second Brain so that Loop0 can turn this first DNS setup into an expert.

## Context
- Live: https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev, version 0.6.1 (release 74659fb). The app does not check the Host header.
- Zone antipo.watch: active on Cloudflare, Free plan, name servers kami and rory.ns.cloudflare.com, propagated (checked over DNS-over-HTTPS at 1.1.1.1 and 8.8.8.8 on 2026-11-16). No DNS records yet. SSL mode Full, Always Use HTTPS off, minimum TLS 1.0.
- Token: an Account API token scoped to the zone antipo.watch (Zone Read, DNS/Zone Settings/SSL and Certificates/Workers Routes Write), injected by Agent Manager as ANTIPO_WATCH_SETUP. Workers Scripts Write on the account is requested from the owner.
- Test: TLS to the Fly IP with SNI antipo.watch is refused (no Fly certificate for that name); SNI fly.dev with Host antipo.watch answers 200. No flyctl access here, and Agent Manager exposes only *.fly.dev.

## Request (user’s words)
> "Tu vas m'aider à dropper une clé Cloudflare pour le domaine que j'ai acheté [...] j'ai acheté antipo.watch. [...] j'aimerais ça qu'on configure les DNS là-dessus. Mais ce qui est bien important, c'est qu'il va falloir que tu consignes toute ton expertise dans Second Brain pour que ça soit converti, ça, par Loop 0 en expert. [...] on configure pour la première fois un DNS. Un nom de domaine, un certificat, tout ça. Tout ce qu'on a besoin techniquement, c'est la clé d'API de Cloudflare. [...] On se lance."

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- The notices stay: unofficial, not affiliated with Anthropic, not investment advice.
- Nothing secret in the public repository, the Brain or a log: no token, no account name (it holds the owner's e-mail), no contact address.
- The page behaves the same at both addresses: every number opens its source, the visits count once, the CSP holds.

## Decisions
### Confirmed by the user — requirements
- **Domain:** Use antipo.watch, bought by the owner, reversing the earlier refusal of a domain — Owner, 2026-11-16: "j'ai acheté antipo.watch [...] On se lance"
- **Expertise:** Record every step, decision and pitfall in the Second Brain for a Loop0 expert — Owner, 2026-11-16
- **Token kind:** Account API token, scoped to the one zone, held by Agent Manager — Owner created it so, 2026-11-16

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Routing:** Proxied DNS records on Cloudflare and a Worker that relays to the fly.dev address — Fly refuses TLS for a name it holds no certificate for, and adding one needs flyctl, which this session does not have. A Worker calls out with the fly.dev SNI. Free up to 100,000 requests a day.
- **Canonical address:** antipo.watch is the main address; www redirects to it; the fly.dev address keeps working — A short address for posts; fly.dev stays as a fallback and for the machine's health checks.
- **TLS settings:** Always Use HTTPS on, minimum TLS 1.2, SSL Full (strict) — The origin has a valid Fly certificate for fly.dev, so strict holds.

## Scope
- Ask the owner for Workers Scripts Write on the token.
- Worker that relays to https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev, keeping the method, path, query and body, and redirecting www to the apex; source kept in deploy/cloudflare/ in the repository (no secret in it).
- DNS: proxied records for antipo.watch and www; routes of the Worker on both.
- Zone settings: Always Use HTTPS, minimum TLS 1.2, SSL Full (strict).
- Check the certificate, the redirects, /health, /stats and the page through the new address; run the e2e tests against https://antipo.watch.
- Docs: INFRASTRUCTURE.md (domain, Cloudflare, Worker, token handling, rollback), README, STATUS, SECURITY, DECISIONS, CHANGELOG; devlog loop-005.
- Second Brain: the procedure, the decisions and the pitfalls, written for a future DNS expert.

## Out of scope
- Fly certificates and changes to the Fly machine.
- E-mail on the domain (MX records).
- Cloudflare caching rules beyond the defaults, analytics, WAF.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: Typing antipo.watch in a phone browser opens the dashboard over HTTPS, with no certificate warning.
- [ ] Experience: www.antipo.watch and http:// both land on https://antipo.watch.
- [ ] https://antipo.watch serves the same page as the fly.dev address, with a valid certificate.
- [ ] www and http redirect to https://antipo.watch with a permanent redirect.
- [ ] The e2e tests pass against https://antipo.watch.
- [ ] No token, account name or contact address in the repository, the Brain, or a log.
- [ ] The Second Brain holds the procedure, the decisions and the pitfalls of this setup.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/005-mission.md` and the report as `loops/005-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-005.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- Cloudflare may cache the page: the app already sends cache headers; check that a new release shows at once.
- The visits count or the market and filings data could break if the Worker drops the method or body of POST /seen.
- Rollback: delete the DNS records and the Worker route; the fly.dev address is untouched.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/005-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-005"
}
```
