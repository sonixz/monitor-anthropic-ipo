"""Charts: scales, ticks, label placement, and what each mark carries."""

from __future__ import annotations

import re
from html.parser import HTMLParser

import pytest

from ipo_monitor import charts
from ipo_monitor.charts import Box, Mark, Range, Scale
from ipo_monitor.render import Page


def mark(ref: str, value: float, text: str | None = None, kind: str = "filed") -> Mark:
    return Mark(ref, f"src-{ref}", f"what {ref} is", value, text or f"${value:,.1f}B", kind)


def money(value: float) -> str:
    return f"${value:,.0f}B"


class Texts(HTMLParser):
    """The text of an SVG, with the attributes of the element that holds it."""

    def __init__(self) -> None:
        super().__init__()
        self.open: list[dict[str, str | None]] = []
        self.found: list[tuple[str, dict[str, str | None]]] = []
        self.marks: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        self.open.append(a)
        if "mark" in (a.get("class") or "").split():
            self.marks.append(a)

    def handle_endtag(self, tag: str) -> None:
        self.open.pop()

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.found.append((data.strip(), self.open[-1]))


def read(svg: str) -> Texts:
    parser = Texts()
    parser.feed(svg)
    return parser


def test_round_ticks() -> None:
    assert charts.nice_step(17.6) == 5
    assert charts.nice_step(1500, 3) == 500
    assert charts.nice_step(2.3, 3) == 1
    assert charts.ticks(0, 17.6) == [0, 5, 10, 15]
    assert charts.ticks(-258.7, 18.7) == [-200, -100, 0]
    assert charts.ticks(0, 0.9, 3) == [0, 0.5]
    with pytest.raises(ValueError, match="positive span"):
        charts.nice_step(0)


def test_the_range_drawn_always_includes_zero() -> None:
    assert charts.extent([3.0, 8.0]) == (0.0, 8.0)
    assert charts.extent([-4.0, 6.0], headroom=0.1) == (-5.0, 7.0)
    assert charts.extent([-4.0, -1.0]) == (-4.0, 0.0)
    with pytest.raises(ValueError, match="nothing to draw"):
        charts.extent([0.0, 0.0])


def test_scale_and_coordinates() -> None:
    scale = Scale(0, 10, 100, 0)
    assert scale(0) == 100
    assert scale(10) == 0
    assert scale(2.5) == 75
    assert charts.num(12.0) == "12"
    assert charts.num(12.345) == "12.35"
    assert charts.num(-0.001) == "0"


def test_a_column_is_rounded_at_its_value_end_only() -> None:
    up = charts.column_path(10, 20, 100, 40)
    assert up.startswith("M10,100V43Q10,40 13,40H27")  # square at the baseline, round at the top
    assert up.endswith("V100Z")
    down = charts.column_path(10, 20, 100, 160)
    assert "V157Q10,160 13,160" in down  # a negative value is rounded at the bottom
    flat = charts.column_path(10, 20, 100, 99)
    assert "Q10,99 11,99" in flat  # the rounding never exceeds the height of the column


def test_text_is_escaped() -> None:
    assert charts.tag("text", charts.esc("a < b & c"), class_="x") == (
        '<text class="x">a &lt; b &amp; c</text>'
    )
    assert charts.attrs(data_tip='say "hi"', hidden=False, data_tick=True, x=1.5) == (
        ' data-tip="say &#34;hi&#34;" data-tick x="1.5"'
    )


def test_a_label_that_would_overlap_is_left_out() -> None:
    first, second, third = mark("a", 1, "$100.0B"), mark("b", 2, "$200.0B"), mark("c", 3, "$3B")
    printed, refs = charts.place(
        [(first, 100, 50, "middle"), (second, 110, 52, "middle"), (third, 250, 50, "middle")]
    )
    assert refs == ("a", "c")
    assert "$200.0B" not in printed
    assert Box(0, 0, 10, 10).hits(Box(11, 0, 20, 10))  # closer than the margin
    assert not Box(0, 0, 10, 10).hits(Box(13, 0, 20, 10))
    assert not Box(0, 0, 10, 10).hits(Box(0, 10, 10, 20))


def test_columns_carry_their_source() -> None:
    marks = [mark(f"q{i}", value) for i, value in enumerate([0.4, 0.8, 4.7, 17.0])]
    chart = charts.columns(
        marks,
        xlabels=["Q1", "Q2", "Q3", "Q4"],
        groups=[("2025", 0, 3)],
        tick_fmt=money,
        label=[3, 2, 0],
        aria="Revenue by quarter.",
    )
    svg = read(str(chart.svg))
    assert [m["data-ref"] for m in svg.marks] == ["q0", "q1", "q2", "q3"]
    assert all(m["data-src"] == f"src-{m['data-ref']}" for m in svg.marks)
    assert svg.marks[3]["data-tip"] == "what q3 is · $17.0B"
    assert chart.marks == tuple(marks)
    assert chart.labels == ("q3", "q2", "q0")
    assert 'role="img"' in chart.svg
    assert 'aria-label="Revenue by quarter."' in chart.svg
    assert "style=" not in chart.svg


def test_chart_text_is_a_sourced_value_a_tick_or_a_label() -> None:
    marks = [mark(f"q{i}", value) for i, value in enumerate([-249.0, -35.0, 8.0])]
    chart = charts.columns(
        marks,
        xlabels=["Q1", "Q2", "Q3"],
        tick_fmt=lambda v: f"{v:.0f}%",
        label=[2, 0],
        signed=True,
        aria="Margin.",
    )
    for text, attrs in read(str(chart.svg)).found:
        if re.search(r"\d", text):
            assert "data-ref" in attrs or "data-tick" in attrs or "data-label" in attrs, text
    assert 'class="col neg"' in chart.svg
    assert 'class="col pos"' in chart.svg


def test_lines_draw_one_dot_per_value_and_skip_missing_ones() -> None:
    first: list[Mark | None] = [None, mark("a1", 109, "+109%"), mark("a2", 47, "+47%")]
    chart = charts.lines(
        [("s1", first)],
        xlabels=["Q1", "Q2", "Q3"],
        tick_fmt=lambda v: f"{v:.0f}%",
        label=[(0, 2, "below"), (0, 0, "above")],
        reference=(100, "doubling"),
        aria="Growth.",
    )
    assert chart.svg.count('class="dot s1"') == 2
    assert chart.labels == ("a2",)  # the missing value has no label
    assert "doubling" in chart.svg
    assert len(chart.marks) == 2


def test_grouped_columns_and_ranges() -> None:
    groups = [
        ("2025", [mark("op25", 8.1), mark("net25", 42.0)]),
        ("2026", [mark("op26", 1.3), mark("net26", 104.0)]),
    ]
    chart = charts.grouped(
        groups, tones=["s1", "s2"], tick_fmt=money, label=[(1, 1), (1, 0)], aria="Losses."
    )
    assert [m.ref for m in chart.marks] == ["op25", "net25", "op26", "net26"]
    assert chart.labels == ("net26", "op26")
    assert chart.svg.count('class="col s2"') == 2

    row = Range(
        "Outstanding",
        mark("lo", 917, "$917B", "calc"),
        mark("mid", 968, "$968B", "calc"),
        mark("hi", 1019, "$1,019B", "calc"),
        ((mark("press", 1020, "$1,020B", "press"), "Reuters"),),
    )
    chart = charts.ranges([row], tick_fmt=money, between="to", aria="Value.")
    assert [m.ref for m in chart.marks] == ["lo", "mid", "hi", "press"]
    assert set(chart.labels) == {"lo", "hi", "press"}
    assert "Reuters $1,020B" in chart.svg
    assert 'class="cv cv-press"' in chart.svg


def test_the_page_has_its_charts(page: Page) -> None:
    assert len(page.charts) >= 8
    assert set(page.charts) >= {
        "value.ranges",
        "ev.bridge",
        "ev.ranges",
        "contracts.due_by_year",
        "growth.revenue",
        "growth.qoq",
        "growth.revenue_vs_compute",
        "growth.margin",
        "losses.by_year",
    }
    drawn = page.html.count('class="chart-svg"') + page.html.count('class="chart-svg ring"')
    assert drawn == len(page.charts) - 1  # the bridge is in a table


def test_every_value_a_chart_draws_is_also_a_number_in_a_table(page: Page) -> None:
    buttons = set(
        re.findall(
            r'<button type="button" class="n [^"]*" popovertarget="[^"]+" data-ref="([^"]+)"',
            page.html,
        )
    )
    cards = set(re.findall(r'<div popover id="(src-[^"]+)"', page.html))
    for name, marks in page.charts.items():
        assert marks, name
        for drawn in marks:
            assert drawn.ref in buttons, f"{name}: {drawn.ref} is on a chart but in no table"
            assert drawn.src in cards, f"{name}: {drawn.ref} has no source card"


def test_a_ring_draws_parts_of_one_whole() -> None:
    from ipo_monitor import charts
    from ipo_monitor.charts import Mark

    def mark(ref: str, value: float) -> Mark:
        return Mark(ref, "src-" + ref, ref, value, f"{value}%", "filed")

    parts = [mark("a", 50.1), mark("b", 44.4), mark("c", 5.5)]
    chart = charts.ring(parts, ["t1", "t2", "t3"], centre=parts[0], caption="one share", aria="x")
    svg = str(chart.svg)
    assert svg.count('class="col slice') == 3
    for ref in ("a", "b", "c"):
        assert f'data-ref="{ref}"' in svg
    # The first slice starts at the top and, past half the circle, takes the long arc.
    first = svg.split(' d="', 1)[1].split('"', 1)[0]
    assert first.startswith("M75,4A71,71 0 1 1")
    assert chart.labels == ("a",)
    assert "one share" in svg
    with __import__("pytest").raises(ValueError):
        charts.ring(parts, ["t1"], centre=parts[0], caption="", aria="x")
