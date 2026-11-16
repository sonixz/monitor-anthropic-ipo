# CLAUDE.md

Guidance for coding agents working in this repository.

**Read [LOOP.md](LOOP.md) first:** work happens in loops, and it says how. Then
[VISION.md](VISION.md) (never edit it without the owner) and [STATUS.md](STATUS.md).

## Commands

```sh
uv sync                              # install
uv run python -m ipo_monitor         # run on http://127.0.0.1:8000 (IPO_PORT to change)
uv run ruff format .                 # format
uv run ruff check .                  # lint
uv run mypy                          # types, strict
uv run pytest                        # unit tests
uv run pytest -m e2e                 # real-browser tests (Playwright, Chromium)
uv run python -m ipo_monitor.extract "data/raw/sec/<file>.html"   # rebuild data/facts/s1a2.json
```

## Conventions

- Python 3.12, `src/` layout, package `ipo_monitor`. Line length 100. Strict typing.
- **Templates never contain a number.** Use `n("id")`. Digits typed in a template must be inside
  an element with `data-label` (period names, form names). `tests/test_web.py` enforces it.
- **FILED facts come from `extract.py`**, never from hand edits of `data/facts/s1a2.json`.
  PRESS facts are recorded by hand in `data/facts/press.json`, with the article opened and quoted.
- Every calculation lives in `calc.py` with its formula and inputs, and has a test in
  `tests/test_calc.py` checked against arithmetic done by hand.
- When figures can be cross-checked, add the check to `reconcile.py`.
- No inline style or script: the Content-Security-Policy forbids it. Draw with SVG attributes.
- **Charts** are built in `charts.py` (drawing) and `figures.py` (which facts each chart draws).
  A value goes onto a chart only through `Numbers.mark`, and must also be a number in a table on
  the page. Axis ticks are the only digits without a source (`data-tick`). Charts are 320 units
  wide: look at them at 360 px and at 1280 px before calling them done.
- **Market values** come only from `market.py`, as facts labeled MARKET built from the source's
  answer. Never type a price. A chart of the day draws `Quote.line`, which ends at the last trade
  the source states. Tests replay recorded answers from `tests/fixtures/market/`; the
  file with `TEST` in its name holds invented prices and names itself as test data on the page.
  The final IPO price is recorded as the fact `pricing.ipo_price` in `data/facts/`, from an
  article that was opened and quoted, or from the final prospectus.
- **Filings** come only from `edgar.py`. It reads the SEC's list on a timer and one figure, the
  price on the cover of a final prospectus, under the checks written in `read_price`. Never
  loosen a check to make a document pass. The contact address (`SEC_CONTACT`) goes to sec.gov
  hosts only and is never printed: not in a log, not in an error message, not in a test output.
  Index fixtures with `TEST` in their name are invented; `s1a2-cover.html` is a real excerpt.
- Layout breakpoints are container queries on `.panel`, not media queries: a panel is as narrow
  on a laptop with two panels side by side as on a phone.
- All user-facing text is in English. The owner's words are given in English, reworded.
- Conventional Commits. Update `CHANGELOG.md` with each release.
- Public repository: no secret, contact address or internal access detail anywhere.

## Things that bite

- sec.gov refuses automated downloads without a contact address in the User-Agent. The owner
  saves filings by hand into `data/raw/sec/` (ignored by git). The service's own watch needs
  `SEC_CONTACT`; to try it locally, load `.env` into the environment first (`set -a; . ./.env`).
- On WSL with the repository under `/mnt/c`, keep the virtual environment on the Linux disk:
  `export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/monitor-anthropic-ipo`.
- If Chromium fails to start for lack of `libnss3`, `libnspr4` or `libasound2`, install them
  (`uv run playwright install-deps chromium`) or point `LD_LIBRARY_PATH` at extracted copies.
- The production machine has no `pip`; `deploy/deploy.sh` installs `uv` into `/data/bin`.
- Deployment, exposure and infrastructure are described in [INFRASTRUCTURE.md](INFRASTRUCTURE.md).
  Exposure and infrastructure changes need the owner's approval.
