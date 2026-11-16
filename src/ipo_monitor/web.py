"""The web service: one server-rendered page, its static files and a health check.

The page is rendered once at startup. If the facts do not reconcile, or a
number has no source, rendering fails and the service does not start.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from ipo_monitor import __version__, log
from ipo_monitor.config import Settings
from ipo_monitor.facts import Facts
from ipo_monitor.render import render_page

CONTENT_SECURITY_POLICY = (
    "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    started = time.time()
    facts = Facts.load(settings.facts_dir)
    page = render_page(facts, release=settings.release)
    body = page.html.encode("utf-8")
    etag = '"' + hashlib.sha256(body).hexdigest()[:20] + '"'
    log.event(
        "page_rendered",
        release=settings.release,
        facts=page.facts,
        calculations=page.calcs,
        checks_passed=page.checks,
        numbers_on_page=page.numbers,
        bytes=len(body),
    )

    app = FastAPI(
        title="ANT IPO Monitor",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
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
        headers = {"ETag": etag, "Cache-Control": "no-cache"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(body, media_type="text/html; charset=utf-8", headers=headers)

    @app.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "version": __version__,
                "release": settings.release,
                "uptime_s": int(time.time() - started),
                "data": {
                    "source_filed": page.filed,
                    "facts": page.facts,
                    "checks_passed": page.checks,
                },
            },
            headers={"Cache-Control": "no-store"},
        )

    app.mount("/static", VersionedStatic(packages=[("ipo_monitor", "static")]), name="static")
    return app
