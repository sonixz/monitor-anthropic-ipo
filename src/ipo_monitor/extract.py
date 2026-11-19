"""Extract FILED facts from a locally saved copy of Anthropic's Form S-1/A.

The filing is never downloaded here: the owner saves it from sec.gov into
`data/raw/sec/` (ignored by git). This module reads that copy, finds each
figure by an anchored pattern, and writes `data/facts/<id>.json` with the
value, the page and the exact passage it was copied from.

Run:  python -m ipo_monitor.extract "data/raw/sec/<file>.html"

A figure that cannot be found stops the extraction: nothing is guessed.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ipo_monitor.facts import Document, Fact, FactFile, Unit

PAGE_RE = re.compile(r'<div style="[^"]*content-visibility:auto;[^"]*height:792pt;[^"]*">')
FOOTER_RE = re.compile(
    r'top:720pt"><div style="width:468pt"><div style="[^"]*">'
    r'<font style="[^"]*">([^<]{1,8})</font>'
)
SAVED_FROM_RE = re.compile(r"saved from url=\(\d+\)(https://www\.sec\.gov/\S+?)\s*-->")
TABLE_RE = re.compile(r"(?is)<table.*?</table>")
ROW_RE = re.compile(r"(?is)<tr.*?</tr>")
CELL_RE = re.compile(r"(?is)<td.*?</td>")
SENTENCE_START_RE = re.compile(r"(?<=[.;])\s+(?=(?:\(\d+\))?[A-Z“])")
MAX_QUOTE = 420

MILLION = 1_000_000
BILLION = 1_000_000_000


class ExtractionError(RuntimeError):
    """A figure or an anchor was not found where it was expected."""


@dataclass(frozen=True)
class Item:
    """One line of text or one table row, with the page it is on."""

    kind: str  # "text" or "row"
    text: str
    cells: tuple[str, ...]
    page: str


@dataclass(frozen=True)
class Hit:
    """A regular-expression match in the text of one page."""

    match: re.Match[str]
    page: str
    quote: str


def clean(fragment: str) -> str:
    """Strip tags and normalise whitespace."""
    text = re.sub(r"<[^>]+>", "", fragment)
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def strip_footnotes(label: str) -> str:
    """'Net loss(2)' -> 'Net loss'."""
    return re.sub(r"(\(\d+\))+$", "", label).strip()


def parse_number(cell: str) -> float:
    """'$(1,260)' -> -1260.0 ; '—' -> 0.0 ; '7,427,991,791 shares (or ...)' -> 7427991791.0."""
    text = cell.strip()
    if text in {"—", "-", "–"}:
        return 0.0
    match = re.search(r"\(?\$?\(?([\d,]+(?:\.\d+)?)\)?", text)
    if match is None:
        raise ExtractionError(f"no number in cell: {cell!r}")
    number = float(match.group(1).replace(",", ""))
    negative = "(" in text[: match.end()] and ")" in text[match.start() : match.end() + 1]
    return -number if negative else number


def join_lines(lines: list[str]) -> str:
    """Join the lines of a page; a word hyphenated at a line end stays one word."""
    out = ""
    for line in lines:
        if out and re.search(r"[A-Za-z]-$", out) and re.match(r"[a-z]", line):
            out += line
        elif out:
            out += " " + line
        else:
            out = line
    return out


def sentence_around(text: str, start: int, end: int) -> str:
    """The sentence (or bullet) of `text` that contains [start, end)."""
    bounds = {0, len(text)}
    bounds.update(m.end() for m in SENTENCE_START_RE.finditer(text))
    bounds.update(m.start() for m in re.finditer("•", text))
    ordered = sorted(bounds)
    left = max(b for b in ordered if b <= start)
    right = min(b for b in ordered if b >= end)
    quote = text[left:right].strip().lstrip("•").strip()
    if len(quote) > MAX_QUOTE:
        lo = max(left, start - MAX_QUOTE // 2)
        hi = min(right, end + MAX_QUOTE // 2)
        if lo > left:
            lo = text.find(" ", lo) + 1
        if hi < right:
            hi = text.rfind(" ", lo, hi)
        quote = ("… " if lo > left else "") + text[lo:hi].strip() + (" …" if hi < right else "")
    if right == len(text) and not quote.endswith((".", ";", ":", "…")):
        quote += " …"
    return quote


class Filing:
    """A saved filing split into pages, lines and table rows."""

    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.items: list[Item] = []
        self.page_text: list[tuple[str, str]] = []
        starts = [m.start() for m in PAGE_RE.finditer(raw)]
        if not starts:
            raise ExtractionError("no page container found: unexpected file layout")
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else len(raw)
            chunk = raw[start:end]
            footer = FOOTER_RE.search(chunk)
            page = footer.group(1).strip() if footer else f"sheet {index + 1}"
            lines: list[str] = []
            position = 0
            for table in TABLE_RE.finditer(chunk):
                lines += self._add_text(chunk[position : table.start()], page)
                for row in ROW_RE.findall(table.group(0)):
                    cells = tuple(c for c in (clean(x) for x in CELL_RE.findall(row)) if c)
                    if cells:
                        self.items.append(Item("row", " | ".join(cells), cells, page))
                position = table.end()
            lines += self._add_text(chunk[position:], page)
            self.page_text.append((page, join_lines(lines)))

    def _add_text(self, segment: str, page: str) -> list[str]:
        segment = re.sub(r"(?is)<(script|style).*?</\1>", "", segment)
        segment = re.sub(r"(?i)</div>", "\n", segment)
        # The running header and the page number are not part of the text.
        furniture = {"", "Table of Contents", page}
        lines = [line for line in (clean(x) for x in segment.split("\n")) if line not in furniture]
        self.items.extend(Item("text", line, (), page) for line in lines)
        return lines

    @property
    def page_count(self) -> int:
        return len(self.page_text)

    def sentence(self, pattern: str) -> Hit:
        """First match of `pattern` in page order, with its sentence as the quote."""
        regex = re.compile(pattern)
        for page, text in self.page_text:
            match = regex.search(text)
            if match:
                return Hit(match, page, sentence_around(text, match.start(), match.end()))
        raise ExtractionError(f"pattern not found: {pattern}")

    def index_of(self, anchor: str, start: int = 0) -> int:
        """Index of the first item at or after `start` whose text matches `anchor`."""
        regex = re.compile(anchor)
        for index in range(start, len(self.items)):
            if regex.search(self.items[index].text):
                return index
        raise ExtractionError(f"anchor not found: {anchor}")

    def row_after(self, start: int, label: str, *, cell: int = 0, reach: int = 90) -> Item:
        """First table row within `reach` items after `start` whose cell matches `label`."""
        regex = re.compile(label)
        for item in self.items[start : start + reach]:
            if (
                item.kind == "row"
                and len(item.cells) > cell
                and regex.fullmatch(strip_footnotes(item.cells[cell]))
            ):
                return item
        raise ExtractionError(f"row not found after item {start}: {label}")


class Collector:
    """Builds the list of facts and refuses duplicates."""

    def __init__(self, filing: Filing) -> None:
        self.filing = filing
        self.facts: list[Fact] = []
        self._ids: set[str] = set()
        # The price the filing's "after the offering" figures use: the middle of the range in an
        # amendment, the IPO price in the final prospectus. Set by `_offering`.
        self.at_basis = ""
        self.assumed = True  # False in the final prospectus, whose figures use the IPO price
        self.price = ""  # that price as written, "$74.00"; "$83.00 (IPO price)" when final

    def add(
        self,
        fact_id: str,
        title: str,
        value: float | str,
        unit: Unit,
        as_filed: str,
        *,
        page: str,
        quote: str,
        section: str,
        period: str | None = None,
        scale: str | None = None,
        context: str | None = None,
    ) -> None:
        if fact_id in self._ids:
            raise ExtractionError(f"duplicate fact id: {fact_id}")
        self._ids.add(fact_id)
        self.facts.append(
            Fact(
                id=fact_id,
                title=title,
                label="FILED",
                value=value,
                unit=unit,
                as_filed=as_filed,
                scale=scale,
                period=period,
                section=section,
                page=page,
                quote=quote,
                context=context,
            )
        )

    # -- text facts ---------------------------------------------------------

    def billions(
        self,
        fact_id: str,
        title: str,
        hit: Hit,
        group: int,
        *,
        section: str,
        period: str | None = None,
    ) -> None:
        raw = hit.match.group(group)
        self.add(
            fact_id,
            title,
            round(float(raw) * BILLION),
            "USD",
            f"${raw} billion",
            page=hit.page,
            quote=hit.quote,
            section=section,
            period=period,
        )

    def millions(
        self,
        fact_id: str,
        title: str,
        hit: Hit,
        group: int,
        *,
        section: str,
        period: str | None = None,
    ) -> None:
        raw = hit.match.group(group)
        self.add(
            fact_id,
            title,
            round(float(raw.replace(",", "")) * MILLION),
            "USD",
            f"${raw} million",
            page=hit.page,
            quote=hit.quote,
            section=section,
            period=period,
        )

    def count(
        self,
        fact_id: str,
        title: str,
        hit: Hit,
        group: int,
        *,
        section: str,
        unit: Unit = "shares",
        period: str | None = None,
        suffix: str = "",
        prefix: str = "",
    ) -> None:
        raw = hit.match.group(group)
        self.add(
            fact_id,
            title,
            float(raw.replace(",", "")),
            unit,
            f"{prefix}{raw}{suffix}",
            page=hit.page,
            quote=hit.quote,
            section=section,
            period=period,
        )

    # -- table facts --------------------------------------------------------

    def table(
        self,
        prefix: str,
        *,
        anchor: str,
        header: str,
        header_cells: list[str],
        columns: list[tuple[str, str]],
        rows: list[tuple[str, str]],
        section: str,
    ) -> None:
        """Each (row, column) of a table in millions of dollars becomes one fact."""
        filing = self.filing
        start = filing.index_of(anchor)
        head = filing.row_after(start, header)
        found = [re.sub(r"\s+", "", strip_footnotes(c)) for c in head.cells[1:]]
        expected = [re.sub(r"\s+", "", c) for c in header_cells]
        if found != expected:
            raise ExtractionError(f"{prefix}: unexpected columns {head.cells[1:]}")
        for row_key, label in rows:
            row = filing.row_after(start, label)
            values = row.cells[1:]
            if len(values) != len(columns):
                raise ExtractionError(f"{prefix}.{row_key}: expected {len(columns)} values: {row}")
            for (column_key, period), cell in zip(columns, values, strict=True):
                self.add(
                    f"{prefix}.{row_key}.{column_key}",
                    strip_footnotes(row.cells[0]),
                    round(parse_number(cell) * MILLION),
                    "USD",
                    cell,
                    scale="in millions",
                    page=row.page,
                    quote=row.text,
                    context=head.text,
                    section=section,
                    period=period,
                )


STATEMENT_ROWS = [
    ("revenue", r"Revenue"),
    ("compute", r"Compute and infrastructure"),
    ("personnel", r"Personnel"),
    ("bartz", r"Bartz settlement"),
    ("sales", r"Sales, marketing, and partnerships"),
    ("other_opex", r"Other operating and administrative"),
    ("total_opex", r"Total operating expenses"),
    ("operating_income", r"Operating (loss|income \(loss\))"),
    ("interest_income", r"Interest income"),
    ("fv_change", r"Change in fair value of convertible notes, derivative liabilities, and SAFEs"),
    ("other_income", r"Other income \(expense\), net"),
    ("total_other", r"Total other income \(expense\), net"),
    ("pretax", r"Loss before provision for income taxes"),
    ("taxes", r"Provision for income taxes"),
    ("net_loss", r"Net loss"),
]

ANNUAL_COLUMNS = [
    ("fy2023", "Year ended Dec 31, 2023"),
    ("fy2024", "Year ended Dec 31, 2024"),
    ("fy2025", "Year ended Dec 31, 2025"),
    ("9m2025", "Nine months ended Sep 30, 2025"),
    ("9m2026", "Nine months ended Sep 30, 2026"),
]

QUARTER_COLUMNS = [
    ("2025q1", "Three months ended Mar 31, 2025"),
    ("2025q2", "Three months ended Jun 30, 2025"),
    ("2025q3", "Three months ended Sep 30, 2025"),
    ("2025q4", "Three months ended Dec 31, 2025"),
    ("2026q1", "Three months ended Mar 31, 2026"),
    ("2026q2", "Three months ended Jun 30, 2026"),
    ("2026q3", "Three months ended Sep 30, 2026"),
]

SEP30 = "As of Sep 30, 2026"


def extract(filing: Filing) -> list[Fact]:
    """All facts the dashboard needs, in a stable order."""
    c = Collector(filing)
    _offering(c)
    _shares(c)
    _balance(c)
    _statements(c)
    _metrics(c)
    _commitments(c)
    _structure(c)
    return c.facts


def _offering(c: Collector) -> None:
    f = c.filing
    # An amendment states when it was filed; the final prospectus states its own date.
    hit = f.sentence(
        r"(As filed with the Securities and Exchange Commission on|Prospectus dated) "
        r"(\w+ \d{1,2}, \d{4})"
    )
    final = hit.match.group(1) == "Prospectus dated"
    filed = datetime.strptime(hit.match.group(2), "%B %d, %Y").date().isoformat()
    c.add(
        "doc.filed_date",
        "Date of this prospectus" if final else "Date this amendment was filed",
        filed,
        "date",
        hit.match.group(2),
        page=hit.page,
        quote=hit.quote,
        section="Prospectus cover" if final else "Registration statement cover",
    )

    basis = f.sentence(
        r"(assumed initial public offering price|based upon the initial public offering price) "
        r"of \$(\d+\.\d{2}) per share"
    )
    price = basis.match.group(2)
    c.assumed = basis.match.group(1).startswith("assumed")
    c.price = f"${price}" if basis.match.group(1).startswith("assumed") else f"${price} (IPO price)"
    c.at_basis = (
        f"At the assumed ${price} price"
        if basis.match.group(1).startswith("assumed")
        else f"At the ${price} IPO price"
    )

    prospectus = "Prospectus cover"
    if final:
        # The final prospectus gives one price, no range.
        hit = f.sentence(r"The initial public offering price per share is \$(\d+\.\d{2})\.")
        raw = hit.match.group(1)
        c.add(
            "pricing.ipo_price",
            "Initial public offering price",
            float(raw),
            "USD/share",
            f"${raw}",
            page=hit.page,
            quote=hit.quote,
            section=prospectus,
        )
        prices: tuple[tuple[str, str, int], ...] = ()
    else:
        hit = f.sentence(
            r"initial public offering price per share will be between "
            r"\$(\d+\.\d{2}) and \$(\d+\.\d{2})"
        )
        prices = (
            ("offering.price_low", "IPO price range, low end", 1),
            ("offering.price_high", "IPO price range, high end", 2),
        )
    for fact_id, title, group in prices:
        raw = hit.match.group(group)
        c.add(
            fact_id,
            title,
            float(raw),
            "USD/share",
            f"${raw}",
            page=hit.page,
            quote=hit.quote,
            section=prospectus,
        )
    # Amendment No. 2: "We have applied to list"; No. 3: "We have been approved to list".
    hit = f.sentence(
        r"We have (applied|been approved) to list our Class A common stock on the "
        r"(Nasdaq Global Select Market) under the symbol “?(\w+)\.?”?"
    )
    c.add(
        "offering.listing",
        "Listing on the exchange",
        "approved" if hit.match.group(1) == "been approved" else "applied for",
        "text",
        f"have {hit.match.group(1)} to list",
        page=hit.page,
        quote=hit.quote,
        section=prospectus,
    )
    c.add(
        "offering.exchange",
        "Exchange",
        hit.match.group(2),
        "text",
        hit.match.group(2),
        page=hit.page,
        quote=hit.quote,
        section=prospectus,
    )
    c.add(
        "offering.symbol",
        "Proposed trading symbol",
        hit.match.group(3),
        "text",
        hit.match.group(3),
        page=hit.page,
        quote=hit.quote,
        section=prospectus,
    )

    section = "Prospectus Summary — The Offering"
    start = f.index_of(r"^The Offering$")
    simple = [
        (
            "offering.shares_company",
            "Shares sold by the company",
            r"Class A common stock offered by us",
        ),
        (
            "offering.shares_selling",
            "Shares sold by existing stockholders",
            r"Class A common stock offered by the selling stockholders",
        ),
        (
            "offering.greenshoe",
            "Extra shares the underwriters may buy",
            r"Underwriters’ option to purchase additional shares of Class A common stock from us",
        ),
    ]
    for fact_id, title, label in simple:
        row = f.row_after(start, label)
        raw = _first(r"([\d,]+) shares", row.cells[1])
        c.add(
            fact_id,
            title,
            float(raw.replace(",", "")),
            "shares",
            f"{raw} shares",
            page=row.page,
            quote=row.text,
            section=section,
        )

    after = (
        " common stock to be outstanding after this offering and the concurrent private placement"
    )
    at_mid = "After the offering, " + c.at_basis[0].lower() + c.at_basis[1:]
    outstanding = [
        ("shares.class_a_after", "Class A shares outstanding after the offering", "Class A"),
        ("shares.class_n_after", "Class N shares outstanding after the offering", "Class N"),
        (
            "shares.total_after",
            "All shares outstanding after the offering",
            "Class A, Class N, Class T, Class E, and Class F",
        ),
    ]
    for fact_id, title, classes in outstanding:
        row = f.row_after(start, re.escape(classes + after))
        cell = row.cells[1]
        raw = _first(r"^([\d,]+) shares", cell)
        c.add(
            fact_id,
            title,
            float(raw.replace(",", "")),
            "shares",
            f"{raw} shares",
            page=row.page,
            quote=_clip(row.text),
            section=section,
            period=at_mid,
        )
        if fact_id == "shares.total_after":
            raw = _first(r"\(or ([\d,]+) shares if the underwriters exercise", cell)
            c.add(
                "shares.total_after_greenshoe",
                "All shares outstanding if the underwriters buy their extra shares",
                float(raw.replace(",", "")),
                "shares",
                f"{raw} shares",
                page=row.page,
                quote=_clip(row.text),
                section=section,
                period=at_mid,
            )

    row = f.row_after(start, r"Class N common stock sold in the concurrent private placement")
    cell = row.cells[1]
    m = _search(r"an aggregate of \$([\d.]+) billion of our Class N common stock", cell)
    c.add(
        "offering.private_placement",
        "Private placement alongside the IPO",
        round(float(m.group(1)) * BILLION),
        "USD",
        f"${m.group(1)} billion",
        page=row.page,
        quote=sentence_around(cell, m.start(), m.end()),
        section=section,
    )

    row = f.row_after(start, r"Use of proceeds")
    cell = row.cells[1]
    m = _search(r"will be approximately \$([\d.]+) billion", cell)
    quote = sentence_around(cell, m.start(), m.end())
    c.add(
        "offering.net_proceeds_mid",
        "Net proceeds to the company (IPO and private placement)",
        round(float(m.group(1)) * BILLION),
        "USD",
        f"${m.group(1)} billion",
        page=row.page,
        quote=quote,
        section=section,
        period=c.at_basis,
    )
    m = _search(
        r"(?:assumed initial public offering price|based upon the initial public offering price)"
        r" of \$(\d+\.\d{2}) per share",
        cell,
    )
    c.add(
        "offering.price_mid",
        "Assumed IPO price (midpoint of the range)"
        if c.assumed
        else "IPO price the filing's figures use",
        float(m.group(1)),
        "USD/share",
        f"${m.group(1)}",
        page=row.page,
        quote=quote,
        section=section,
    )


def _shares(c: Collector) -> None:
    f = c.filing
    section = "Prospectus Summary — The Offering (shares not counted as outstanding)"
    a = "shares of our Class A common stock"
    n = "shares of our Class N common stock"

    hit = f.sentence(
        rf"([\d,]+) {a} issuable upon the exercise of options to purchase {a} outstanding "
        r"as of September 30, 2026, with a weighted-average exercise price of \$([\d.]+) per share"
    )
    c.count(
        "shares.options",
        "Shares issuable on exercise of stock options",
        hit,
        1,
        section=section,
        period=SEP30,
        suffix=" shares",
    )
    c.add(
        "shares.options_exercise_price",
        "Average exercise price of the stock options",
        float(hit.match.group(2)),
        "USD/share",
        f"${hit.match.group(2)}",
        page=hit.page,
        quote=hit.quote,
        section=section,
        period=SEP30,
    )
    hit = f.sentence(
        rf"([\d,]+) {a} issuable upon the vesting and settlement of RSUs outstanding "
        r"as of September 30, 2026, but for which"
    )
    c.count(
        "shares.rsus_unvested",
        "Shares issuable when outstanding RSUs vest",
        hit,
        1,
        section=section,
        period=SEP30,
        suffix=" shares",
    )
    hit = f.sentence(
        rf"([\d,]+) {a} issuable upon the vesting and settlement of RSUs granted after "
        r"September 30, 2026"
    )
    c.count(
        "shares.rsus_granted_after",
        "Shares issuable for RSUs granted after Sep 30, 2026",
        hit,
        1,
        section=section,
        suffix=" shares",
    )
    hit = f.sentence(
        rf"([\d,]+) {a} and ([\d,]+) {n} issued after September 30, 2026 in connection with "
        r"our acquisitions"
    )
    c.count(
        "shares.acquisitions_class_a",
        "Class A shares issued for acquisitions after Sep 30, 2026",
        hit,
        1,
        section=section,
        suffix=" shares",
    )
    c.count(
        "shares.acquisitions_class_n",
        "Class N shares issued for acquisitions after Sep 30, 2026",
        hit,
        2,
        section=section,
        suffix=" shares",
    )
    # Amendment No. 2: "...2026 Plan ..., and include: (i) N shares of our Class A common stock;
    # Amendment No. 3: "N shares of our Class A common stock to be reserved ... under our 2026
    # Equity Incentive Plan ..., plus up to ...". The final prospectus drops "to be".
    try:
        hit = f.sentence(rf"include: \(i\) ([\d,]+) {a}; \(ii\)")
    except ExtractionError:
        hit = f.sentence(
            rf"([\d,]+) {a} (?:to be )?reserved for future issuance under our 2026 Equity "
            r"Incentive Plan"
        )
    c.count(
        "shares.plan_2026_reserve",
        "Shares reserved for future grants (2026 Equity Incentive Plan)",
        hit,
        1,
        section=section,
        suffix=" shares",
    )
    hit = f.sentence(
        rf"([\d,]+) {a} (?:to be )?reserved for future issuance under our 2026 Employee Stock "
        r"Purchase Plan"
    )
    c.count(
        "shares.espp_reserve",
        "Shares reserved for the employee stock purchase plan",
        hit,
        1,
        section=section,
        suffix=" shares",
    )
    hit = f.sentence(rf"([\d,]+) {n} reserved for future issuance under our Donation Matching Plan")
    c.count(
        "shares.donation_reserve",
        "Shares reserved for the donation matching plan",
        hit,
        1,
        section=section,
        period=SEP30,
        suffix=" shares",
    )
    hit = f.sentence(
        rf"([\d,]+) {n} that were issued after September 30, 2026 to match employee donations"
    )
    c.count(
        "shares.matching_issuance",
        "Shares issued after Sep 30, 2026 to match employee donations",
        hit,
        1,
        section=section,
        suffix=" shares",
    )
    hit = f.sentence(
        r"withholding of ([\d,]+) shares of Class A common stock subject to such RSUs "
        r"to satisfy the associated estimated tax withholding"
    )
    c.count(
        "shares.rsu_tax_withheld",
        "RSU shares withheld to pay employee taxes at the offering",
        hit,
        1,
        section=section,
        period=c.at_basis,
        suffix=" shares",
    )

    notes = "Convertible notes held by Amazon"
    hit = f.sentence(
        r"the conversion of \$([\d.]+) million in aggregate principal amount of our outstanding "
        r"convertible promissory notes into ([\d,]+) shares of Class N common stock"
    )
    c.count(
        "notes.shares_converted_at_ipo",
        "Shares issued to Amazon when its notes convert at the offering",
        hit,
        2,
        section=notes,
        suffix=" shares",
    )
    hit = f.sentence(
        r"An aggregate of an additional ([\d,]+) shares of Class N common stock will be issuable "
        r"after this offering upon conversion of remaining outstanding convertible promissory notes"
    )
    c.count(
        "notes.shares_remaining",
        "Shares still owed to Amazon on its remaining convertible notes",
        hit,
        1,
        section=notes,
        suffix=" shares",
    )

    start = f.index_of(r"^Counterparty \| Agreement \| Principal Amount Outstanding")
    head = f.items[start]
    total = f.row_after(start, r"Total")
    if len(total.cells) != 3:
        raise ExtractionError(f"unexpected notes total row: {total}")
    c.add(
        "notes.principal",
        "Principal of the Amazon convertible notes",
        round(parse_number(total.cells[1]) * MILLION),
        "USD",
        total.cells[1],
        scale="in millions",
        page=total.page,
        quote=total.text,
        context=head.text,
        section=notes,
        period=SEP30,
    )
    c.add(
        "notes.shares_issuable_total",
        "Shares issuable on full conversion of the Amazon notes",
        parse_number(total.cells[2]),
        "shares",
        f"{total.cells[2]} shares",
        page=total.page,
        quote=total.text,
        context=head.text,
        section=notes,
        period=SEP30,
    )

    hit = f.sentence(
        r"sale and issuance by us of ([\d,]+) shares of our Class N common stock in the "
        r"concurrent private placement"
    )
    c.count(
        "offering.private_placement_shares_mid",
        "Shares sold in the private placement",
        hit,
        1,
        section="Summary consolidated financial data — notes",
        period=c.at_basis,
        suffix=" shares",
    )


def _balance(c: Collector) -> None:
    f = c.filing
    columns = [
        ("actual", "As of Sep 30, 2026, actual"),
        ("pro_forma", "As of Sep 30, 2026, pro forma"),
        ("as_adjusted", f"As of Sep 30, 2026, pro forma as adjusted for the offering at {c.price}"),
    ]
    c.table(
        "balance",
        anchor=r"^Consolidated Balance Sheet Data$",
        header=r"\(in millions\)",
        header_cells=["Actual", "Pro Forma", "Pro Forma As Adjusted"],
        columns=columns,
        rows=[
            ("cash", r"Cash, cash equivalents, and short-term investments"),
            ("total_liabilities", r"Total liabilities"),
            ("accumulated_deficit", r"Accumulated deficit"),
        ],
        section="Summary consolidated financial data — balance sheet",
    )
    c.table(
        "capitalization",
        anchor=r"^Capitalization$",
        header=r"Actual",
        header_cells=["ProForma", "ProForma AsAdjusted"],
        columns=columns,
        rows=[("convertible_notes", r"Convertible notes payable")],
        section="Capitalization",
    )

    if c.assumed:  # the final prospectus has one price: no "each $1.00 increase" sentence
        hit = f.sentence(
            r"Each \$1\.00 increase or decrease in the assumed initial public offering price "
            r"would increase or decrease each of cash, cash equivalents, and short-term "
            r"investments; [^.]*? by \$(\d+) million"
        )
        c.millions(
            "balance.cash_sensitivity_per_dollar",
            "Change in post-offering cash for each $1.00 of IPO price",
            hit,
            1,
            section="Summary consolidated financial data — notes",
        )
    hit = f.sentence(
        r"raised an aggregate of \$([\d.]+) billion of capital and had cash and cash equivalents "
        r"of \$([\d.]+) billion and short-term investments of \$([\d.]+) billion"
    )
    section = "Prospectus Summary"
    c.billions(
        "balance.capital_raised", "Capital raised to date", hit, 1, section=section, period=SEP30
    )
    c.billions(
        "balance.cash_equivalents",
        "Cash and cash equivalents",
        hit,
        2,
        section=section,
        period=SEP30,
    )
    c.billions(
        "balance.short_term_investments",
        "Short-term investments",
        hit,
        3,
        section=section,
        period=SEP30,
    )

    hit = f.sentence(r"we had (no borrowings drawn) under the A&R Credit Facility")
    c.add(
        "debt.credit_facility_drawn",
        "Borrowings drawn under the credit facility",
        0,
        "USD",
        hit.match.group(1),
        page=hit.page,
        quote=hit.quote,
        section="Liquidity and Capital Resources — Credit facility",
        period=SEP30,
    )
    hit = f.sentence(
        r"accumulated deficit of \$([\d.]+) billion, which includes \$([\d.]+) billion related to "
        r"changes in the fair value of our convertible notes driven by increases in our "
        r"enterprise valuation and derivative liabilities since 2023, including \$([\d.]+) "
        r"billion during the nine months ended September 30, 2026"
    )
    section = "Liquidity and Capital Resources"
    c.billions("deficit.accumulated", "Accumulated deficit", hit, 1, section=section, period=SEP30)
    c.billions(
        "deficit.fair_value_part",
        "Part of the accumulated deficit due to fair-value changes",
        hit,
        2,
        section=section,
        period="Since 2023",
    )
    c.billions(
        "deficit.fair_value_9m2026",
        "Fair-value changes in the first nine months of 2026",
        hit,
        3,
        section=section,
        period="Nine months ended Sep 30, 2026",
    )


def _statements(c: Collector) -> None:
    c.table(
        "is",
        anchor=r"^Consolidated Statements of Operations Data$",
        header=r"\(in millions, except share and per share amounts\)",
        header_cells=["2023", "2024", "2025", "2025", "2026"],
        columns=ANNUAL_COLUMNS,
        rows=STATEMENT_ROWS,
        section="Summary consolidated financial data — statements of operations",
    )
    c.table(
        "q",
        anchor=r"^Quarterly Consolidated Statements of Operations$",
        header=r"\(in millions\)",
        header_cells=[
            "March 31,2025",
            "June 30,2025",
            "September 30,2025",
            "December 31,2025",
            "March 31,2026",
            "June 30,2026",
            "September 30,2026",
        ],
        columns=QUARTER_COLUMNS,
        rows=STATEMENT_ROWS,
        section="Quarterly Results of Operations",
    )


def _metrics(c: Collector) -> None:
    f = c.filing
    section = "Prospectus Summary"
    hit = f.sentence(
        r"revenue that grew ([\d,]+)% year over year for the three months ended September 30, "
        r"2026, compared to compute and infrastructure expenses that grew (\d+)%"
    )
    period = "Three months ended Sep 30, 2026 vs 2025"
    c.count(
        "metrics.revenue_growth_q3",
        "Revenue growth, year over year",
        hit,
        1,
        section=section,
        unit="percent",
        period=period,
        suffix="%",
    )
    c.count(
        "metrics.compute_growth_q3",
        "Growth of compute and infrastructure expenses, year over year",
        hit,
        2,
        section=section,
        unit="percent",
        period=period,
        suffix="%",
    )
    hit = f.sentence(r"Net Revenue Retention of approximately (\d+)% as of September 30, 2026")
    c.count(
        "metrics.net_revenue_retention",
        "Net Revenue Retention",
        hit,
        1,
        section=section,
        unit="percent",
        period=SEP30,
        suffix="%",
        prefix="approximately ",
    )

    section = "Business"
    hit = f.sentence(
        r"customers with \$100,000 or more of revenue on a TTM basis from more than ([\d,]+) "
        r"to more than ([\d,]+)"
    )
    title = "Customers with $100,000 or more of trailing-twelve-month revenue"
    c.count(
        "metrics.customers_100k_2025",
        title,
        hit,
        1,
        section=section,
        unit="count",
        period="As of Sep 30, 2025",
        prefix="more than ",
    )
    c.count(
        "metrics.customers_100k_2026",
        title,
        hit,
        2,
        section=section,
        unit="count",
        period=SEP30,
        prefix="more than ",
    )
    hit = f.sentence(
        r"Run-Rate Revenue was approximately \$(\d+) billion as of October 31, 2026, "
        r"up \$(\d+) billion from September 30, 2026"
    )
    c.billions(
        "metrics.run_rate_oct31",
        "Run-Rate Revenue",
        hit,
        1,
        section=section,
        period="As of Oct 31, 2026",
    )
    c.billions(
        "metrics.run_rate_increase_oct",
        "Increase in Run-Rate Revenue during October 2026",
        hit,
        2,
        section=section,
        period="Sep 30 to Oct 31, 2026",
    )

    section = "Notes to consolidated financial statements — Revenue"
    hit = f.sentence(r"remaining performance obligations amounted to \$([\d.]+) billion")
    c.billions(
        "rpo.total",
        "Remaining performance obligations (signed customer contracts)",
        hit,
        1,
        section=section,
        period=SEP30,
    )
    hit = f.sentence(
        r"expects to recognize approximately (\d+)% \(unaudited\) of this amount as revenue "
        r"over the next 12 months"
    )
    c.count(
        "rpo.share_next_12m",
        "Share of signed customer contracts recognised within 12 months",
        hit,
        1,
        section=section,
        unit="percent",
        period=SEP30,
        suffix="%",
        prefix="approximately ",
    )


def _commitments(c: Collector) -> None:
    f = c.filing
    section = "Prospectus Summary"
    period = "As of and subsequent to Sep 30, 2026"
    hit = f.sentence(r"aggregate committed spend of approximately \$([\d.]+) billion")
    c.billions(
        "commit.total",
        "Total committed spend (compute and infrastructure)",
        hit,
        1,
        section=section,
        period=period,
    )
    hit = f.sentence(
        r"approximately \$([\d.]+) billion expected to be incurred before December 31, 2030"
    )
    c.billions(
        "commit.before_2031",
        "Committed spend expected before Dec 31, 2030",
        hit,
        1,
        section=section,
        period=period,
    )
    hit = f.sentence(
        r"Approximately \$([\d.]+) billion of these commitments are due in the 12 months "
        r"following September 30, 2026"
    )
    c.billions(
        "commit.next_12m",
        "Committed spend due in the next 12 months",
        hit,
        1,
        section=section,
        period="Oct 2026 to Sep 2027",
    )

    section = "Liquidity and Capital Resources — Contractual Obligations"
    hit = f.sentence(
        r"Approximately \$([\d.]+) billion of the aggregate total of our contractual obligations "
        r"relates to arrangements that are subject to either exercisable termination rights or "
        r"contingent conditions"
    )
    c.billions(
        "commit.conditional",
        "Commitments that can still be terminated or depend on conditions",
        hit,
        1,
        section=section,
        period=period,
    )
    hit = f.sentence(
        r"Minimum payments under such contracts were approximately \$([\d.]+) billion "
        r"as of September 30, 2026"
    )
    c.billions(
        "commit.short_term",
        "Short-term commitments not in the obligations table",
        hit,
        1,
        section=section,
        period=SEP30,
    )
    hit = f.sentence(
        r"total estimated future undiscounted lease obligations of approximately "
        r"\$([\d.]+) billion"
    )
    c.billions(
        "commit.leases_not_commenced",
        "Leases signed but not yet started",
        hit,
        1,
        section=section,
        period=SEP30,
    )
    hit = f.sentence(
        r"commitments entered into after September 30, 2026, with aggregate future minimum "
        r"payment obligations of approximately \$([\d.]+) billion"
    )
    c.billions(
        "commit.after_sep30",
        "Commitments signed after Sep 30, 2026",
        hit,
        1,
        section=section,
        period="After Sep 30, 2026",
    )
    hit = f.sentence(
        r"short[- ]term in nature\. Minimum payments under such contracts are approximately "
        r"\$([\d.]+) billion"
    )
    c.billions(
        "commit.after_sep30_short_term",
        "Short-term commitments signed after Sep 30, 2026",
        hit,
        1,
        section=section,
        period="After Sep 30, 2026",
    )

    c.table(
        "obligations",
        anchor=r"^The following table summarizes our contractual obligations as of",
        header=r"\(in millions\)",
        header_cells=["Total", "2026", "2027", "2028", "2029", "2030", "Thereafter"],
        columns=[
            ("total", "Total, as of Sep 30, 2026"),
            ("2026", "Due in 2026 (from Oct 1)"),
            ("2027", "Due in 2027"),
            ("2028", "Due in 2028"),
            ("2029", "Due in 2029"),
            ("2030", "Due in 2030"),
            ("thereafter", "Due after 2030"),
        ],
        rows=[
            ("operating_leases", r"Operating leases"),
            ("finance_leases", r"Finance leases"),
            ("purchase_commitments", r"Purchase commitments"),
            ("total", r"Total"),
        ],
        section=section,
    )


UNLOCK_SHARES_RE = re.compile(r"^Up to ([\d.]+) (million|billion) shares of Class A common stock")
# Amendment No. 3 splits each step into Class A, Class N and their total: the page draws the total.
UNLOCK_TOTAL_RE = re.compile(
    r"^Up to ([\d.]+) (million|billion) shares of Class A and Class N common stock"
)


def _structure(c: Collector) -> None:
    """Who gets the offered shares, when existing shares may be sold, who controls the company."""
    f = c.filing

    # The underwriters and the total they take. Their allocation is blank before pricing.
    section = "Underwriting"
    start = f.index_of(r"^Underwriters \| Number of Shares of Class A Common Stock$")
    names: list[str] = []
    allocated: list[str] = []  # the final prospectus fills in each bank's number of shares
    for item in f.items[start + 1 : start + 60]:
        if item.kind != "row":
            break
        if item.cells[0] == "Total":
            raw = _first(r"^([\d,]+)$", item.cells[1])
            c.add(
                "underwriting.total",
                "Shares the underwriters take, all banks together",
                float(raw.replace(",", "")),
                "shares",
                f"{raw} shares",
                page=item.page,
                quote=item.text,
                section=section,
            )
            break
        if item.cells[0] in ("Bookrunners", "Co-managers") and not c.assumed:
            continue  # the final prospectus groups the banks under these two headings
        if len(item.cells) == 2 and not c.assumed:
            allocated.append(_first(r"^([\d,]+)$", item.cells[1]))
        elif len(item.cells) != 1:
            raise ExtractionError(f"underwriter row with an allocation: {item.text}")
        names.append(item.cells[0])
    else:
        raise ExtractionError("underwriting table: no total row")
    if len(names) < 10:
        raise ExtractionError(f"underwriting table: only {len(names)} names")
    if allocated:
        if len(allocated) != len(names):
            raise ExtractionError("underwriting table: some banks have no number of shares")
        shares = sum(float(a.replace(",", "")) for a in allocated)
        if shares != c.facts[-1].value:
            raise ExtractionError(f"underwriting table: {shares:,.0f} shares, not the total")
    c.add(
        "underwriting.banks",
        "Underwriters named in the filing",
        "; ".join(names),
        "text",
        "; ".join(names),
        page=f.items[start].page,
        quote=(
            "Underwriters: "
            + "; ".join(f"{n} ({a} shares)" for n, a in zip(names, allocated, strict=True))
            + "."
            if allocated
            else f"Underwriters: {'; '.join(names)}. Their number of shares is left blank."
        ),
        section=section,
    )

    # Who holds the shares after the offering.
    section = "Dilution"
    hit = f.sentence(
        r"by existing stockholders to be reduced to ([\d,]+) shares, or approximately "
        r"([\d.]+)% of the total"
    )
    c.count(
        "holders.existing_after",
        "Shares held by existing stockholders after the IPO",
        hit,
        1,
        section=section,
        suffix=" shares",
    )
    c.count(
        "holders.existing_after_pct",
        "Share of all shares held by existing stockholders",
        hit,
        2,
        section=section,
        unit="percent",
        suffix="%",
    )
    hit = f.sentence(
        r"increase the number of shares held by new investors to ([\d,]+) shares, or "
        r"approximately ([\d.]+)%"
    )
    c.count(
        "holders.new_after",
        "Shares held by new investors after the IPO",
        hit,
        1,
        section=section,
        suffix=" shares",
    )
    c.count(
        "holders.new_after_pct",
        "Share of all shares held by new investors",
        hit,
        2,
        section=section,
        unit="percent",
        suffix="%",
    )

    # The private placement's buyers, and the insiders who may buy in the IPO.
    section = "Underwriting — Concurrent Private Placement"
    hit = f.sentence(r"Each of (Google LLC, [^.]*?) has entered into an agreement with us")
    c.add(
        "placement.buyers",
        "Buyers of the private placement",
        hit.match.group(1),
        "text",
        hit.match.group(1),
        page=hit.page,
        quote=hit.quote,
        section=section,
    )
    hit = f.sentence(
        r"Certain members of our board of directors and entities affiliated or associated with "
        r"them have indicated an interest in purchasing shares of our Class A common stock in "
        r"this offering at the initial public offering price at an aggregate purchase price of "
        r"up to \$([\d,]+) million"
    )
    c.millions(
        "offering.insider_interest",
        "Insiders' indicated interest in buying IPO shares (not binding)",
        hit,
        1,
        section="Prospectus cover",
    )

    # Who controls the company.
    section = "Description of Capital Stock"
    hit = f.sentence(
        r"Each share of Class A common stock is entitled to (one) vote and shares of "
        r"Class N common stock have (no voting rights)"
    )
    c.add(
        "control.class_a",
        "Votes per Class A share",
        1.0,
        "count",
        hit.match.group(1),
        page=hit.page,
        quote=hit.quote,
        section=section,
    )
    c.add(
        "control.class_n",
        "Votes of Class N shares",
        hit.match.group(2),
        "text",
        hit.match.group(2),
        page=hit.page,
        quote=hit.quote,
        section=section,
    )
    hit = f.sentence(
        r"Class F common stock, which will be held by the Founder LLC, will be entitled "
        r"to an aggregate number of votes that equals ([\d.]+)% of the total voting"
    )
    c.count(
        "control.class_f_pct",
        "Voting power of the single Class F share (co-founders)",
        hit,
        1,
        section=section,
        unit="percent",
        suffix="%",
    )
    hit = f.sentence(
        r"the voting power of the holders of Class A common stock is limited to an "
        r"aggregate of ([\d.]+)% of the total outstanding voting power"
    )
    c.count(
        "control.class_a_pct",
        "Voting power of all Class A shares together",
        hit,
        1,
        section=section,
        unit="percent",
        suffix="%",
    )
    hit = f.sentence(
        r"the LTBT generally has the authority to elect and remove the Class T "
        r"directors, who together will constitute (a majority) of the authorized"
    )
    c.add(
        "control.class_t",
        "Board seats elected by the Long-Term Benefit Trust (Class T)",
        hit.match.group(1),
        "text",
        hit.match.group(1),
        page=hit.page,
        quote=hit.quote,
        section=section,
    )
    hit = f.sentence(
        r"Our Class E common stock will be entitled to vote (only on certain limited "
        r"matters)"
    )
    c.add(
        "control.class_e",
        "Votes of Class E shares (employees)",
        hit.match.group(1),
        "text",
        hit.match.group(1),
        page=hit.page,
        quote=hit.quote,
        section=section,
    )

    # When existing shares may be sold: the filing's table, step by step.
    section = "Shares Eligible for Future Sale"
    start = f.index_of(
        r"^Earliest Date Available for Sale in the Public Market \| "
        r"(?:Approximate Number of Shares|Shares of Class A Common Stock \| Shares of Class N)"
    )
    context = (
        "As the filing words it: shares that become available for sale at each step, "
        "subject to the lock-up and market standoff agreements, Rules 144 and 701 and the "
        'insider trading policy. The filing gives each step as a maximum ("up to").'
    )
    step = 0
    for item in f.items[start + 1 : start + 60]:
        if item.kind == "text" and item.text.startswith("____"):
            break
        if item.kind != "row" or item.cells[0].startswith("Earliest Date Available"):
            continue
        if len(item.cells) == 2:  # Amendment No. 2: one column, Class A
            found = UNLOCK_SHARES_RE.match(item.cells[1])
        elif len(item.cells) == 4:  # Amendment No. 3: Class A, Class N, total
            found = UNLOCK_TOTAL_RE.match(item.cells[3])
        else:
            raise ExtractionError(f"unlock row not understood: {item.text}")
        if found is None:
            raise ExtractionError(f"unlock shares not understood: {item.text}")
        step += 1
        number, scale = found.group(1), found.group(2)
        key = f"unlock.{step:02d}"
        c.add(
            key,
            f"Shares that may be sold at step {step}",
            round(float(number) * (MILLION if scale == "million" else BILLION)),
            "shares",
            f"up to {number} {scale}",
            page=item.page,
            quote=item.text,
            section=section,
            context=context,
        )
        c.add(
            f"{key}.when",
            f"When step {step} comes",
            strip_footnotes(item.cells[0]),
            "text",
            strip_footnotes(item.cells[0]),
            page=item.page,
            quote=item.text,
            section=section,
        )
    if step < 10:
        raise ExtractionError(f"unlock table: only {step} steps")


def _search(pattern: str, text: str) -> re.Match[str]:
    match = re.search(pattern, text)
    if match is None:
        raise ExtractionError(f"pattern not found in cell: {pattern}")
    return match


def _first(pattern: str, text: str) -> str:
    return _search(pattern, text).group(1)


def _clip(text: str) -> str:
    return text if len(text) <= MAX_QUOTE else text[:MAX_QUOTE].rstrip() + " …"


def build(path: Path, *, document_id: str) -> FactFile:
    """Read a saved filing and return its fact file."""
    data = path.read_bytes()
    raw = data.decode("cp1252", errors="replace")
    saved_from = SAVED_FROM_RE.search(raw[:2000])
    if saved_from is None:
        raise ExtractionError("the file does not say which sec.gov address it was saved from")
    url = saved_from.group(1)
    accession_digits = url.rstrip("/").split("/")[-2]
    accession = f"{accession_digits[:10]}-{accession_digits[10:12]}-{accession_digits[12:]}"
    filing = Filing(raw)
    facts = extract(filing)
    filed = next(str(f.value) for f in facts if f.id == "doc.filed_date")
    # The cover says which amendment this is: "AMENDMENT NO. 3 TO FORM S-1", or that it is the
    # final prospectus: "Filed Pursuant to Rule 424(b)(4)".
    cover = filing.page_text[0][1]
    amendment = re.search(r"AMENDMENT NO\. (\d+) TO FORM S-1", cover)
    if amendment is not None:
        form, title = "S-1/A", f"Form S-1/A, Amendment No. {amendment[1]}"
    elif re.match(r"Filed Pursuant to Rule 424\(b\)\(4\)", cover):
        form, title = "424B4", "Form 424B4, final prospectus"
    else:
        raise ExtractionError("the cover does not say which amendment this is")
    document = Document(
        id=document_id,
        company="Anthropic, PBC",
        form=form,
        title=title,
        accession=accession,
        filed=filed,
        url=url,
        source_sha256=hashlib.sha256(data).hexdigest(),
    )
    return FactFile(document=document, facts=facts)


def render(file: FactFile) -> str:
    """Stable JSON, so that a re-run on the same input gives the same file."""
    return json.dumps(file.model_dump(exclude_none=True), indent=1, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="saved filing (HTML from sec.gov)")
    parser.add_argument("--id", default="s1a2", help="document id (default: s1a2)")
    parser.add_argument("--out", type=Path, default=None, help="output JSON file")
    args = parser.parse_args()
    out: Path = args.out or Path("data/facts") / f"{args.id}.json"
    file = build(args.source, document_id=args.id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(file), encoding="utf-8")
    print(f"{len(file.facts)} facts written to {out}")


if __name__ == "__main__":
    main()
