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
SHOWN_DAYS = 60
SHOWN_HOURS = 48  # the line of the first days, when there are too few days for a line


def _local(moment: float) -> datetime:
    offset, _ = eastern_at(int(moment))
    return datetime.fromtimestamp(moment, timezone(timedelta(seconds=offset)))


def today(moment: float) -> str:
    """The day in New York, as 2026-11-19."""
    return _local(moment).date().isoformat()


def hour(moment: float) -> str:
    """The hour in New York, as 2026-11-19T14."""
    return _local(moment).strftime("%Y-%m-%dT%H")


class Visits:
    """Visits per day. Kept in memory and, when a file is given, in that file."""

    def __init__(self, path: Path | None, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self.clock = clock
        self.days: dict[str, int] = {}
        self.hours: dict[str, int] = {}  # the last SHOWN_HOURS hours only
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
            hours = saved.get("hours", {})
            if isinstance(hours, dict) and all(
                isinstance(k, str) and isinstance(v, int) and v >= 0 for k, v in hours.items()
            ):
                self.hours = dict(hours)
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
            when = hour(now)
            self.hours[when] = self.hours.get(when, 0) + 1
            for old in sorted(self.hours)[:-SHOWN_HOURS]:
                del self.hours[old]
            self._save()
        return True

    def _save(self) -> None:
        if self.path is None:
            return
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_text(
                json.dumps(
                    {"since": self.since, "days": self.days, "hours": self.hours}, sort_keys=True
                ),
                "utf-8",
            )
            os.replace(temporary, self.path)
        except OSError as error:
            log.event("visits_not_saved", level="warning", error=type(error).__name__)

    def summary(self) -> dict[str, object]:
        """What the page shows: today, the total, since when, and the last days."""
        with self._lock:
            now = self.clock()
            day = today(now)
            # Every day and every hour on the way, those without a visit at zero: a line in time.
            first = max(
                self.since, (_local(now) - timedelta(days=SHOWN_DAYS - 1)).date().isoformat()
            )
            days = []
            cursor = datetime.fromisoformat(first).date()
            while cursor.isoformat() <= day:
                days.append(
                    {"day": cursor.isoformat(), "visits": self.days.get(cursor.isoformat(), 0)}
                )
                cursor += timedelta(days=1)
            hours = [
                {"hour": key, "visits": self.hours.get(key, 0)}
                for key in (hour(now - 3600 * back) for back in range(SHOWN_HOURS - 1, -1, -1))
                if key[:10] >= self.since
            ]
            return {
                "today": self.days.get(day, 0),
                "total": sum(self.days.values()),
                "since": self.since,
                "days": days,
                "hours": hours,
                "kept": "a number per day and per hour; no cookie, no address",
            }
