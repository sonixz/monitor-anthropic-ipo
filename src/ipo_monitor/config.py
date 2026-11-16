"""Configuration: environment variables only, checked at startup."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

LOG_LEVELS = ("debug", "info", "warning", "error")


class ConfigError(ValueError):
    """An environment variable has a value the service cannot use."""


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    facts_dir: Path
    release: str
    log_level: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        source = os.environ if env is None else env

        port_text = source.get("IPO_PORT", "8000")
        if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            raise ConfigError(
                f"IPO_PORT must be a port number between 1 and 65535, got {port_text!r}"
            )

        facts_dir = Path(source.get("IPO_FACTS_DIR", "data/facts"))
        if not facts_dir.is_dir():
            raise ConfigError(
                f"IPO_FACTS_DIR must be an existing directory, got {str(facts_dir)!r}"
            )

        release = source.get("IPO_RELEASE", "dev")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", release):
            raise ConfigError(
                f"IPO_RELEASE must be 1 to 40 letters, digits, dots, dashes or underscores, "
                f"got {release!r}"
            )

        log_level = source.get("IPO_LOG_LEVEL", "info").lower()
        if log_level not in LOG_LEVELS:
            raise ConfigError(
                f"IPO_LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}, got {log_level!r}"
            )

        host = source.get("IPO_HOST", "127.0.0.1")
        if not host:
            raise ConfigError("IPO_HOST must not be empty")

        return cls(
            host=host,
            port=int(port_text),
            facts_dir=facts_dir,
            release=release,
            log_level=log_level,
        )
