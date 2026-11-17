"""A count of visits, shown on the page. No cookie, no address, nothing about the visitor.

The page's script tells the service once per browser session that the page was opened
(`POST /seen`). The service adds one to the count of the day, in New York time, and to the
total. That is all it keeps: a number per day, in a small file. A visit is counted only when
the page's script ran, which leaves out most robots; the counts are approximate and say so.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ipo_monitor import log
from ipo_monitor.market import eastern_at

PER_MINUTE = 120  # more than this in one minute is not a crowd of readers: the rest is ignored
SHOWN_DAYS = 14


def today(moment: float) -> str:
    """The day in New York, as 2026-11-19."""
    offset, _ = eastern_at(int(moment))
    return datetime.fromtimestamp(moment, timezone(timedelta(seconds=offset))).date().isoformat()


class Visits:
    """Visits per day. Kept in memory and, when a file is given, in that file."""

    def __init__(self, path: Path | None, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self.clock = clock
        self.days: dict[str, int] = {}
        self.since = today(clock())
        self._minute = (0, 0)  # (minute, visits counted in it)
        self._lock = threading.Lock()
        if path is not None and path.exists():
            self._load(path)

    def _load(self, path: Path) -> None:
        try:
            saved = json.loads(path.read_text("utf-8"))
            days = saved["days"]
            if not isinstance(days, dict) or not all(
                isinstance(k, str) and isinstance(v, int) and v >= 0 for k, v in days.items()
            ):
                raise ValueError("days")
            self.days = dict(days)
            self.since = str(saved.get("since") or min(days, default=self.since))
        except (OSError, ValueError, KeyError, TypeError) as error:
            # A damaged file must not stop the page: counting starts again, and the log says so.
            log.event("visits_reset", level="warning", error=type(error).__name__)

    def add(self) -> bool:
        """Count one visit. False if it was ignored (too many in this minute)."""
        now = self.clock()
        with self._lock:
            minute = int(now // 60)
            counted = self._minute[1] if self._minute[0] == minute else 0
            if counted >= PER_MINUTE:
                return False
            self._minute = (minute, counted + 1)
            day = today(now)
            self.days[day] = self.days.get(day, 0) + 1
            self._save()
        return True

    def _save(self) -> None:
        if self.path is None:
            return
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_text(
                json.dumps({"since": self.since, "days": self.days}, sort_keys=True), "utf-8"
            )
            os.replace(temporary, self.path)
        except OSError as error:
            log.event("visits_not_saved", level="warning", error=type(error).__name__)

    def summary(self) -> dict[str, object]:
        """What the page shows: today, the total, since when, and the last days."""
        with self._lock:
            day = today(self.clock())
            recent = sorted(self.days.items())[-SHOWN_DAYS:]
            return {
                "today": self.days.get(day, 0),
                "total": sum(self.days.values()),
                "since": self.since,
                "days": [{"day": d, "visits": n} for d, n in recent],
                "kept": "a number per day; no cookie, no address",
            }
