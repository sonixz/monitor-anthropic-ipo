"""The web service: one server-rendered page, its static files and a health check.

The page is rendered at startup. If the facts do not reconcile, or a number
has no source, rendering fails and the service does not start. It is rendered
again only when the market source or the SEC's filing index says something new;
if that rendering fails, the previous page stays.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import re
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from ipo_monitor import __version__, edgar, log
from ipo_monitor.config import Settings
from ipo_monitor.edgar import Index, Watch
from ipo_monitor.facts import Facts
from ipo_monitor.market import Snapshot, Source, Watcher, source_from
from ipo_monitor.render import Page, render_page
from ipo_monitor.scan import watch as scan_watch
from ipo_monitor.scan.bars import BarSource, RecordedDaily, YahooDaily
from ipo_monitor.scan.board import Board as ScanBoard
from ipo_monitor.scan.board import build as build_scan
from ipo_monitor.scan.board import dossier
from ipo_monitor.scan.render import ScanPage, render_scan
from ipo_monitor.scan.universe import Candidates
from ipo_monitor.visits import Visits

SIGNALS = Path("data/signals")


def scan_sources(
    settings: Settings,
) -> tuple[BarSource | None, list[scan_watch.SignalSource]]:
    """The scanner's closes and signal files, as configured."""
    if settings.scan == "off":
        return None, []
    bars: BarSource = (
        RecordedDaily(Path(settings.scan[5:]))
        if settings.scan.startswith("file:")
        else YahooDaily()
    )
    signals: list[scan_watch.SignalSource] = []
    if settings.signals in ("auto", "local"):
        signals.append(scan_watch.Folder(SIGNALS))
    if settings.signals == "auto":
        signals.append(scan_watch.GitHub())
    if settings.signals.startswith("dir:"):
        signals.append(scan_watch.Folder(Path(settings.signals[4:]), name="folder"))
    return bars, signals


COMPANY = "Anthropic"  # the market source must name the company so, or its price is not shown

CONTENT_SECURITY_POLICY = (
    "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Strict-Transport-Security": "max-age=31536000",
}


class VersionedStatic(StaticFiles):
    """Static files are requested with ?v=<hash>, so they can be cached for long."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


@dataclass
class Board:
    """The page being served. Replaced as a whole when the market data changes."""

    page: Page
    body: bytes
    etag: str


@dataclass
class Seen:
    """The last answer of each outside source."""

    market: Snapshot | None = None
    filings: Watch | None = None


def _iso(moment: int | None) -> str | None:
    return None if moment is None else datetime.fromtimestamp(moment, UTC).isoformat()


def _filings_health(watcher: edgar.Watcher | None) -> dict[str, object]:
    if watcher is None:
        return {"state": "off"}
    watch = watcher.watch
    latest = watch.filings[0] if watch.filings else None
    return {
        "state": watch.state,
        "source": watch.source,
        "checked": _iso(watch.checked),
        "latest": {"form": latest.form, "filed": latest.filed} if latest else None,
        "final_prospectus": watch.prospectus.filed if watch.prospectus else None,
        "final_price_read": watch.price is not None,
    }


def filed_range(facts: Facts) -> tuple[float, float]:
    """The last price range filed: the current filing's, or the latest amendment's once the
    final prospectus (which has no range) is the current filing."""
    if "offering.price_low" in facts:
        return facts.num("offering.price_low"), facts.num("offering.price_high")
    for old in reversed(facts.history):
        values = {f.id: f.value for f in old.facts}
        low, high = values.get("offering.price_low"), values.get("offering.price_high")
        if isinstance(low, float) and isinstance(high, float):
            return low, high
    raise ValueError("no price range in the filings")


def create_app(
    settings: Settings | None = None, source: Source | None = None, filings: Index | None = None
) -> FastAPI:
    """Build the service. `source` and `filings` replace the configured sources (tests)."""
    settings = settings or Settings.from_env()
    started = time.time()
    facts = Facts.load(settings.facts_dir)
    source = source or source_from(settings.market)
    filings = filings or edgar.source_from(settings.filings, settings.sec_contact)
    if settings.sec_contact_refused:
        log.event("filings_off", level="warning", reason="SEC_CONTACT is not one e-mail address")
    seen = Seen()
    visits = Visits(settings.visits)

    def render() -> Board:
        release = settings.release
        try:
            page = render_page(facts, release=release, market=seen.market, filings=seen.filings)
        except Exception as error:
            if seen.filings is None:
                raise
            # Whatever the filing index brought, the page of the facts and the market stays.
            log.event("render_failed", level="error", part="filings", error=type(error).__name__)
            page = render_page(facts, release=release, market=seen.market)
        body = page.html.encode("utf-8")
        log.event(
            "page_rendered",
            release=settings.release,
            facts=page.facts,
            calculations=page.calcs,
            checks_passed=page.checks,
            numbers_on_page=page.numbers,
            market=page.market,
            filings=page.filings,
            bytes=len(body),
        )
        return Board(page, body, '"' + hashlib.sha256(body).hexdigest()[:20] + '"')

    live: list[Board] = []  # one item: the page being served
    rendering = threading.Lock()  # the two watchers may speak at the same moment

    def publish() -> None:
        with rendering:
            try:
                live[:] = [render()]
            except Exception as error:  # the page being served stays
                log.event("render_failed", level="error", error=type(error).__name__)

    def market_changed(snapshot: Snapshot) -> None:
        seen.market = snapshot
        publish()

    def filings_changed(watch: Watch) -> None:
        seen.filings = watch
        publish()

    watcher: Watcher | None = None
    if source is not None:
        # The first answer is awaited, so the first page never claims more than the source said.
        watcher = Watcher(source, facts.text("offering.symbol"), COMPANY, market_changed)
        seen.market = watcher.snapshot
    live.append(render())  # the facts alone must give a page, or the service does not start

    filings_watcher: edgar.Watcher | None = None
    if filings is not None:
        document = facts.filing
        registrant = re.search(r"/edgar/data/(\d+)/", document.url)
        if registrant is None:
            raise ValueError("the filing's link does not give the registrant's number")
        filings_watcher = edgar.Watcher(
            filings,
            filings_changed,
            cik=registrant[1],
            company=document.company,
            low=filed_range(facts)[0],
            high=filed_range(facts)[1],
        )
        filings_changed(filings_watcher.watch)  # a failure here leaves the page above

    scan: list[ScanPage] = []  # one item: the scanner page being served
    scanner: scan_watch.ScanWatcher | None = None

    def scan_changed(board: ScanBoard) -> None:
        try:
            page = render_scan(board, release=settings.release)
        except Exception as error:  # the page being served stays
            log.event("render_failed", level="error", part="scan", error=type(error).__name__)
            return
        scan[:] = [page]
        log.event(
            "scan_rendered",
            stocks=page.stocks,
            signals=page.signals,
            session=board.session,
            bytes=len(page.html),
        )

    bars, signal_sources = scan_sources(settings)
    if bars is not None:
        scanner = scan_watch.ScanWatcher(
            Candidates.load(settings.scan_candidates), bars, signal_sources, scan_changed
        )
        # Until the first closes are read, the page says so instead of showing an empty list.
        scanner.board = build_scan(scanner.candidates, {}, {}, datetime.now(UTC))
        scan_changed(scanner.board)

    async def first_scan() -> None:
        if scanner is None:
            return
        try:
            board = await asyncio.to_thread(scanner.start)
            scan_changed(board)
        except Exception as error:
            log.event("scan_error", level="error", error=type(error).__name__)
        await scanner.run()

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        tasks = [asyncio.create_task(each.run()) for each in (watcher, filings_watcher) if each]
        if scanner is not None:
            tasks.append(asyncio.create_task(first_scan()))
        yield
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="Anthropic IPO Watch",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.watcher = watcher
    app.state.filings = filings_watcher
    app.state.visits = visits
    app.state.scanner = scanner
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def headers_and_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        begin = time.perf_counter()
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if request.url.path != "/health":
            log.event(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                ms=round((time.perf_counter() - begin) * 1000, 1),
            )
        return response

    def html(request: Request, body: bytes, etag: str) -> Response:
        headers = {"ETag": etag, "Cache-Control": "no-cache"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(body, media_type="text/html; charset=utf-8", headers=headers)

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def home(request: Request) -> Response:
        if scan:
            return html(request, scan[0].html.encode("utf-8"), scan[0].etag)
        return html(request, live[0].body, live[0].etag)

    @app.api_route("/ant", methods=["GET", "HEAD"], include_in_schema=False)
    async def dashboard(request: Request) -> Response:
        return html(request, live[0].body, live[0].etag)

    @app.get("/scan/dossier.json", include_in_schema=False)
    async def scan_dossier() -> JSONResponse:
        if scanner is None or scanner.board is None:
            return JSONResponse({"error": "the scanner is off"}, status_code=404)
        return JSONResponse(
            dossier(scanner.board, datetime.now(UTC)), headers={"Cache-Control": "no-cache"}
        )

    @app.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "version": __version__,
                "release": settings.release,
                "uptime_s": int(time.time() - started),
                "data": {
                    "source_filed": live[0].page.filed,
                    "facts": live[0].page.facts,
                    "checks_passed": live[0].page.checks,
                },
                "market": {
                    "state": live[0].page.market,
                    "source": watcher.snapshot.source if watcher else None,
                    "checked": _iso(watcher.snapshot.checked) if watcher else None,
                    "quote_time": _iso(watcher.snapshot.quote.time)
                    if watcher and watcher.snapshot.quote
                    else None,
                },
                "filings": _filings_health(filings_watcher),
                "scan": scan_watch.health(scanner),
                "visits": {
                    key: value
                    for key, value in visits.summary().items()
                    if key in ("today", "total", "since")
                },
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/seen", include_in_schema=False)
    async def seen_once() -> Response:
        visits.add()  # the page's script calls this once per browser session
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @app.get("/stats", include_in_schema=False)
    async def stats() -> JSONResponse:
        return JSONResponse(visits.summary(), headers={"Cache-Control": "no-store"})

    app.mount("/static", VersionedStatic(packages=[("ipo_monitor", "static")]), name="static")
    return app
