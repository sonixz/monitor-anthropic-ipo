"""Facts: numbers copied from a source, each with where it comes from.

A fact is never typed into a template. It is extracted from the filing by
`ipo_monitor.extract` (label FILED) or recorded from a named press article
(label PRESS), stored in `data/facts/*.json`, and loaded here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

Label = Literal["FILED", "PRESS", "MARKET"]
Unit = Literal["USD", "USD/share", "shares", "percent", "count", "date", "text"]


class Document(BaseModel):
    """The source document a set of FILED facts was extracted from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    company: str
    form: str
    title: str
    accession: str
    filed: str
    url: str
    source_sha256: str


class Fact(BaseModel):
    """One sourced value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    label: Label
    value: float | str
    unit: Unit
    as_filed: str
    scale: str | None = None
    period: str | None = None
    section: str | None = None
    page: str | None = None
    quote: str
    context: str | None = None
    outlet: str | None = None
    url: str | None = None
    published: str | None = None
    accessed: str | None = None


class FactFile(BaseModel):
    """One JSON file in `data/facts/`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document: Document | None = None
    facts: list[Fact]


class MissingFactError(KeyError):
    """A fact id that the code needs is not in the dataset."""


class Facts:
    """All loaded facts, by id."""

    def __init__(self, files: list[FactFile]) -> None:
        self._by_id: dict[str, Fact] = {}
        self.documents: dict[str, Document] = {}
        self._doc_of: dict[str, str] = {}
        for file in files:
            if file.document is not None:
                self.documents[file.document.id] = file.document
            for fact in file.facts:
                if fact.id in self._by_id:
                    raise ValueError(f"duplicate fact id: {fact.id}")
                self._by_id[fact.id] = fact
                if file.document is not None:
                    self._doc_of[fact.id] = file.document.id

    @classmethod
    def load(cls, directory: Path) -> Facts:
        paths = sorted(directory.glob("*.json"))
        if not paths:
            raise FileNotFoundError(f"no fact files in {directory}")
        return cls([FactFile.model_validate(json.loads(p.read_text("utf-8"))) for p in paths])

    def plus(
        self, extra: list[Fact], document: Document | None = None, *, replacing: bool = False
    ) -> Facts:
        """The same facts with some more, such as a market quote. The original is unchanged.

        `document` is the filing the extra facts were read from. `replacing` lets them take the
        place of facts with the same id: a filed price replaces one recorded from the press.
        """
        both = Facts([])
        both._by_id = dict(self._by_id)
        both.documents = dict(self.documents)
        both._doc_of = dict(self._doc_of)
        if document is not None:
            if document.id in both.documents:
                raise ValueError(f"duplicate document id: {document.id}")
            both.documents[document.id] = document
        for fact in extra:
            if fact.id in both._by_id and not replacing:
                raise ValueError(f"duplicate fact id: {fact.id}")
            both._by_id[fact.id] = fact
            both._doc_of.pop(fact.id, None)
            if document is not None:
                both._doc_of[fact.id] = document.id
        return both

    def __contains__(self, fact_id: str) -> bool:
        return fact_id in self._by_id

    def __len__(self) -> int:
        return len(self._by_id)

    def get(self, fact_id: str) -> Fact:
        try:
            return self._by_id[fact_id]
        except KeyError:
            raise MissingFactError(fact_id) from None

    def num(self, fact_id: str) -> float:
        value = self.get(fact_id).value
        if isinstance(value, str):
            raise TypeError(f"fact {fact_id} is not numeric")
        return float(value)

    def text(self, fact_id: str) -> str:
        return str(self.get(fact_id).value)

    def document_of(self, fact_id: str) -> Document | None:
        doc_id = self._doc_of.get(fact_id)
        return self.documents[doc_id] if doc_id else None

    def ids(self) -> list[str]:
        return list(self._by_id)
