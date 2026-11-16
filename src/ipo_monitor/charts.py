"""Charts drawn on the server as SVG. No library, no script, no inline style.

Every mark carries the id of the fact or calculation it draws (`data-ref`) and
the id of its source card (`data-src`), so selecting it opens the same card as
the number in the table next to it. Axis ticks are scale marks, not facts: they
are the only digits without a source and are flagged `data-tick`.

Charts are designed at phone width (320 units). Wider screens show them side
by side, so their text keeps about the same size everywhere.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from markupsafe import Markup, escape

WIDTH = 320.0
FONT = 11.0  # size of chart text, in chart units
CHAR = 0.61  # advance of one monospace glyph, in em
BAR = 24.0  # a column is never thicker than this
RADIUS = 3.0  # rounding of the data end of a bar
TickFormat = Callable[[float], str]


@dataclass(frozen=True)
class Mark:
    """One value drawn on a chart, with the id it comes from."""

    ref: str
    src: str  # id of the source card
    label: str  # what it is, in words: "Q3 2026"
    value: float  # in the unit of the chart
    text: str  # as printed: "$17.0B"
    kind: str  # filed, calc or press

    @property
    def tip(self) -> str:
        return f"{self.label} · {self.text}"


@dataclass(frozen=True)
class Chart:
    """A rendered chart: the SVG and the marks it drew."""

    svg: Markup
    marks: tuple[Mark, ...]
    labels: tuple[str, ...]  # refs printed as text on the chart


@dataclass(frozen=True)
class Box:
    """The space a piece of text takes."""

    x0: float
    y0: float
    x1: float
    y1: float

    def hits(self, other: Box, margin: float = 2.0) -> bool:
        return not (
            self.x1 + margin <= other.x0
            or other.x1 + margin <= self.x0
            or self.y1 <= other.y0
            or other.y1 <= self.y0
        )


@dataclass(frozen=True)
class Scale:
    """A straight line from values to positions."""

    lo: float
    hi: float
    start: float
    end: float

    def __call__(self, value: float) -> float:
        return self.start + (value - self.lo) / (self.hi - self.lo) * (self.end - self.start)


# -- small helpers ---------------------------------------------------------


def num(value: float) -> str:
    """A coordinate, short."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def attrs(**pairs: object) -> str:
    out = []
    for key, value in pairs.items():
        if value is None or value is False:
            continue
        name = key.rstrip("_").replace("_", "-")
        if value is True:
            out.append(f" {name}")
            continue
        text = num(value) if isinstance(value, float) else str(value)
        out.append(f' {name}="{escape(text)}"')
    return "".join(out)


def tag(name: str, content: str = "", **pairs: object) -> str:
    """An element. `content` is markup already; escape text with `esc` first."""
    if not content and name in {"rect", "line", "path", "circle"}:
        return f"<{name}{attrs(**pairs)}/>"
    return f"<{name}{attrs(**pairs)}>{content}</{name}>"


def esc(text: str) -> str:
    return str(escape(text))


def text_width(text: str, size: float = FONT) -> float:
    return len(text) * size * CHAR


def nice_step(span: float, target: int = 4) -> float:
    """A round distance between ticks: 1, 2, 2.5 or 5 times a power of ten."""
    if span <= 0:
        raise ValueError("a scale needs a positive span")
    raw = span / max(target, 1)
    power: float = 10 ** math.floor(math.log10(raw))
    for multiple in (1.0, 2.0, 2.5, 5.0):
        if raw <= multiple * power * (1 + 1e-9):
            return multiple * power
    return 10 * power


def ticks(lo: float, hi: float, target: int = 4) -> list[float]:
    """Round values between lo and hi, zero included when it is in range."""
    step = nice_step(hi - lo, target)
    value = math.ceil(lo / step - 1e-9) * step
    out = []
    while value <= hi + step * 1e-9:
        out.append(0.0 if abs(value) < step * 1e-9 else round(value, 10))
        value += step
    return out


def extent(values: Sequence[float], headroom: float = 0.0) -> tuple[float, float]:
    """The range to draw, zero included."""
    lo, hi = min(0.0, *values), max(0.0, *values)
    span = hi - lo
    if span == 0:
        raise ValueError("nothing to draw")
    return (lo - span * headroom if lo < 0 else 0.0, hi + span * headroom if hi > 0 else 0.0)


def column_path(x: float, width: float, base: float, end: float) -> str:
    """A column from the baseline to its value, rounded at the value end only."""
    radius = min(RADIUS, width / 2, abs(end - base))
    turn = radius if end < base else -radius  # towards the baseline
    return (
        f"M{num(x)},{num(base)}V{num(end + turn)}Q{num(x)},{num(end)} {num(x + radius)},{num(end)}"
        f"H{num(x + width - radius)}Q{num(x + width)},{num(end)} {num(x + width)},{num(end + turn)}"
        f"V{num(base)}Z"
    )


def value_text(mark: Mark, x: float, y: float, anchor: str = "middle") -> str:
    return tag(
        "text",
        esc(mark.text),
        class_=f"cv cv-{mark.kind}",
        x=x,
        y=y,
        text_anchor=anchor,
        data_ref=mark.ref,
        data_src=mark.src,
    )


def mark_group(mark: Mark, content: str, extra: str = "") -> str:
    return tag(
        "g",
        content,
        class_=("mark " + extra).strip(),
        data_ref=mark.ref,
        data_src=mark.src,
        data_tip=mark.tip,
        data_kind=mark.kind,
    )


def place(wanted: Sequence[tuple[Mark, float, float, str]]) -> tuple[str, tuple[str, ...]]:
    """Print value labels in order of priority; one that would overlap is left out."""
    taken: list[Box] = []
    out: list[str] = []
    refs: list[str] = []
    for mark, x, y, anchor in wanted:
        width = text_width(mark.text)
        x0 = x - width / 2 if anchor == "middle" else x - width if anchor == "end" else x
        box = Box(x0, y - FONT, x0 + width, y + 2)
        if any(box.hits(other) for other in taken):
            continue
        taken.append(box)
        out.append(value_text(mark, x, y, anchor))
        refs.append(mark.ref)
    return "".join(out), tuple(refs)


def svg(content: str, height: float, label: str) -> Markup:
    # Safe: every piece of text in `content` went through `esc` or `attrs`.
    return Markup(  # noqa: S704
        tag(
            "svg",
            content,
            class_="chart-svg",
            viewBox=f"0 0 {num(WIDTH)} {num(height)}",
            role="img",
            aria_label=label,
            focusable="false",
        )
    )


# -- frame shared by the charts with a value axis ---------------------------


@dataclass(frozen=True)
class Frame:
    slots: int
    height: float
    two_rows: bool
    left: float = 40.0
    right: float = 4.0
    top: float = 18.0

    @property
    def bottom(self) -> float:
        return self.height - (34.0 if self.two_rows else 20.0)

    @property
    def band(self) -> float:
        return (WIDTH - self.left - self.right) / self.slots

    def centre(self, slot: int) -> float:
        return self.left + self.band * (slot + 0.5)

    def clamp(self, x: float, width: float) -> float:
        """Keep a centred text of this width inside the chart."""
        return min(max(x, width / 2 + 1), WIDTH - width / 2 - 1)


def axes(
    frame: Frame,
    scale: Scale,
    tick_values: Sequence[float],
    tick_fmt: TickFormat,
    xlabels: Sequence[str],
    groups: Sequence[tuple[str, int, int]],
) -> str:
    parts = []
    for value in tick_values:
        y = scale(value)
        parts.append(
            tag(
                "line",
                class_="zero" if value == 0 else "grid",
                x1=frame.left,
                x2=WIDTH - frame.right,
                y1=y,
                y2=y,
            )
        )
        parts.append(
            tag(
                "text",
                esc(tick_fmt(value)),
                class_="tick",
                x=frame.left - 6,
                y=y + 3.5,
                text_anchor="end",
                data_tick=True,
            )
        )
    for slot, label in enumerate(xlabels):
        parts.append(
            tag(
                "text",
                esc(label),
                class_="xl",
                x=frame.centre(slot),
                y=frame.bottom + 14,
                text_anchor="middle",
                data_label=True,
            )
        )
    for label, first, last in groups:
        x0, x1 = frame.left + frame.band * first + 3, frame.left + frame.band * (last + 1) - 3
        y = frame.bottom + 20
        parts.append(tag("line", class_="grid", x1=x0, x2=x1, y1=y, y2=y))
        parts.append(
            tag(
                "text",
                esc(label),
                class_="xl",
                x=(x0 + x1) / 2,
                y=y + 11,
                text_anchor="middle",
                data_label=True,
            )
        )
    return tag("g", "".join(parts), class_="axis", aria_hidden="true")


def hit(frame: Frame, slot: int) -> str:
    return tag(
        "rect",
        class_="hit",
        x=frame.left + frame.band * slot,
        y=frame.top - 14,
        width=frame.band,
        height=frame.bottom - frame.top + 14,
    )


# -- columns -----------------------------------------------------------------


def columns(
    marks: Sequence[Mark | None],
    *,
    xlabels: Sequence[str],
    tick_fmt: TickFormat,
    label: Sequence[int],
    aria: str,
    groups: Sequence[tuple[str, int, int]] = (),
    tone: str = "s1",
    signed: bool = False,
    apart: Sequence[int] = (),
    height: float = 168.0,
) -> Chart:
    """Columns on one baseline. `signed` colours them by sign; `apart` slots are drawn muted."""
    drawn = [m for m in marks if m is not None]
    frame = Frame(len(marks), height, bool(groups))
    lo, hi = extent([m.value for m in drawn], headroom=0.04)
    scale = Scale(lo, hi, frame.bottom if lo == 0 else frame.bottom - 12, frame.top)
    width = min(BAR, frame.band * 0.62)
    base = scale(0)
    body = []
    for slot, mark in enumerate(marks):
        if mark is None:
            continue
        end = scale(mark.value)
        kind = ("pos" if mark.value >= 0 else "neg") if signed else tone
        if slot in apart:
            kind += " apart"
        column = tag(
            "path",
            class_=f"col {kind}",
            d=column_path(frame.centre(slot) - width / 2, width, base, end),
        )
        body.append(mark_group(mark, hit(frame, slot) + column))
    wanted = []
    for slot in label:
        mark = marks[slot]
        if mark is None:
            continue
        end = scale(mark.value)
        y = end - 5 if mark.value >= 0 else end + FONT + 2
        wanted.append((mark, frame.clamp(frame.centre(slot), text_width(mark.text)), y, "middle"))
    printed, refs = place(wanted)
    content = (
        axes(frame, scale, ticks(lo, hi), tick_fmt, xlabels, groups)
        + tag("g", "".join(body), class_="marks")
        + tag("g", printed, class_="labels")
    )
    return Chart(svg(content, height, aria), tuple(drawn), refs)


# -- lines ---------------------------------------------------------------------


def lines(
    series: Sequence[tuple[str, Sequence[Mark | None]]],
    *,
    xlabels: Sequence[str],
    tick_fmt: TickFormat,
    label: Sequence[tuple[int, int, str]],
    aria: str,
    groups: Sequence[tuple[str, int, int]] = (),
    reference: tuple[float, str] | None = None,
    height: float = 168.0,
) -> Chart:
    """One or two series over time, as (tone, marks).

    `label` lists (series, slot, "above" or "below") by priority. `reference`
    draws a named level to read the lines against.
    """
    drawn = [m for _, marks in series for m in marks if m is not None]
    frame = Frame(len(xlabels), height, bool(groups))
    lo, hi = extent([m.value for m in drawn], headroom=0.1)
    scale = Scale(lo, hi, frame.bottom, frame.top)
    body = []
    if reference is not None:
        level, name = reference
        y = scale(level)
        body.append(tag("line", class_="ref", x1=frame.left, x2=WIDTH - frame.right, y1=y, y2=y))
        body.append(tag("text", esc(name), class_="ref-label", x=frame.left + 3, y=y - 4))
    for tone, marks in series:
        points = [(frame.centre(i), scale(m.value)) for i, m in enumerate(marks) if m is not None]
        path = "M" + "L".join(f"{num(x)},{num(y)}" for x, y in points)
        body.append(tag("path", class_=f"ln {tone}", d=path))
    for tone, marks in series:
        for slot, mark in enumerate(marks):
            if mark is None:
                continue
            x, y = frame.centre(slot), scale(mark.value)
            area = (
                hit(frame, slot)
                if len(series) == 1
                else tag("circle", class_="hit", cx=x, cy=y, r=12.0)
            )
            dot = tag("circle", class_=f"dot {tone}", cx=x, cy=y, r=4.0)
            body.append(mark_group(mark, area + dot))
    wanted = []
    for index, slot, side in label:
        mark = series[index][1][slot]
        if mark is None:
            continue
        y = scale(mark.value) - 9
        if side == "below" or y - FONT < 0:
            y = scale(mark.value) + FONT + 7
        wanted.append((mark, frame.clamp(frame.centre(slot), text_width(mark.text)), y, "middle"))
    printed, refs = place(wanted)
    content = (
        axes(frame, scale, ticks(lo, hi), tick_fmt, xlabels, groups)
        + tag("g", "".join(body), class_="marks")
        + tag("g", printed, class_="labels")
    )
    return Chart(svg(content, height, aria), tuple(drawn), refs)


# -- columns side by side ----------------------------------------------------


def grouped(
    groups: Sequence[tuple[str, Sequence[Mark]]],
    *,
    tones: Sequence[str],
    tick_fmt: TickFormat,
    label: Sequence[tuple[int, int]],
    aria: str,
    height: float = 168.0,
) -> Chart:
    """A few series compared within each group. The legend is printed by the page."""
    drawn = [mark for _, series in groups for mark in series]
    frame = Frame(len(groups), height, two_rows=False)
    lo, hi = extent([m.value for m in drawn], headroom=0.04)
    scale = Scale(lo, hi, frame.bottom, frame.top)
    count = len(tones)
    gap = 2.0
    width = min(BAR, (frame.band * 0.7 - gap * (count - 1)) / count)
    total = width * count + gap * (count - 1)
    base = scale(0)

    def left_of(slot: int, index: int) -> float:
        return frame.centre(slot) - total / 2 + index * (width + gap)

    body = []
    for slot, (_, series) in enumerate(groups):
        for index, mark in enumerate(series):
            x = left_of(slot, index)
            area = tag(
                "rect",
                class_="hit",
                x=x - gap / 2,
                y=frame.top - 14,
                width=width + gap,
                height=frame.bottom - frame.top + 14,
            )
            column = tag(
                "path",
                class_=f"col {tones[index]}",
                d=column_path(x, width, base, scale(mark.value)),
            )
            body.append(mark_group(mark, area + column))
    wanted = []
    for slot, index in label:
        mark = groups[slot][1][index]
        y = scale(mark.value) - 5
        if index == 0 and count > 1:
            # The first of a group grows to the left, away from its taller neighbour.
            wanted.append((mark, left_of(slot, index) + width, y, "end"))
        else:
            x = left_of(slot, index) + width / 2
            wanted.append((mark, frame.clamp(x, text_width(mark.text)), y, "middle"))
    printed, refs = place(wanted)
    content = (
        axes(frame, scale, ticks(lo, hi), tick_fmt, [name for name, _ in groups], ())
        + tag("g", "".join(body), class_="marks")
        + tag("g", printed, class_="labels")
    )
    return Chart(svg(content, height, aria), tuple(drawn), refs)


# -- ranges on one axis ------------------------------------------------------


@dataclass(frozen=True)
class Range:
    """One row: a value at the low, middle and high end, and outside figures to compare."""

    name: str
    low: Mark
    mid: Mark
    high: Mark
    others: tuple[tuple[Mark, str], ...] = ()  # (mark, short name) drawn under the bar


def ranges(rows: Sequence[Range], *, tick_fmt: TickFormat, between: str, aria: str) -> Chart:
    """Rows on one axis from zero: a pale bar up to the low value, a full one over the range."""
    row_height = 46.0
    top = 2.0
    height = top + row_height * len(rows) + 16
    values = [m.value for row in rows for m in (row.low, row.high, *(o for o, _ in row.others))]
    step = nice_step(max(values), 3)
    hi = math.ceil(max(values) / step - 1e-9) * step
    scale = Scale(0.0, hi, 0.0, WIDTH - 1)
    axis = []
    bottom = top + row_height * len(rows)
    tick_values = ticks(0.0, hi, 3)
    axis.append(tag("line", class_="zero", x1=0.0, x2=WIDTH - 1, y1=bottom + 1, y2=bottom + 1))
    for value in tick_values:
        x = scale(value)
        axis.append(tag("line", class_="zero", x1=x, x2=x, y1=bottom - 3, y2=bottom + 1))
        anchor = "start" if value == 0 else "end" if value == tick_values[-1] else "middle"
        axis.append(
            tag(
                "text",
                esc(tick_fmt(value)),
                class_="tick",
                x=x,
                y=bottom + 13,
                text_anchor=anchor,
                data_tick=True,
            )
        )
    body = []
    texts = []
    printed: list[str] = []
    marks: list[Mark] = []
    for index, row in enumerate(rows):
        y = top + row_height * index
        x_low, x_mid, x_high = scale(row.low.value), scale(row.mid.value), scale(row.high.value)
        texts.append(tag("text", esc(row.name), class_="row-name", x=0.0, y=y + 11))
        high_width = text_width(row.high.text)
        gap = text_width(f" {between} ")
        texts.append(value_text(row.high, WIDTH, y + 11, "end"))
        texts.append(
            tag(
                "text",
                esc(between),
                class_="row-join",
                x=WIDTH - high_width - gap / 2,
                y=y + 11,
                text_anchor="middle",
            )
        )
        texts.append(value_text(row.low, WIDTH - high_width - gap, y + 11, "end"))
        printed += [row.low.ref, row.high.ref]
        bar_y = y + 17
        body.append(tag("rect", class_="track", x=0.0, y=bar_y, width=WIDTH, height=10.0, rx=2.0))
        body.append(tag("rect", class_="col s1 pale", x=0.0, y=bar_y, width=x_low - 1, height=10.0))
        span = tag(
            "rect",
            class_="col s1",
            x=x_low + 1,
            y=bar_y,
            width=x_high - x_low - 1,
            height=10.0,
            rx=2.0,
        )
        notch = tag("line", class_="notch", x1=x_mid, x2=x_mid, y1=bar_y, y2=bar_y + 10)
        area = tag(
            "rect", class_="hit", x=x_low - 6, y=bar_y - 4, width=x_high - x_low + 12, height=18.0
        )
        body.append(mark_group(row.mid, area + span + notch))
        marks += [row.low, row.mid, row.high]
        for other, name in row.others:
            x = scale(other.value)
            pointer = tag(
                "path",
                class_=f"pointer cv-{other.kind}",
                d=f"M{num(x)},{num(bar_y + 12)}l-4,6h8Z",
            )
            caption = tag(
                "text",
                esc(f"{name} {other.text}"),
                class_=f"cv cv-{other.kind}",
                x=x - 8,
                y=bar_y + 21,
                text_anchor="end",
                data_ref=other.ref,
                data_src=other.src,
            )
            area = tag("rect", class_="hit", x=x - 12, y=bar_y + 10, width=24.0, height=14.0)
            body.append(mark_group(other, area + pointer) + caption)
            marks.append(other)
            printed.append(other.ref)
    content = (
        tag("g", "".join(axis), class_="axis", aria_hidden="true")
        + tag("g", "".join(body), class_="marks")
        + tag("g", "".join(texts), class_="labels")
    )
    return Chart(svg(content, height, aria), tuple(marks), tuple(printed))


# -- a price through the day ------------------------------------------------------


def trace(
    points: Sequence[tuple[int, float]],
    *,
    last: Mark,
    tick_fmt: TickFormat,
    ends: tuple[str, str],
    aria: str,
    level: tuple[float, str] | None = None,
    height: float = 150.0,
) -> Chart:
    """A line through many points, read against an optional named level.

    The axis does not start at zero: a price moves within a narrow band. Only
    the last point is a mark; the line is the source's own series.
    """
    left, right, top, bottom = 46.0, 8.0, 16.0, height - 20.0
    values = [value for _, value in points]
    lo, hi = min(values), max(values)
    if level is not None and lo * 0.9 <= level[0] <= hi * 1.1:
        lo, hi = min(lo, level[0]), max(hi, level[0])
    else:
        level = None
    pad = (hi - lo) * 0.12 or hi * 0.01
    lo, hi = lo - pad, hi + pad
    y = Scale(lo, hi, bottom, top)
    first, final = points[0][0], points[-1][0]
    x = Scale(
        float(first), float(final) if final > first else float(first) + 1, left, WIDTH - right
    )
    axis = []
    for value in ticks(lo, hi, 3):
        axis.append(tag("line", class_="grid", x1=left, x2=WIDTH - right, y1=y(value), y2=y(value)))
        axis.append(
            tag(
                "text",
                esc(tick_fmt(value)),
                class_="tick",
                x=left - 6,
                y=y(value) + 3.5,
                text_anchor="end",
                data_tick=True,
            )
        )
    for text, at, anchor in ((ends[0], left, "start"), (ends[1], WIDTH - right, "end")):
        axis.append(
            tag(
                "text",
                esc(text),
                class_="xl",
                x=at,
                y=bottom + 14,
                text_anchor=anchor,
                data_label=True,
            )
        )
    body = []
    if level is not None:
        body.append(
            tag("line", class_="ref", x1=left, x2=WIDTH - right, y1=y(level[0]), y2=y(level[0]))
        )
        body.append(tag("text", esc(level[1]), class_="ref-label", x=left + 3, y=y(level[0]) - 4))
    path = "M" + "L".join(f"{num(x(float(t)))},{num(y(v))}" for t, v in points)
    body.append(tag("path", class_="ln s1", d=path))
    end_x, end_y = x(float(final)), y(points[-1][1])
    area = tag("circle", class_="hit", cx=end_x, cy=end_y, r=14.0)
    body.append(mark_group(last, area + tag("circle", class_="dot s1", cx=end_x, cy=end_y, r=4.0)))
    label_y = end_y - 9 if end_y - 9 - FONT > 0 else end_y + FONT + 7
    printed, refs = place([(last, WIDTH - right, label_y, "end")])
    content = (
        tag("g", "".join(axis), class_="axis", aria_hidden="true")
        + tag("g", "".join(body), class_="marks")
        + tag("g", printed, class_="labels")
    )
    return Chart(svg(content, height, aria), (last,), refs)
