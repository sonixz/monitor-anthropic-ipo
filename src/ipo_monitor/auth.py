"""The portal's gate: one owner account, a login page, a signed session cookie.

The username and the password come from the machine's secrets (`SITE_USER`, `SITE_PASSWORD`),
never from the repository. A successful login sets a cookie that holds its expiry and a
signature of it made with a key derived from the credentials: changing the password signs every
session out. Failed logins are counted; after `MAX_FAILURES` in `WINDOW` seconds, logins are
refused for `PAUSE` seconds. Nothing here is printed or logged.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections import deque
from dataclasses import dataclass, field

COOKIE = "antipo_session"
LIFETIME = 30 * 24 * 3600  # seconds a login lasts
MAX_FAILURES = 10
WINDOW = 600
PAUSE = 300


@dataclass
class Gate:
    user: str = field(repr=False)
    password: str = field(repr=False)
    failures: deque[float] = field(default_factory=deque, repr=False)
    paused_until: float = 0.0

    @property
    def on(self) -> bool:
        return bool(self.user and self.password)

    def _key(self) -> bytes:
        material = f"antipo-session\x00{self.user}\x00{self.password}".encode()
        return hashlib.sha256(material).digest()

    def _sign(self, expires: int) -> str:
        return hmac.new(self._key(), str(expires).encode(), hashlib.sha256).hexdigest()

    def issue(self, now: float | None = None) -> str:
        expires = int((now if now is not None else time.time()) + LIFETIME)
        return f"{expires}.{self._sign(expires)}"

    def valid(self, cookie: str | None, now: float | None = None) -> bool:
        if not self.on or not cookie or "." not in cookie:
            return False
        expires_text, _, signature = cookie.partition(".")
        if not expires_text.isdigit():
            return False
        expires = int(expires_text)
        if expires < (now if now is not None else time.time()):
            return False
        return hmac.compare_digest(signature, self._sign(expires))

    def login(self, user: str, password: str, now: float | None = None) -> str | None:
        """None when the credentials are right; otherwise what to tell the reader."""
        moment = now if now is not None else time.time()
        if moment < self.paused_until:
            return "Too many attempts. Wait a few minutes and try again."
        right_user = hmac.compare_digest(user.encode(), self.user.encode())
        right_password = hmac.compare_digest(password.encode(), self.password.encode())
        if self.on and right_user and right_password:
            return None
        self.failures.append(moment)
        while self.failures and self.failures[0] < moment - WINDOW:
            self.failures.popleft()
        if len(self.failures) >= MAX_FAILURES:
            self.paused_until = moment + PAUSE
            self.failures.clear()
            return "Too many attempts. Wait a few minutes and try again."
        return "Wrong username or password."


def bearer(header: str, token: str) -> bool:
    """An `Authorization: Bearer <token>` header with the expected token."""
    scheme, _, value = header.partition(" ")
    if not token or scheme.lower() != "bearer" or not value:
        return False
    return hmac.compare_digest(value.strip().encode(), token.encode())
