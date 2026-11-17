"""The extractor: parsing helpers on small inputs, and the real filing when it is present."""

from __future__ import annotations

import pytest

from ipo_monitor.extract import (
    Collector,
    ExtractionError,
    Filing,
    build,
    join_lines,
    parse_number,
    render,
    sentence_around,
    strip_footnotes,
)

from .conftest import FACTS_DIR, RAW_EARLIER, RAW_FILING

PAGE = (
    '<div style="--justify:justify;content-visibility:auto;float:none;height:792pt;'
    'position:relative;width:612pt">'
)


def footer(label: str) -> str:
    return (
        '<div style="position:absolute;top:720pt"><div style="width:468pt">'
        f'<div style="line-height:7pt"><font style="font-size:9pt">{label}</font></div></div></div>'
    )


def line(text: str) -> str:
    return f"<div><font>{text}</font></div>"


def table(*rows: list[str]) -> str:
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tbody>{body}</tbody></table>"


SAMPLE = "".join(
    [
        "<html><body>",
        PAGE,
        line("As filed on the cover."),
        "</div>",
        PAGE,
        footer("41"),
        line("Our revenue was $33.2 billion for the nine months ended September 30,"),
        line("2026, up from $2.5 billion. We are growing our go-"),
        line("to-market team."),
        line("Results Table"),
        table(
            ["(in millions)", "2025", "2026(1)"],
            ["Revenue", "$2,545", "$33,242"],
            ["Operating loss(2)", "(5,224)", "(1,260)"],
            ["Bartz settlement", "1,500", "&#8212;"],
        ),
        "</div>",
        "</body></html>",
    ]
)


def test_parse_number() -> None:
    assert parse_number("$16,956") == 16956
    assert parse_number("(567)") == -567
    assert parse_number("$(104,039)") == -104039
    assert parse_number("—") == 0
    assert parse_number("7,427,991,791 shares (or 7,551,741,791 shares if exercised)") == 7427991791
    assert parse_number("$2.0928") == pytest.approx(2.0928)
    with pytest.raises(ExtractionError):
        parse_number("n/a")


def test_strip_footnotes() -> None:
    assert strip_footnotes("Net loss(2)") == "Net loss"
    assert strip_footnotes("Total(4)(5)") == "Total"
    assert strip_footnotes("Operating income (loss)") == "Operating income (loss)"


def test_join_lines_keeps_hyphenated_words_whole() -> None:
    assert join_lines(["efficient go-", "to-market motion", "and more"]) == (
        "efficient go-to-market motion and more"
    )


def test_sentence_around() -> None:
    text = "First sentence here. The price is $74.00 per share today. Last one."
    start = text.index("$74.00")
    assert sentence_around(text, start, start + 6) == "The price is $74.00 per share today."
    bullets = "after giving effect to: •one thing; and •1,234 shares of stock for a plan;"
    start = bullets.index("1,234")
    assert sentence_around(bullets, start, start + 5).startswith("1,234 shares")
    cut = "Complete. This one runs off the page and"
    assert sentence_around(cut, 12, 16).endswith("…")


def test_pages_lines_and_rows() -> None:
    filing = Filing(SAMPLE)
    assert filing.page_count == 2
    assert [page for page, _ in filing.page_text] == ["sheet 1", "41"]
    hit = filing.sentence(
        r"revenue was \$([\d.]+) billion for the nine months ended September 30, 2026"
    )
    assert hit.page == "41"
    assert hit.match.group(1) == "33.2"
    assert hit.quote.startswith("Our revenue was $33.2 billion")
    assert "go-to-market" in filing.page_text[1][1]
    start = filing.index_of(r"^Results Table$")
    row = filing.row_after(start, r"Operating loss")
    assert row.cells == ("Operating loss(2)", "(5,224)", "(1,260)")
    assert row.page == "41"


def test_table_becomes_one_fact_per_cell() -> None:
    collector = Collector(Filing(SAMPLE))
    collector.table(
        "t",
        anchor=r"^Results Table$",
        header=r"\(in millions\)",
        header_cells=["2025", "2026"],
        columns=[("a", "Year 2025"), ("b", "Year 2026")],
        rows=[("revenue", r"Revenue"), ("op", r"Operating loss"), ("bartz", r"Bartz settlement")],
        section="Sample",
    )
    by_id = {f.id: f for f in collector.facts}
    assert by_id["t.revenue.b"].value == 33_242_000_000
    assert by_id["t.op.b"].value == -1_260_000_000
    assert by_id["t.bartz.b"].value == 0
    fact = by_id["t.op.a"]
    assert (fact.title, fact.page, fact.scale, fact.period) == (
        "Operating loss",
        "41",
        "in millions",
        "Year 2025",
    )
    assert fact.quote == "Operating loss(2) | (5,224) | (1,260)"
    assert fact.context == "(in millions) | 2025 | 2026(1)"


def test_missing_figures_stop_the_extraction() -> None:
    filing = Filing(SAMPLE)
    with pytest.raises(ExtractionError):
        filing.sentence(r"net income of \$\d+")
    with pytest.raises(ExtractionError):
        filing.index_of(r"^No Such Table$")
    with pytest.raises(ExtractionError):
        filing.row_after(0, r"No such row")
    with pytest.raises(ExtractionError):
        Collector(filing).table(
            "t",
            anchor=r"^Results Table$",
            header=r"\(in millions\)",
            header_cells=["2024", "2025"],
            columns=[("a", "A"), ("b", "B")],
            rows=[("revenue", r"Revenue")],
            section="Sample",
        )
    with pytest.raises(ExtractionError):
        Filing("<html><body>no pages</body></html>")


@pytest.mark.skipif(not RAW_FILING.exists(), reason="the saved filing is not in data/raw/sec/")
def test_extraction_reproduces_the_committed_dataset() -> None:
    regenerated = render(build(RAW_FILING, document_id="s1a3"))
    assert regenerated == (FACTS_DIR / "s1a3.json").read_text("utf-8")


@pytest.mark.skipif(not RAW_EARLIER.exists(), reason="the saved filing is not in data/raw/sec/")
def test_the_same_code_reproduces_the_earlier_filing() -> None:
    # Amendment No. 2 words three passages differently; the extractor reads both wordings.
    regenerated = render(build(RAW_EARLIER, document_id="s1a2"))
    assert regenerated == (FACTS_DIR / "history" / "s1a2.json").read_text("utf-8")
