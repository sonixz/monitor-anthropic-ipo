# Loop 006 — A share card for X: Open Graph, twitter:card and an image without unsourced figures · monitor-anthropic-ipo

> Mission rendered by loop0 · 2026-11-17 · save as `loops/006-mission.md` before building
> Project: `monitor-anthropic-ipo` · Loop: `loop-006` · Repository: existing — inspect before changing · Size: small

## Objective
Before the owner's first post on X, make a link to antipo.watch show a large, clean card: the page declares its title, description, canonical address and a 1200×630 image under the name Anthropic IPO Watch. The image holds no figure, so it never goes stale. Verified as Twitterbot sees it, through Cloudflare, before anything is posted.

## Context
- Live: https://antipo.watch (Loop 005), version 0.6.1; uncommitted and approved: canonical link to https://antipo.watch/, README and SECURITY giving antipo.watch only, version 0.6.2.
- The x-post-research child session checked the page as Twitterbot: no Open Graph or twitter:card tags.
- X caches a card for about a week and no longer offers a card validator: the real check is pasting the link in the composer without posting.
- Cloudflare's Browser Integrity Check is off, so Twitterbot reaches the page.

## Request (user’s words)
> "La page d'accueil d'antipo.watch n'a pas de balises Open Graph ni twitter:card (vérifié avec l'agent Twitterbot). Ajoute og:title, og:description, og:url, og:image (une image 1200×630 sans chiffre non sourcé) et twitter:card=summary_large_image, puis vérifie l'aperçu avant que je publie." — then: "Parfait. [...] tu peux lancer la loop A sans problème. Puis après ça, on structure tout le reste là. Pour le branding."

## The promise — mandatory
The product's promise makes these mandatory. They are in scope even if the loop is small.

- No figure without a source: the image holds no number.
- The notices stay: unofficial, not affiliated with Anthropic, not investment advice, on the page and in the image.
- No Anthropic logo or brand colors: the project's own mark and palette.

## Decisions
### Confirmed by the user — requirements
- **Name:** Anthropic IPO Watch, matching antipo.watch — Owner, 2026-11-17: "Parfait" to the name proposal
- **Order:** Share card now (loop 006), branding pass with a light centered hero next (loop 007) — Owner, 2026-11-17

### Proposed — recommendations, not confirmed; you may revisit them with a stated reason
- **Image:** A static PNG drawn from an SVG in the page's palette, made by the test browser and committed, with no figure — X does not accept SVG; a price in the image would be false after pricing while X keeps the card cached.
- **Page title:** The tab title takes the new name now; the header wordmark changes in loop 007 — og:title and the tab title should agree; the visible header belongs to the branding pass.

## Scope
- One place in render.py for the name, the tagline, the description and the canonical address; the template reads them.
- Tags: og:type, og:site_name, og:title, og:description, og:url, og:image (absolute, versioned), og:image:width/height/alt, twitter:card summary_large_image, twitter:title/description/image/image:alt; canonical link.
- Image: src/ipo_monitor/static/og.png, 1200×630, from og.svg, with the mark, the name, the tagline, the notices and the domain.
- Tests: tags present with absolute URLs; image is a 1200×630 PNG under 5 MB; no digit in the image's source text except the domain-free dimensions.
- Release 0.6.2 (with the approved canonical and docs changes), deploy under D-016, check as Twitterbot through antipo.watch, render the card for the owner.

## Out of scope
- The header wordmark, the hero, the layout and the keys hint (loop 007).
- Posting on X.

## Loop contract
Follow the loop described in `LOOP.md` at the repository root: **Mission** → **Discover** → **Plan** → **Build** → **Validate** → **Document** → **Report**. If `LOOP.md` is missing, say so in your report and follow these steps anyway.

## Acceptance criteria
- [ ] Experience: Pasting https://antipo.watch in the X composer shows a large card with the image, the name and the description, without posting.
- [ ] As Twitterbot, https://antipo.watch/ returns every listed tag with absolute https://antipo.watch URLs.
- [ ] https://antipo.watch/static/og.png answers 200, image/png, 1200×630, under 5 MB.
- [ ] The image holds no figure and shows the notices.
- [ ] Unit and real-browser tests pass locally, in CI and against antipo.watch.
- [ ] The owner sees a rendering of the card before posting.
- [ ] Real use: every form and main flow done in a real browser, as a user would (not only through tests that call the code directly), with screenshots or transcripts in the devlog; what is handed to the user to use (a link, a command, a password) is tried exactly as it is written to them; if that cannot run here, the check is `not_run`, carried over and named in the summary.
- [ ] This mission is saved as `loops/006-mission.md` and the report as `loops/006-report.json`.
- [ ] The project documents listed in `LOOP.md` and their diagrams are updated wherever this loop changed what they describe.
- [ ] If the devlog standard is on: `devlog/loop-006.html` tells this loop and is linked from `devlog/index.html`.

## Risks and unknowns
- X caches a wrong card for days: nothing is posted before the check.
- A long title is cut in the card: keep og:title short.

## Honest reporting
The honest reporting rules in `LOOP.md` apply: a test is `passed` only if you ran it and saw it pass; anything not executed is `not_run`. Only the user accepts a loop.

## Report
Write `loops/006-report.json` (format in `LOOP.md`), starting from these values, then give the user a short summary. Do not add a status or acceptance field.

```json
{
  "schemaVersion": "loop0.report/1",
  "projectId": "monitor-anthropic-ipo",
  "loopId": "loop-006"
}
```
