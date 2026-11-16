# ANT IPO Monitor

An independent, AI-assisted dashboard following Anthropic's IPO and, after listing, its stock.
It answers a few plain questions — what is it worth, what are the contracts, is the price
justified — and traces every number to its source.

> **Unofficial.** Not affiliated with Anthropic. **Not investment advice.**

**Live:** https://agmgd-on-ipo-monitor-ba4eccd0.fly.dev (placeholder page for now)

## Status

Loop 0 of the [Loop0 Method](https://agmgd-on-loop0-22c0a8ea.fly.dev/): vision, validation,
standards and the first mission are being prepared. The product itself is not built yet.

| Path | What |
|---|---|
| `deploy/` | How it runs: one Fly.io machine provisioned and exposed through Agent Manager ([deploy/README.md](deploy/README.md)) |
| `deploy/placeholder/` | The temporary page now online: static HTML, a `/health` endpoint, Python standard library only |
| `data/raw/` | Local copies of SEC filings, ignored by git |

## Principles

- **Sourced or silent.** Every figure is labeled *Filed*, *Calculated*, *AI analysis* or *Press-reported*, with its source.
- **AI explains, code computes.** Numbers are extracted and checked by code, never invented by a model.
- **Public by default, safe by default.** No secret or internal access detail ever lands in this repository.

## Run the placeholder locally

```sh
ROOT=deploy/placeholder/www PORT=8000 python3 deploy/placeholder/serve.py
# then open http://localhost:8000 and http://localhost:8000/health
```

Built with the Loop0 Method.
