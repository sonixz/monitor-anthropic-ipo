"""Configuration: environment variables only, checked at startup."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ipo_monitor.edgar import valid_contact

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
    market: str = "off"
    filings: str = "off"
    # The address the SEC asks automated clients for. Personal: never printed, never logged.
    sec_contact: str = field(default="", repr=False)
    sec_contact_refused: bool = False  # a value was given and is not one e-mail address
    visits: Path | None = None  # the file of the visit counts; None keeps them in memory
    scan: str = "off"  # the scanner's closes: auto (Yahoo Finance), off, or file:<folder>
    signals: str = "off"  # signal files: auto (release and GitHub), local, off, or dir:<folder>
    scan_candidates: Path = Path("data/scan/candidates.json")  # the stocks the list ranks
    # The password of the portfolio page. Personal: never printed, never logged.
    portfolio_password: str = field(default="", repr=False)
    ledger: Path | None = None  # the owner's real orders; on the machine, outside git

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

        market = source.get("IPO_MARKET", "auto")
        if not re.fullmatch(r"off|auto|nasdaq|yahoo|file:.+", market):
            raise ConfigError(
                "IPO_MARKET must be auto, nasdaq, yahoo, off or file:<recorded answer>, "
                f"got {market!r}"
            )

        filings = source.get("IPO_FILINGS", "auto")
        if not re.fullmatch(r"off|auto|file:.+", filings):
            raise ConfigError(
                f"IPO_FILINGS must be auto, off or file:<recorded answer>, got {filings!r}"
            )
        # An unusable address switches the filings watch off instead of stopping the service:
        # the page must not go down for an optional source. The value is never shown.
        sec_contact = source.get("SEC_CONTACT", "").strip()
        refused = bool(sec_contact) and not valid_contact(sec_contact)

        visits_text = source.get("IPO_VISITS", "").strip()
        visits = Path(visits_text) if visits_text else None
        if visits is not None and not visits.parent.is_dir():
            raise ConfigError(
                f"IPO_VISITS must be a file in an existing directory, got {visits_text!r}"
            )

        scan = source.get("IPO_SCAN", "auto")
        if not re.fullmatch(r"off|auto|file:.+", scan):
            raise ConfigError(f"IPO_SCAN must be auto, off or file:<folder>, got {scan!r}")
        signals = source.get("IPO_SIGNALS", "auto")
        if not re.fullmatch(r"off|auto|local|dir:.+", signals):
            raise ConfigError(
                f"IPO_SIGNALS must be auto, local, off or dir:<folder>, got {signals!r}"
            )

        scan_candidates = Path(source.get("IPO_SCAN_CANDIDATES", "data/scan/candidates.json"))
        if scan != "off" and not scan_candidates.is_file():
            raise ConfigError(
                f"IPO_SCAN_CANDIDATES must be a candidate list file, got {str(scan_candidates)!r}"
            )

        ledger_text = source.get("IPO_LEDGER", "").strip()
        ledger = Path(ledger_text) if ledger_text else None
        if ledger is not None and not ledger.parent.is_dir():
            raise ConfigError(
                f"IPO_LEDGER must be a file in an existing directory, got {ledger_text!r}"
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
            market=market,
            filings=filings,
            sec_contact="" if refused else sec_contact,
            sec_contact_refused=refused,
            visits=visits,
            scan=scan,
            signals=signals,
            scan_candidates=scan_candidates,
            portfolio_password=source.get("PORTFOLIO_PASSWORD", ""),
            ledger=ledger,
        )
