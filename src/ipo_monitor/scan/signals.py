"""Signal files: what the AI wrote for one session, and the rules a file must meet to be shown.

A signal file (`data/signals/YYYY-MM-DD.json`) is written by Claude after the close. It holds,
for each stock, a level, a confidence, a one-line summary and reasons. The AI never types a
number: a reason names an indicator by putting its key in braces, `{rsi14}`, and the page
writes the value computed by `indicators.py`. A reason that names no indicator must cite an
article or a filing, with its link and the words quoted from it. A file that breaks a rule is
refused whole, and the page keeps the last good one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ipo_monitor.scan.indicators import Indicator

SCHEMA = "antipo.signals/1"
Level = Literal["strong_buy", "buy", "neutral", "sell", "strong_sell"]
Confidence = Literal["low", "medium", "high"]
LEVELS: dict[str, str] = {
    "strong_buy": "strong buy",
    "buy": "buy",
    "neutral": "neutral",
    "sell": "sell",
    "strong_sell": "strong sell",
}
STRENGTH = {"strong_buy": 2, "buy": 1, "neutral": 0, "sell": -1, "strong_sell": -2}
PLACEHOLDER = re.compile(r"\{([a-z0-9_]+)\}")


class Source(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["article", "filing", "release"]
    url: str = Field(pattern=r"^https://[^\s]+$", max_length=500)
    outlet: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    published: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    quote: str = Field(min_length=1, max_length=500)  # the source's own words, digits allowed


class Reason(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1, max_length=320)
    source: Source | None = None

    @property
    def keys(self) -> list[str]:
        return PLACEHOLDER.findall(self.text)


class Signal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1, max_length=12)
    level: Level
    confidence: Confidence
    summary: str = Field(min_length=1, max_length=180)
    reasons: list[Reason] = Field(min_length=1, max_length=6)

    @property
    def label(self) -> str:
        return LEVELS[self.level]

    @property
    def strength(self) -> int:
        return STRENGTH[self.level]


class SignalFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_: Literal["antipo.signals/1"] = Field(alias="schema")
    session: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    written_at: str
    written_by: Literal["Claude, scheduled run", "Claude, session"]
    model: str = Field(min_length=1, max_length=60)
    run: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=400)
    signals: list[Signal] = Field(min_length=1, max_length=120)

    @property
    def written(self) -> datetime:
        return datetime.fromisoformat(self.written_at.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Checked:
    """A signal file that met every rule, or the reasons it was refused."""

    name: str
    file: SignalFile | None
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.file is not None and not self.problems


def _digits(text: str) -> bool:
    return bool(re.search(r"\d", PLACEHOLDER.sub("", text)))


def check(
    raw: object,
    name: str,
    *,
    allowed: set[str],
    indicators: dict[str, dict[str, Indicator]],
) -> Checked:
    """Check one signal file against the stocks allowed that session and their indicators.

    `indicators` gives, for each symbol, the indicators as of the file's session.
    """
    try:
        file = SignalFile.model_validate(raw)
    except ValidationError as error:
        found = tuple(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()[:20]
        )
        return Checked(name, None, found)
    problems: list[str] = []
    try:
        Date.fromisoformat(file.session)
        file.written  # noqa: B018 - parses the time
    except ValueError:
        problems.append("session or written_at is not a date")
    if name.removesuffix(".json") != file.session:
        problems.append(f"the file name must be the session date, {file.session}.json")
    seen: set[str] = set()
    for index, signal in enumerate(file.signals):
        where = f"signals.{index} ({signal.symbol})"
        if signal.symbol in seen:
            problems.append(f"{where}: a second signal for the same stock")
        seen.add(signal.symbol)
        if signal.symbol not in allowed:
            problems.append(f"{where}: not in the list scanned for {file.session}")
            continue
        known = indicators.get(signal.symbol, {})
        if not known:
            problems.append(f"{where}: no close for {file.session}")
            continue
        texts = [("summary", signal.summary)] + [
            (f"reasons.{i}", r.text) for i, r in enumerate(signal.reasons)
        ]
        for field, text in texts:
            if _digits(text):
                problems.append(f"{where}.{field}: a number typed by hand; name an indicator")
            for key in PLACEHOLDER.findall(text):
                if key not in known:
                    problems.append(f"{where}.{field}: unknown indicator {{{key}}}")
        for i, reason in enumerate(signal.reasons):
            if not reason.keys and reason.source is None:
                problems.append(f"{where}.reasons.{i}: cites no indicator and no source")
            if reason.source is not None:
                try:
                    published = Date.fromisoformat(reason.source.published)
                except ValueError:
                    problems.append(f"{where}.reasons.{i}: the source's date is not a date")
                    continue
                if published > Date.fromisoformat(file.session) and published > file.written.date():
                    problems.append(f"{where}.reasons.{i}: the source is dated after the run")
    return Checked(name, file if not problems else None, tuple(problems))


def read(path: Path) -> object:
    return json.loads(path.read_text("utf-8"))


def fill(text: str, known: dict[str, Indicator]) -> list[tuple[str, Indicator | None]]:
    """Split a reason into text and indicators, for the page to draw each value with its card."""
    parts: list[tuple[str, Indicator | None]] = []
    position = 0
    for match in PLACEHOLDER.finditer(text):
        if match.start() > position:
            parts.append((text[position : match.start()], None))
        parts.append(("", known[match.group(1)]))
        position = match.end()
    if position < len(text):
        parts.append((text[position:], None))
    return parts
