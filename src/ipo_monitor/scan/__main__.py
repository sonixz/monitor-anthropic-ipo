"""Command line for the scheduled run and for checks by hand.

    python -m ipo_monitor.scan dossier [--bars yahoo|file:<folder>] [--out <file>]
    python -m ipo_monitor.scan check <signal file> [--bars yahoo|file:<folder>]

`dossier` reads the closes and writes what the AI reads before it writes a signal file.
`check` applies the same rules the site applies, and exits with 1 if the file would be refused.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from ipo_monitor.scan.bars import BarSource, RecordedDaily, YahooDaily
from ipo_monitor.scan.board import build, dossier
from ipo_monitor.scan.signals import read
from ipo_monitor.scan.universe import Candidates
from ipo_monitor.scan.watch import Folder, ScanWatcher

CANDIDATES = Path("data/scan/candidates.json")
SIGNALS = Path("data/signals")


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
    args = parser.parse_args(argv)

    candidates = Candidates.load(args.candidates)
    watcher = ScanWatcher(candidates, bar_source(args.bars), [Folder(SIGNALS)], lambda _: None)
    watcher.read_bars()
    now = datetime.fromtimestamp(time.time(), UTC)
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


if __name__ == "__main__":
    raise SystemExit(main())
