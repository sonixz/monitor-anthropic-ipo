"""Stops and targets: where a signal is proven wrong, and where it has done its work.

Computed by code from the entry close and the average true range (ATR over 14 sessions), with
the multiples below, never typed by the AI. For a buy, the stop is under the entry and the
target above; for a sell (exit or avoid, not advice to sell short), the mirror: the level that
cancels the sell is above, the target below. Neutral has none. A signal is followed for
`HOLD` sessions at most.
"""

from __future__ import annotations

from ipo_monitor.scan.indicators import Indicator

STOP_ATR = 2.0
TARGET_ATR = 3.0
HOLD = 20  # sessions


def levels(level: str, found: dict[str, Indicator]) -> dict[str, Indicator]:
    """Entry, stop, target, risk and reward per share, as indicators with their formulas."""
    close, range_ = found.get("close"), found.get("atr14")
    if close is None or range_ is None or level == "neutral":
        return {}
    up = level in ("buy", "strong_buy")
    entry, a = close.value, range_.value
    stop = entry - STOP_ATR * a if up else entry + STOP_ATR * a
    target = entry + TARGET_ATR * a if up else entry - TARGET_ATR * a
    unit = close.unit
    day = close.last

    def one(key: str, title: str, value: float, formula: str) -> Indicator:
        return Indicator(key, title, value, unit, formula, range_.sessions, range_.first, day)

    sign_stop, sign_target = ("−", "+") if up else ("+", "−")
    atr_text = f"ATR {range_.shown}"
    return {
        "entry": one(
            "entry",
            "Entry: the close of the signal's session",
            entry,
            "the close of the session the signal was written for",
        ),
        "stop": one(
            "stop",
            "Stop" if up else "Cancels the sell above",
            stop,
            f"entry {close.shown} {sign_stop} {STOP_ATR:g} × {atr_text}",
        ),
        "target": one(
            "target",
            "Target",
            target,
            f"entry {close.shown} {sign_target} {TARGET_ATR:g} × {atr_text}",
        ),
        "risk": one(
            "risk",
            "Risk per share",
            STOP_ATR * a,
            f"distance from entry to stop = {STOP_ATR:g} × {atr_text}",
        ),
        "reward": one(
            "reward",
            "Reward per share",
            TARGET_ATR * a,
            f"distance from entry to target = {TARGET_ATR:g} × {atr_text}",
        ),
    }
