"""Start the service:  python -m ipo_monitor"""

from __future__ import annotations

import sys

import uvicorn

from ipo_monitor import log
from ipo_monitor.config import ConfigError, Settings
from ipo_monitor.web import create_app


def main() -> None:
    try:
        settings = Settings.from_env()
    except ConfigError as error:
        sys.exit(f"configuration error: {error}")
    log.configure(settings.log_level)
    app = create_app(settings)
    log.event("starting", host=settings.host, port=settings.port, release=settings.release)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
