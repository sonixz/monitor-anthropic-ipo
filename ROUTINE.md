# ROUTINE.md · the daily signal run

The scheduled Claude run follows this file, every weekday after the Toronto close. It writes one
signal file for the latest session and pushes it; the site reads it from GitHub within 15
minutes. Nothing else in the repository is changed by the run.

## Steps

1. **Set up.** `uv sync` (on WSL or a cloud box, the default environment is fine).
2. **Build the dossier.**
   `uv run python -m ipo_monitor.scan dossier --out /tmp/dossier.json`
   It reads a year of daily closes for the candidates from Yahoo Finance, ranks the list (top 50 of
   the S&P/TSX Composite by value traded) and gives each stock's indicators. Note the `session`.
3. **Stop if there is nothing to do.** If `data/signals/<session>.json` already exists, or the
   dossier's session is older than the last weekday (a market holiday), end the run and say so.
4. **Read the figures.** For every stock in the dossier: trend (close against its 50- and 200-day
   averages, distance from the 52-week high and low), momentum (RSI, 20-session change), volume
   against its average, the day's move. The horizon is a few days to a few weeks: swing trading,
   not intraday.
5. **Look up the news** for the stocks that moved most, the ones with unusual volume and the ones
   you lean to a buy or a sell on: results, guidance, deals, analyst moves, sector news. **Open
   every article you cite** and copy the words you quote exactly. No article, no news reason.
6. **Write `data/signals/<session>.json`**, one signal per stock in the dossier (ANT included):
   - `schema` `antipo.signals/1`, `session`, `written_at` (UTC now, ISO 8601), `written_by`
     `Claude, scheduled run`, `model` (your model id), `run` (this session's link if you have it),
     an optional one-line `note` about the market that day.
   - `level`: `strong_buy`, `buy`, `neutral`, `sell` or `strong_sell`. `confidence`: `low`,
     `medium` or `high`. Strong levels and high confidence are rare: they need trend, momentum and
     volume to agree, ideally with news behind them. A sell means exit or avoid.
   - `summary`: one line. `reasons`: one to six.
   - **Never type a digit** in a summary or a reason. Name an indicator as `{key}` (`{rsi14}`,
     `{vs_sma200}`, `{vol_ratio}`, `{from_low52}`...): the site writes its value. A reason without
     an indicator must carry a `source` (`kind` article, filing or release; `url`, `outlet`,
     `title`, `published` date, `quote` in the source's own words).
   - Stops and targets are added by the site (2 × and 3 × ATR); do not write them.
7. **Check.** `uv run python -m ipo_monitor.scan check data/signals/<session>.json`. Fix every
   problem it lists and check again until it says `ok`.
8. **Commit and push only that file** to `main`:
   `git add data/signals/<session>.json`,
   commit message `chore(signals): session <session>` ending with the attribution lines below, then
   `git push origin main`. If the push is refused because main moved, `git pull --rebase` and push
   again. Never force-push, never change another file.

## Never

- Never invent a price, a figure or a news item; never quote an article you did not open.
- Never put a secret, a personal detail or the owner's holdings in a file or a commit.
- Never change code, tests or other signal files; a past signal stays as it was written.

## Attribution lines

```
Co-Authored-By: Claude <noreply@anthropic.com>
```
