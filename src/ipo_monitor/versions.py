"""Versions: what changed from one filing to the next.

The page reads one filing, the latest the owner saved (`data/facts/*.json`). Earlier filings stay
in `data/facts/history/`, extracted by the same code. Nothing is overwritten in silence: every
fact whose value or wording differs between two filings in a row is listed, the earlier value
opening the earlier filing's passage and the later one the later filing's.

Each side is shown as that filing words it, so a figure whose meaning changed (Class A shares
only, then Class A and Class N) never reads as a bare change of value.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass, replace

from ipo_monitor.facts import Document, Fact, FactFile, Facts

# Facts about the document itself (its date): the line at the top says it already.
LEFT_OUT = ("doc.",)


@dataclass(frozen=True)
class Change:
    """One fact that differs between two filings."""

    id: str
    title: str
    before: str | None  # the earlier value, as a ref on the page; None when the fact is new
    after: str | None  # the later value; None when the later filing no longer gives it
    style: str = ""
    when: str | None = None  # for a lock-up step, the ref of when it comes


@dataclass(frozen=True)
class Step:
    """From one filing to the next."""

    older: Document
    newer: Document
    changes: tuple[Change, ...]

    @property
    def main(self) -> tuple[Change, ...]:
        """The changes shown at once."""
        return tuple(c for c in self.changes if not c.id.startswith("unlock."))

    @property
    def lockup(self) -> tuple[Change, ...]:
        """The lock-up steps that changed: many rows, folded on the page."""
        return tuple(c for c in self.changes if c.id.startswith("unlock."))


def history_ref(document_id: str, fact_id: str) -> str:
    """The id an earlier filing's fact takes on the page: `s1a2:unlock.02`."""
    return f"{document_id}:{fact_id}"


def _style(fact: Fact) -> str:
    if fact.unit == "shares" and isinstance(fact.value, float | int) and abs(fact.value) < 1e9:
        return "m"
    return ""


def _differs(a: Fact, b: Fact) -> bool:
    return a.value != b.value or a.as_filed != b.as_filed


def compare(older: dict[str, Fact], newer: dict[str, Fact]) -> list[tuple[str, str]]:
    """Fact ids that changed, appeared or went away, in the newer filing's order.

    Returns (id, kind) with kind "changed", "added" or "removed".
    """
    found: list[tuple[str, str]] = []
    for fact_id, fact in newer.items():
        if fact_id.startswith(LEFT_OUT):
            continue
        if fact_id not in older:
            found.append((fact_id, "added"))
        elif _differs(older[fact_id], fact):
            found.append((fact_id, "changed"))
    found += [(i, "removed") for i in older if i not in newer and not i.startswith(LEFT_OUT)]
    return found


def versions(facts: Facts) -> tuple[Facts, tuple[Step, ...]]:
    """The facts with the earlier values the page shows, and the steps, newest first."""
    current = facts.filing
    filed = {i: facts.get(i) for i in facts.ids() if facts.document_of(i) == current}
    chain: list[tuple[Document, dict[str, Fact], bool]] = [
        (_document(file), {f.id: f for f in file.facts}, True) for file in facts.history
    ]
    chain.append((current, filed, False))

    steps: list[Step] = []
    shown: dict[str, list[Fact]] = {}  # earlier facts to add, by document id
    for (old_doc, old, _), (new_doc, new, new_is_history) in itertools.pairwise(chain):
        later = shown.setdefault(new_doc.id, []) if new_is_history else None
        changes = []
        for fact_id, kind in compare(old, new):
            before = after = when = None
            if kind != "added":
                before = history_ref(old_doc.id, fact_id)
                shown.setdefault(old_doc.id, []).append(old[fact_id])
            if kind != "removed":
                after = _on_page(new_doc, new, fact_id, later)
                if fact_id + ".when" in new:
                    when = _on_page(new_doc, new, fact_id + ".when", later)
            fact = new.get(fact_id) or old[fact_id]
            changes.append(Change(fact_id, fact.title, before, after, _style(fact), when))
        # Two columns of one table share a title ("Total liabilities"): name each by its period.
        titles = Counter(c.title for c in changes)
        for index, change in enumerate(changes):
            fact = new.get(change.id) or old[change.id]
            if titles[change.title] > 1 and fact.period:
                changes[index] = replace(change, title=f"{change.title}, {_column(fact.period)}")
        steps.append(Step(old_doc, new_doc, tuple(changes)))

    documents = {_document(f).id: _document(f) for f in facts.history}
    for document_id, earlier in shown.items():
        unique = {f.id: f for f in earlier}.values()
        renamed = [f.model_copy(update={"id": history_ref(document_id, f.id)}) for f in unique]
        facts = facts.plus(renamed, documents[document_id])
    return facts, tuple(reversed(steps))


def _column(period: str) -> str:
    """'As of Sep 30, 2026, pro forma as adjusted for ...' → 'pro forma as adjusted'."""
    words = period.removeprefix("As of Sep 30, 2026, ")
    return words.split(" for the offering")[0]


def _on_page(
    document: Document, facts: dict[str, Fact], fact_id: str, history: list[Fact] | None
) -> str:
    """The ref of a fact of the newer filing; an earlier filing's fact is added to the page."""
    if history is None:
        return fact_id
    history.append(facts[fact_id])
    return history_ref(document.id, fact_id)


def _document(file: FactFile) -> Document:
    if file.document is None:  # Facts.load refuses such a file in history/
        raise ValueError("a file in history/ must be a filing")
    return file.document
