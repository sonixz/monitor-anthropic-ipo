"""Keeping the scanner current: closes after each session, signal files as they are published.

Bars: read for every stock at startup, then again once a session has closed (after 16:20,
Toronto time, on a weekday) until the new closes are there; after one try with nothing new
(a market holiday), not again before the next day.

Signal files: those shipped with the release (`data/signals/`), and those the scheduled run
committed to the public repository since, read from GitHub every 15 minutes. Each file is
checked by `signals.check` when the board is built; a refused file is never shown.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from ipo_monitor import log
from ipo_monitor.market import USER_AGENT, SourceError
from ipo_monitor.scan.bars import BarSource, Series
from ipo_monitor.scan.board import TORONTO, Board, build
from ipo_monitor.scan.portfolio import Rules
from ipo_monitor.scan.universe import Candidates

REPOSITORY = "sonixz/monitor-anthropic-ipo"
SIGNALS_PATH = "data/signals"
DECISIONS_PATH = "data/portfolio/decisions"
EVERY = 900  # seconds between two looks
CLOSED_AFTER = (16, 20)  # Toronto time: the session's closes are expected after this


class SignalSource(Protocol):
    name: str

    def files(self) -> dict[str, object]: ...


@dataclass
class Folder:
    """Signal files in a folder."""

    folder: Path
    name: str = "release"

    def files(self) -> dict[str, object]:
        found: dict[str, object] = {}
        if not self.folder.is_dir():
            return found
        for path in sorted(self.folder.glob("*.json")):
            try:
                found[path.name] = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError) as error:
                found[path.name] = {"unreadable": type(error).__name__}
        return found


def _get(url: str, accept: str) -> bytes:
    request = urllib.request.Request(  # noqa: S310 - fixed https addresses
        url, headers={"User-Agent": USER_AGENT, "Accept": accept}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return bytes(response.read(1_000_000))
    except urllib.error.HTTPError as error:
        raise SourceError(f"HTTP {error.code}") from error
    except OSError as error:
        raise SourceError(type(error).__name__) from error


@dataclass
class GitHub:
    """Signal files in the public repository, read without any token."""

    repository: str = REPOSITORY
    path: str = SIGNALS_PATH
    name: str = "GitHub"
    get: Callable[[str, str], bytes] = field(default=_get, repr=False)
    cache: dict[str, tuple[str, object]] = field(default_factory=dict)  # name → (sha, content)

    def files(self) -> dict[str, object]:
        listing = json.loads(
            self.get(
                f"https://api.github.com/repos/{self.repository}/contents/{self.path}",
                "application/vnd.github+json",
            )
        )
        if not isinstance(listing, list):
            raise SourceError("unexpected answer")
        found: dict[str, object] = {}
        for entry in listing:
            if not isinstance(entry, dict):
                continue
            name, sha = str(entry.get("name", "")), str(entry.get("sha", ""))
            if not name.endswith(".json") or entry.get("type") != "file":
                continue
            if name in self.cache and self.cache[name][0] == sha:
                found[name] = self.cache[name][1]
                continue
            raw = self.get(
                f"https://raw.githubusercontent.com/{self.repository}/main/{self.path}/{name}",
                "application/json",
            )
            try:
                content: object = json.loads(raw)
            except ValueError:
                content = {"unreadable": "not JSON"}
            self.cache[name] = (sha, content)
            found[name] = content
        return found


def expected_session(now: datetime) -> str:
    """The latest session whose closes should be out by now (holidays are not known)."""
    local = now.astimezone(TORONTO)
    day = local.date()
    if (local.hour, local.minute) < CLOSED_AFTER:
        day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


@dataclass
class ScanWatcher:
    candidates: Candidates
    bars: BarSource
    signals: list[SignalSource]
    on_change: Callable[[Board], None]
    clock: Callable[[], float] = time.time
    series: dict[str, Series] = field(default_factory=dict)
    files: dict[str, object] = field(default_factory=dict)
    problems: tuple[str, ...] = ()
    tried_for: str | None = None  # the session last fetched for
    signals_read: dict[str, str] = field(default_factory=dict)  # source → time or problem
    board: Board | None = None
    decision_sources: list[SignalSource] = field(default_factory=list)
    decisions: dict[str, object] = field(default_factory=dict)
    rules: Rules | None = None

    def now(self) -> datetime:
        return datetime.fromtimestamp(self.clock(), UTC)

    def read_bars(self) -> bool:
        """Read every stock's bars. Returns whether anything changed."""
        now = int(self.clock())
        problems = []
        changed = False
        everyone = self.candidates.candidates + self.candidates.pinned + self.candidates.benchmarks
        for stock in everyone:
            try:
                series = self.bars.daily(stock.symbol, stock.source_symbol, now)
            except (SourceError, KeyError, TypeError, ValueError, IndexError) as error:
                problems.append(f"{stock.symbol}: {error}")
                continue
            old = self.series.get(stock.symbol)
            if old is None or old.bars != series.bars:
                changed = True
            self.series[stock.symbol] = series
        if problems:
            log.event("scan_bars_problems", level="warning", count=len(problems))
        changed = changed or tuple(problems) != self.problems
        self.problems = tuple(problems)
        return changed

    def read_signals(self) -> bool:
        files: dict[str, object] = {}
        for source in self.signals:
            try:
                files.update(source.files())
                self.signals_read[source.name] = self.now().isoformat(timespec="seconds")
            except (SourceError, ValueError) as error:
                self.signals_read[source.name] = f"failed: {error}"
                log.event("scan_signals_failed", level="warning", source=source.name)
                # keep what that source gave last time
                files.update({k: v for k, v in self.files.items() if k not in files})
        changed = files != self.files
        self.files = files
        decisions: dict[str, object] = {}
        for source in self.decision_sources:
            try:
                decisions.update(source.files())
            except (SourceError, ValueError):
                log.event("scan_decisions_failed", level="warning", source=source.name)
                decisions.update({k: v for k, v in self.decisions.items() if k not in decisions})
        changed = changed or decisions != self.decisions
        self.decisions = decisions
        return changed

    def rebuild(self) -> Board:
        self.board = build(
            self.candidates,
            self.series,
            self.files,
            self.now(),
            self.problems,
            self.decisions,
            self.rules,
        )
        for refused in self.board.refused:
            log.event(
                "scan_signal_file_refused",
                level="warning",
                file=refused.name,
                problems=len(refused.problems),
            )
        return self.board

    def start(self) -> Board:
        self.read_bars()
        self.tried_for = expected_session(self.now())
        self.read_signals()
        return self.rebuild()

    def due(self) -> bool:
        """Whether a new session's closes should be fetched now."""
        want = expected_session(self.now())
        have = max((s.last.date for s in self.series.values() if s.last), default="")
        return have < want and self.tried_for != want

    def step(self) -> bool:
        changed = False
        if self.due():
            self.tried_for = expected_session(self.now())
            changed = self.read_bars()
        changed = self.read_signals() or changed
        if changed:
            board = self.rebuild()
            self.on_change(board)
        return changed

    async def run(self) -> None:
        while True:
            await asyncio.sleep(EVERY)
            try:
                await asyncio.to_thread(self.step)
            except Exception as error:  # keep watching whatever happens
                log.event("scan_error", level="error", error=type(error).__name__)


def health(watcher: ScanWatcher | None) -> dict[str, Any]:
    if watcher is None or watcher.board is None:
        return {"state": "off"}
    board = watcher.board
    return {
        "state": "ok" if not board.problems else "partial",
        "session": board.session,
        "list_ranked_on": board.universe.date if board.universe else None,
        "stocks": len(board.stocks),
        "bars_problems": len(board.problems),
        "signals_session": board.current.session if board.current else None,
        "signals_written_by": board.current.written_by if board.current else None,
        "signals_stale": board.stale,
        "files_refused": [c.name for c in board.refused],
        "signals_read": watcher.signals_read,
        "next_run": board.next_run.isoformat(timespec="minutes"),
    }
