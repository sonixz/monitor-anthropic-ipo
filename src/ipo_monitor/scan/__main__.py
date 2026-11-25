"""Command line for the scheduled run and for checks by hand.

    python -m ipo_monitor.scan dossier [--bars yahoo|file:<folder>] [--out <file>]
    python -m ipo_monitor.scan check <signal file> [--bars yahoo|file:<folder>]
    python -m ipo_monitor.scan portfolio [--bars yahoo|file:<folder>]
    python -m ipo_monitor.scan upload <file> [--url https://antipo.watch]

`upload` sends a signal, decision or ledger file to the site, which checks it and keeps it on the
server only. The token comes from ANTIPO_UPLOAD_TOKEN or ~/.config/antipo/upload_token.

`portfolio` replays the simulated envelope from the signal and decision files, says which signals
the rules allow to buy after the latest session and which positions are open, and checks every
decision file: exit 1 if one is refused.

`dossier` reads the closes and writes what the AI reads before it writes a signal file.
`check` applies the same rules the site applies, and exits with 1 if the file would be refused.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from ipo_monitor.scan.bars import BarSource, RecordedDaily, YahooDaily
from ipo_monitor.scan.board import build, dossier
from ipo_monitor.scan.portfolio import Ledger, Rules, eligible
from ipo_monitor.scan.signals import read
from ipo_monitor.scan.universe import Candidates
from ipo_monitor.scan.watch import Folder, ScanWatcher

CANDIDATES = Path("data/scan/candidates.json")
SIGNALS = Path("data/signals")
DECISIONS = Path("data/portfolio/decisions")
RULES = Path("data/portfolio/rules.json")
LEDGER = Path("data/portfolio/ledger.json")


def bar_source(setting: str) -> BarSource:
    if setting == "yahoo":
        return YahooDaily()
    if setting.startswith("file:"):
        return RecordedDaily(Path(setting[5:]))
    raise SystemExit(f"--bars must be yahoo or file:<folder>, got {setting!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ipo_monitor.scan")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("dossier", help="write the dossier the AI reads")
    one.add_argument("--bars", default="yahoo")
    one.add_argument("--candidates", type=Path, default=CANDIDATES)
    one.add_argument("--out", type=Path)
    two = sub.add_parser("check", help="check a signal file as the site would")
    two.add_argument("file", type=Path)
    two.add_argument("--bars", default="yahoo")
    two.add_argument("--candidates", type=Path, default=CANDIDATES)
    three = sub.add_parser("portfolio", help="replay the envelope and check decision files")
    three.add_argument("--bars", default="yahoo")
    three.add_argument("--candidates", type=Path, default=CANDIDATES)
    four = sub.add_parser("upload", help="send a result file to the site")
    four.add_argument("file", type=Path)
    four.add_argument("--url", default="https://antipo.watch")
    args = parser.parse_args(argv)
    if args.command == "upload":
        return upload(args.file, args.url)

    candidates = Candidates.load(args.candidates)
    watcher = ScanWatcher(candidates, bar_source(args.bars), [Folder(SIGNALS)], lambda _: None)
    watcher.read_bars()
    now = datetime.fromtimestamp(time.time(), UTC)
    if args.command == "portfolio":
        return portfolio(candidates, watcher, now)
    if args.command == "dossier":
        board = build(candidates, watcher.series, {}, now, watcher.problems)
        text = json.dumps(dossier(board, now), indent=1, ensure_ascii=False)
        if args.out:
            args.out.write_text(text + "\n", "utf-8")
            print(f"dossier for the session of {board.session}: {args.out}")
        else:
            print(text)
        for problem in watcher.problems:
            print(f"warning: {problem}", file=sys.stderr)
        return 0
    try:
        raw = read(args.file)
    except (OSError, ValueError) as error:
        print(f"refused: cannot read {args.file}: {error}")
        return 1
    for problem in watcher.problems:
        print(f"warning: closes not read for {problem}", file=sys.stderr)
    board = build(candidates, watcher.series, {args.file.name: raw}, now, watcher.problems)
    result = board.checked[0]
    if result.ok:
        count = len(result.file.signals) if result.file else 0
        print(f"ok: {args.file.name}, {count} signals, all rules met")
        return 0
    print(f"refused: {args.file.name}")
    for problem in result.problems:
        print(f"  - {problem}")
    return 1


def portfolio(candidates: Candidates, watcher: ScanWatcher, now: datetime) -> int:
    rules = Rules.load(RULES)
    signals = Folder(SIGNALS).files()
    decisions = Folder(DECISIONS).files()
    fills = None
    if LEDGER.is_file():  # the owner's orders, a copy of the server's (ignored by git)
        ledger = Ledger.model_validate(json.loads(LEDGER.read_text("utf-8")))
        fills = list(ledger.fills) if ledger.real else None
    board = build(
        candidates, watcher.series, signals, now, watcher.problems, decisions, rules, fills
    )
    book = board.book
    if book is None:
        print("no portfolio")
        return 1
    held = {p.symbol for p in book.open_positions}
    latest = board.current
    print(f"envelope: {book.metrics().equity:,.2f} {rules.currency} (rules v{rules.version})")
    print(f"open positions: {', '.join(sorted(held)) or 'none'}")
    if latest is not None:
        allowed = eligible(rules, latest, held)
        print(f"signals of {latest.session}: the rules allow buying {', '.join(allowed) or 'none'}")
        print(f"decision file to write: {DECISIONS}/{latest.session}.json")
    for order in book.pending:
        print(f"  order: buy {order.sizing.shares} {order.symbol} (ref. {order.sizing.close:.2f})")
    for name, problems in board.refused_decisions:
        print(f"refused: {name}")
        for problem in problems:
            print(f"  - {problem}")
    return 1 if board.refused_decisions else 0


def upload(path: Path, base: str) -> int:
    token = os.environ.get("ANTIPO_UPLOAD_TOKEN", "").strip()
    stored = Path.home() / ".config" / "antipo" / "upload_token"
    if not token and stored.is_file():
        token = stored.read_text("utf-8").strip()
    if not token:
        print("no upload token: set ANTIPO_UPLOAD_TOKEN or ~/.config/antipo/upload_token")
        return 1
    if path.name == "ledger.json":
        kind = "ledger"
    elif "decisions" in path.parts:
        kind = "decisions"
    else:
        kind = "signals"
    body = path.read_bytes()
    request = urllib.request.Request(  # noqa: S310 - the site's own address
        f"{base.rstrip('/')}/api/upload/{kind}/{path.name}",
        data=body,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "antipo.watch upload",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:  # noqa: S310
            print(f"stored on the server: {kind}/{path.name} ({json.loads(answer.read())})")
            return 0
    except urllib.error.HTTPError as error:
        detail = error.read()[:4000].decode("utf-8", "replace")
        print(f"refused ({error.code}): {detail}")
        return 1
    except OSError as error:
        print(f"could not reach the site: {type(error).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
