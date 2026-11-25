# ROUTINE.md · the daily signal run

> Since Loop 013 results are uploaded to the server, not committed.

The scheduled Claude run follows this file, every weekday after the Toronto close. It writes one
signal file and the portfolio's decisions for the latest session and uploads them to the site,
which checks and keeps them on the server. Nothing in the repository is changed by the run.

## Steps

1. **Set up.** `uv sync` (on WSL or a cloud box, the default environment is fine). Then
   `uv run python -m ipo_monitor.scan pull`: the owner reports orders on the page (D-057), so the
   server's ledger is the reference. It replaces `data/portfolio/ledger.json`; the decisions
   below follow the owner's real positions.
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
8. **The simulated portfolio.** Run `uv run python -m ipo_monitor.scan portfolio`. It replays the
   envelope (`data/portfolio/rules.json`), lists the open positions and the signals the rules allow
   to buy after this session. Write `data/portfolio/decisions/<session>.json`
   (`schema` `antipo.decisions/1`, same `session`, `written_at`, `written_by`, `model`, optional
   `note`):
   - `entries`: for each allowed signal, `buy`, `wait` or `pass`, with a reason. Buy only what you
     would really buy: a slot is precious (at most five), sectors are capped at two.
   - `positions`: for each open position, `hold` or `exit`, with a reason. Stops, targets, the
     holding period and a signal turned to sell are applied by code; exit early only for a reason.
   - **No digit in a reason.** Sizes, prices and dates come from the code.
   Run `portfolio` again: it must not list the file as refused.
   **On Fridays**, also write `data/portfolio/reviews/<session>.json`: what worked and what did not
   this week, by level, confidence and sector, and any rule change you propose with the figures
   behind it (the owner decides; never change `rules.json` yourself).
9. **Upload, never commit.** Results live on the server only (Loop 013). Send each file with
   `uv run python -m ipo_monitor.scan upload data/signals/<session>.json`, then the decision file
   (and the review): the site checks it with the same rules and answers `stored` or the problems.
   Never upload the ledger unless the owner asked for a correction; the server refuses a copy that
   drops an order it holds (`scan pull` first).
   The token is in `~/.config/antipo/upload_token` (never print it). Keep the local copies: they
   are ignored by git and let `scan portfolio` replay the whole history on this PC.

10. **Discipline.** Ask the site for today's checklist:
    `curl -s -H "Authorization: Bearer $(cat ~/.config/antipo/upload_token)" https://antipo.watch/api/upload/discipline`
    (never print the token). In the summary to the owner, say plainly if the morning list was not
    checked, the streak, and any new gap from the plan. One line, no lecture.

## Never

- Never invent a price, a figure or a news item; never quote an article you did not open.
- Never put a secret, a personal detail or the owner's holdings in a file or a commit.
- Never change code, tests, the rules or other signal and decision files; the past stays as it was written.

## Attribution lines

```
Co-Authored-By: Claude <noreply@anthropic.com>
```
