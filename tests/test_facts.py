"""The dataset: every fact is sourced."""

from __future__ import annotations

import re

import pytest

from ipo_monitor.facts import Facts, MissingFactError


def test_dataset_is_loaded(facts: Facts) -> None:
    assert len(facts) > 250
    document = facts.documents["s1a2"]
    assert document.accession == "0001628280-26-072484"
    assert document.filed == "2026-11-10"
    assert document.url.startswith("https://www.sec.gov/Archives/edgar/data/2130357/")


def test_every_filed_fact_says_where_it_comes_from(facts: Facts) -> None:
    for fact_id in facts.ids():
        fact = facts.get(fact_id)
        if fact.label != "FILED":
            continue
        assert fact.title, fact_id
        assert fact.page, fact_id
        assert fact.section, fact_id
        assert fact.quote, fact_id
        assert facts.document_of(fact_id) is not None, fact_id


def test_every_filed_value_appears_in_its_quote(facts: Facts) -> None:
    """The figure as filed must be readable in the quoted passage."""
    for fact_id in facts.ids():
        fact = facts.get(fact_id)
        if fact.label != "FILED":
            continue
        number = re.search(r"\d[\d,]*(?:\.\d+)?", fact.as_filed)
        needle = number.group(0) if number else fact.as_filed
        assert needle in fact.quote, f"{fact_id}: {needle!r} not in quote"


def test_every_press_fact_names_its_article(facts: Facts) -> None:
    press = [facts.get(i) for i in facts.ids() if facts.get(i).label == "PRESS"]
    assert press
    for fact in press:
        assert fact.outlet, fact.id
        assert fact.url, fact.id
        assert fact.url.startswith("https://"), fact.id
        assert fact.published, fact.id
        assert fact.accessed, fact.id
        assert fact.quote, fact.id


def test_unknown_fact_is_an_error(facts: Facts) -> None:
    with pytest.raises(MissingFactError):
        facts.get("does.not.exist")


def test_text_fact_is_not_a_number(facts: Facts) -> None:
    with pytest.raises(TypeError):
        facts.num("offering.symbol")
    assert facts.text("offering.symbol") == "ANT"
