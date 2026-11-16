"""The web service: one server-rendered page, its static files and a health check.

The page is rendered at startup. If the facts do not reconcile, or a number
has no source, rendering fails and the service does not start. It is rendered
again only when the market source says something new; if that rendering
fails, the previous page stays.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from ipo_monitor import __version__, log
from ipo_monitor.config import Settings
from ipo_monitor.facts import Facts
from ipo_monitor.market import Snapshot, Source, Watcher, source_from
from ipo_monitor.render import Page, render_page

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


def _iso(moment: int | None) -> str | None:
    return None if moment is None else datetime.fromtimestamp(moment, UTC).isoformat()


def create_app(settings: Settings | None = None, source: Source | None = None) -> FastAPI:
    """Build the service. `source` replaces the configured market source (tests)."""
    settings = settings or Settings.from_env()
    started = time.time()
    facts = Facts.load(settings.facts_dir)
    source = source or source_from(settings.market)

    def render(snapshot: Snapshot | None) -> Board:
        page = render_page(facts, release=settings.release, market=snapshot)
        body = page.html.encode("utf-8")
        log.event(
            "page_rendered",
            release=settings.release,
            facts=page.facts,
            calculations=page.calcs,
            checks_passed=page.checks,
            numbers_on_page=page.numbers,
            market=page.market,
            bytes=len(body),
        )
        return Board(page, body, '"' + hashlib.sha256(body).hexdigest()[:20] + '"')

    live: list[Board] = []  # one item: the page being served

    def publish(snapshot: Snapshot) -> None:
        try:
            live[:] = [render(snapshot)]
        except Exception as error:  # the page being served stays
            log.event("render_failed", level="error", error=type(error).__name__)

    watcher: Watcher | None = None
    if source is not None:
        # The first answer is awaited, so the first page never claims more than the source said.
        watcher = Watcher(source, facts.text("offering.symbol"), COMPANY, publish)
    live.append(render(watcher.snapshot if watcher else None))

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(watcher.run()) if watcher else None
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="ANT IPO Monitor",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.watcher = watcher
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

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def dashboard(request: Request) -> Response:
        current = live[0]
        headers = {"ETag": current.etag, "Cache-Control": "no-cache"}
        if request.headers.get("if-none-match") == current.etag:
            return Response(status_code=304, headers=headers)
        return Response(current.body, media_type="text/html; charset=utf-8", headers=headers)

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
            },
            headers={"Cache-Control": "no-store"},
        )

    app.mount("/static", VersionedStatic(packages=[("ipo_monitor", "static")]), name="static")
    return app
