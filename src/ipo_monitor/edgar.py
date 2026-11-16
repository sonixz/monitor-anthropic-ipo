"""The SEC's filing index (EDGAR): what the company has filed, and the final IPO price.

The service asks EDGAR for the list of the registrant's filings on a timer. When a final
prospectus appears, it reads the offering price from the cover, under checks strict enough
that a misread cannot pass. Whatever fails here leaves the page as it was.

The SEC asks automated clients to say who they are. The User-Agent carries the contact address
given in SEC_CONTACT; it is sent to sec.gov hosts only and is never logged. Without an address
nothing is asked.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, Protocol

from ipo_monitor import log
from ipo_monitor.facts import Document, Fact

State = Literal["ok", "unavailable"]
HOSTS = ("data.sec.gov", "www.sec.gov")
CLIENT = "ANT IPO Monitor"  # the name the SEC sees, followed by the contact address
EVERY = 600  # seconds between two questions; the SEC allows far more
LONGEST_WAIT = 3600
SHOWN = 8  # lines of filings listed on the page
COVER_BYTES = 1_000_000  # the cover is at the top of the document; the rest is not read
FINAL_PROSPECTUS = ("424B4", "424B1")
PROSPECTUS_FORMS = ("S-1", "S-1/A", *FINAL_PROSPECTUS)
PRICED = "pricing.ipo_price"

# What a form is, in plain words. A form that is not here is shown by its name alone.
FORMS = {
    "DRS": "draft registration statement",
    "DRS/A": "amended draft registration statement",
    "S-1": "registration statement, the first public prospectus",
    "S-1/A": "amended registration statement",
    "S-1MEF": "registration of additional shares",
    "FWP": "free writing prospectus, extra material for investors",
    "8-A12B": "registration of the shares for listing on an exchange",
    "CERT": "the exchange certifies the listing",
    "CERTNAS": "Nasdaq certifies the listing",
    "CERTNYS": "the New York Stock Exchange certifies the listing",
    "EFFECT": "the SEC declares the registration effective",
    "424B1": "final prospectus",
    "424B4": "final prospectus, with the final price",
    "S-8": "registration of shares for employee plans",
    "3": "an insider's first statement of ownership",
    "4": "a change in an insider's holdings",
    "8-K": "current report on a material event",
    "10-Q": "quarterly report",
    "10-K": "annual report",
    "CORRESP": "letter from the company to the SEC",
    "UPLOAD": "letter from the SEC to the company",
}


# What is not a numbered form is named for what it is.
NAMES = {
    "EFFECT": "Notice of effectiveness",
    "CERT": "Listing certificate",
    "CERTNAS": "Listing certificate",
    "CERTNYS": "Listing certificate",
    "CORRESP": "Letter",
    "UPLOAD": "Letter",
}


class SourceError(Exception):
    """EDGAR could not be read, or what it gave is not what was expected."""


@dataclass(frozen=True)
class Filing:
    """One filing of the registrant, as the index lists it."""

    accession: str  # 0001628280-26-072484
    form: str
    filed: str  # 2026-11-10
    url: str  # the main document on sec.gov, or the folder of the filing

    @property
    def name(self) -> str:
        return NAMES.get(self.form, f"Form {self.form}")

    @property
    def meaning(self) -> str:
        return FORMS.get(self.form, "")


@dataclass(frozen=True)
class Batch:
    """Filings of one form made on one day: one line on the page."""

    first: Filing
    others: tuple[Filing, ...] = ()


def batches(filings: tuple[Filing, ...], limit: int = SHOWN) -> tuple[Batch, ...]:
    """The newest filings, those of the same form and day together, as `limit` lines at most."""
    lines: list[Batch] = []
    for filing in filings:
        last = lines[-1].first if lines else None
        if last is not None and (last.form, last.filed) == (filing.form, filing.filed):
            lines[-1] = Batch(last, (*lines[-1].others, filing))
        elif len(lines) < limit:
            lines.append(Batch(filing))
        else:
            break
    return tuple(lines)


@dataclass(frozen=True)
class Price:
    """The offering price read from the cover of a final prospectus."""

    value: float
    total: float
    shares: int
    quote: str
    filing: Filing
    sha256: str  # of the part of the document that was read


@dataclass(frozen=True)
class Watch:
    """What the service knows about the filings after one check."""

    state: State
    checked: int
    filings: tuple[Filing, ...] = ()  # newest first; kept while EDGAR fails
    source: str = ""
    detail: str = ""
    prospectus: Filing | None = None  # a final prospectus, once one is filed
    cover_read: bool = False  # its cover was downloaded and judged: not asked for again
    price: Price | None = None
    price_problem: str = ""  # why the price of that prospectus was not taken

    @property
    def shown(self) -> tuple[Any, ...]:
        """What the page displays. The page is rendered again only when this changes."""
        return (
            self.state,
            tuple(filing.accession for filing in self.filings),
            self.prospectus.accession if self.prospectus else None,
            self.price.value if self.price else None,
            self.price_problem,
        )

    def newer_than(self, accession: str) -> Filing | None:
        """The latest prospectus filed after the one the page reads, if any."""
        for index, filing in enumerate(self.filings):
            if filing.accession == accession:
                later = self.filings[:index]
                break
        else:
            later = self.filings
        return next((f for f in later if f.form in PROSPECTUS_FORMS), None)


class Index(Protocol):
    """Anything that can give the filing index and a document. Raises SourceError."""

    name: str

    def index(self, cik: str) -> dict[str, Any]: ...

    def cover(self, url: str) -> bytes: ...


def valid_contact(contact: str) -> bool:
    """An address that can sit in a header: one e-mail address, nothing else."""
    return re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", contact) is not None


class Edgar:
    """HTTPS requests to the SEC, each naming this client and its contact address."""

    name = "SEC EDGAR"

    def __init__(self, contact: str) -> None:
        if not valid_contact(contact):
            raise ValueError("the SEC contact must be one e-mail address")  # never echo it
        self._agent = f"{CLIENT} {contact}"

    def _get(self, url: str, limit: int) -> bytes:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in HOSTS:
            raise SourceError("not an address of the SEC")  # the contact goes nowhere else
        headers = {"User-Agent": self._agent, "Accept-Encoding": "identity"}
        request = urllib.request.Request(url, headers=headers)  # noqa: S310 - https, checked
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
                data: bytes = response.read(limit)
                return data
        except urllib.error.HTTPError as error:
            raise SourceError(f"HTTP {error.code}") from None
        except OSError as error:
            raise SourceError(type(error).__name__) from None

    def index(self, cik: str) -> dict[str, Any]:
        raw = self._get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", 8_000_000)
        try:
            payload = json.loads(raw)
        except ValueError as error:
            raise SourceError(type(error).__name__) from None
        if not isinstance(payload, dict):
            raise SourceError("unexpected answer")
        return payload

    def cover(self, url: str) -> bytes:
        return self._get(url, COVER_BYTES)


class RecordedIndex:
    """A saved answer, for tests: {"index": EDGAR's answer, "cover": the top of a document}."""

    name = "TEST DATA, not real filings"

    def __init__(self, path: Path) -> None:
        self.path = path

    def _saved(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError) as error:
            raise SourceError(type(error).__name__) from None
        if not isinstance(payload, dict):
            raise SourceError("unexpected answer")
        return payload

    def index(self, cik: str) -> dict[str, Any]:
        index = self._saved().get("index")
        if not isinstance(index, dict):
            raise SourceError("unexpected answer")
        return index

    def cover(self, url: str) -> bytes:
        cover = self._saved().get("cover")
        if not isinstance(cover, str):
            raise SourceError("HTTP 404")
        return cover.encode("utf-8")


def source_from(setting: str, contact: str) -> Index | None:
    """`auto` (EDGAR when a contact address is set, else nothing), `off`, or `file:<path>`."""
    if setting.startswith("file:"):
        return RecordedIndex(Path(setting[5:]))
    if setting == "auto" and contact:
        return Edgar(contact)
    if setting in {"auto", "off"}:
        return None
    raise ValueError(f"unknown filings source: {setting}")


def read_index(payload: dict[str, Any], *, cik: str, company: str) -> tuple[Filing, ...]:
    """The filings of the registrant, newest first, from EDGAR's answer."""
    if str(payload.get("cik", "")).lstrip("0") != cik.lstrip("0"):
        raise SourceError("answer for another company")
    if company.split(",")[0].lower() not in str(payload.get("name", "")).lower():
        raise SourceError("answer for another company")
    recent = (payload.get("filings") or {}).get("recent")
    if not isinstance(recent, dict):
        raise SourceError("unexpected answer")

    def column(key: str) -> list[Any]:
        values = recent.get(key)
        if not isinstance(values, list):
            raise SourceError("unexpected answer")
        return values

    accessions, forms, dates = column("accessionNumber"), column("form"), column("filingDate")
    documents = column("primaryDocument")
    if len({len(accessions), len(forms), len(dates), len(documents)}) != 1:
        raise SourceError("unexpected answer")
    filings = []
    for accession, form, filed, document in zip(accessions, forms, dates, documents, strict=True):
        if not (
            isinstance(accession, str)
            and re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession)
            and isinstance(form, str)
            and form
            and isinstance(filed, str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", filed)
        ):
            raise SourceError("unexpected answer")
        folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
        named = isinstance(document, str) and re.fullmatch(r"[\w.-]+", document) is not None
        filings.append(Filing(accession, form, filed, folder + document if named else folder))
    # EDGAR lists the newest first; sorting keeps that true whatever it does. Same day: its order.
    return tuple(sorted(filings, key=lambda filing: filing.filed, reverse=True))


def cover_text(data: bytes) -> str:
    """The text of the top of a filing, one space between words."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:  # filings are often in the Windows encoding
        text = data.decode("cp1252", errors="replace")
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text).replace("\xa0", " ")).strip()


def _amount(text: str) -> float:
    return float(text.replace(",", ""))


def read_price(data: bytes, filing: Filing, *, company: str, low: float, high: float) -> Price:
    """The initial public offering price on the cover of a final prospectus.

    Refused unless the cover names the company, is not a preliminary prospectus, gives the price
    per share and the total, and the total is the price times the number of shares on the same
    cover. `low` and `high` are the filed range: a price far outside it is taken for a misread.
    """
    if filing.form not in FINAL_PROSPECTUS:
        raise SourceError("not a final prospectus")
    text = cover_text(data)
    row = re.search(
        r"Initial public offering price\s*\$\s*([\d,]*\d(?:\.\d+)?)\s*\$\s*([\d,]*\d(?:\.\d+)?)",
        text,
    )
    start = text.find("Initial public offering price")
    if start < 0:
        raise SourceError("no price row on the cover")
    cover = text[:start]
    if company not in cover:
        raise SourceError("the cover does not name the company")
    if "subject to completion" in cover.lower():
        raise SourceError("a preliminary prospectus")
    if row is None or row.start() != start:
        raise SourceError("the price is blank")
    offered = re.search(r"(\d{1,3}(?:,\d{3})+) Shares\b", cover)
    if offered is None:
        raise SourceError("no number of shares on the cover")
    price, total, shares = _amount(row[1]), _amount(row[2]), int(_amount(offered[1]))
    if not re.fullmatch(r"\d+\.\d{2}", row[1]) or price <= 0:
        raise SourceError("price not in dollars and cents")
    if abs(price * shares - total) > 0.5:
        raise SourceError("the total is not the price times the shares")
    if not low / 2 <= price <= high * 2:
        raise SourceError("price far from the filed range")
    quote = f"{offered[1]} Shares … {row[0]}"
    return Price(price, total, shares, quote, filing, hashlib.sha256(data).hexdigest())


def check(
    source: Index,
    previous: Watch | None,
    now: int,
    *,
    cik: str,
    company: str,
    low: float,
    high: float,
) -> Watch:
    """Ask EDGAR once. A failure never raises: it becomes the `unavailable` state."""
    try:
        filings = read_index(source.index(cik), cik=cik, company=company)
    except SourceError as error:
        problem = str(error)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as error:
        problem = f"unexpected answer ({type(error).__name__})"
    else:
        watch = Watch("ok", now, filings, source.name)
        final = next((f for f in filings if f.form in FINAL_PROSPECTUS), None)
        if final is None:
            return watch
        watch = replace(watch, prospectus=final)
        if previous and previous.prospectus == final and previous.cover_read:
            # A document does not change: its cover is read once, whatever came out of it.
            return replace(
                watch, cover_read=True, price=previous.price, price_problem=previous.price_problem
            )
        try:
            cover = source.cover(final.url)
        except SourceError as error:
            return replace(watch, price_problem=f"not downloaded ({error})")  # asked again later
        try:
            price = read_price(cover, final, company=company, low=low, high=high)
        except SourceError as error:
            return replace(watch, cover_read=True, price_problem=str(error))
        return replace(watch, cover_read=True, price=price)
    if previous is None:
        return Watch("unavailable", now, source=source.name, detail=problem)
    return replace(previous, state="unavailable", checked=now, detail=problem)


def price_fact(price: Price, company: str) -> tuple[Fact, Document]:
    """The price as a FILED fact, with the document it was read from."""
    filing = price.filing
    document = Document(
        id="final",
        company=company,
        form=filing.form,
        title=f"Form {filing.form}, final prospectus",
        accession=filing.accession,
        filed=filing.filed,
        url=filing.url,
        source_sha256=price.sha256,
    )
    fact = Fact(
        id=PRICED,
        title="Initial public offering price",
        label="FILED",
        value=price.value,
        unit="USD/share",
        as_filed=f"${price.value:,.2f}",
        page="sheet cover",
        section="Cover page",
        quote=price.quote,
        context=(
            "Read by the service from the cover of the final prospectus. Checked: the total "
            "stated beside it is this price times the number of shares on the same cover."
        ),
    )
    return fact, document


class Watcher:
    """Checks EDGAR on a timer and tells the page when what it shows has changed."""

    def __init__(
        self,
        source: Index,
        on_change: Callable[[Watch], None],
        *,
        cik: str,
        company: str,
        low: float,
        high: float,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.source = source
        self.on_change = on_change
        self.cik, self.company, self.low, self.high = cik, company, low, high
        self.clock = clock
        self.failures = 0
        self.watch = self.ask(None)
        self.failures = int(self.watch.state == "unavailable")

    @property
    def wait(self) -> int:
        """Seconds until the next question: longer and longer while EDGAR fails."""
        if self.watch.state == "ok":
            return EVERY
        return min(LONGEST_WAIT, EVERY * (1 << min(max(0, self.failures - 1), 4)))

    def ask(self, previous: Watch | None) -> Watch:
        return check(
            self.source,
            previous,
            int(self.clock()),
            cik=self.cik,
            company=self.company,
            low=self.low,
            high=self.high,
        )

    async def step(self) -> None:
        new = await asyncio.to_thread(self.ask, self.watch)
        changed = new.shown != self.watch.shown
        self.failures = self.failures + 1 if new.state == "unavailable" else 0
        self.watch = new
        if changed:
            log.event(
                "filings_changed",
                state=new.state,
                latest=new.filings[0].form if new.filings else None,
                priced=new.price is not None,
                detail=new.detail or new.price_problem,
            )
            await asyncio.to_thread(self.on_change, new)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.wait)
            try:
                await self.step()
            except Exception as error:  # keep watching whatever happens
                log.event("filings_error", level="error", error=type(error).__name__)
