"""Sign-in state in SQLite: sessions, failed attempts and the last TOTP step used.

Session tokens are random; only their SHA-256 is stored, so a copy of the database
cannot be turned into a working cookie. Deleting the file signs everyone out.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS failures (
    address TEXT NOT NULL,
    at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS failures_by_address ON failures (address, at);
CREATE TABLE IF NOT EXISTS totp_used (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    step INTEGER NOT NULL
);
"""


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthStore:
    """Thread-safe; one connection guarded by a lock is plenty for one user."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # -- sessions -------------------------------------------------------------

    def create_session(self, now: float, ttl_seconds: float) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            self._db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?)", (_digest(token), now, now + ttl_seconds)
            )
        return token

    def session_valid(self, token: str, now: float) -> bool:
        with self._lock:
            row = self._db.execute(
                "SELECT expires_at FROM sessions WHERE token_hash = ?", (_digest(token),)
            ).fetchone()
        return row is not None and float(row[0]) > now

    def delete_session(self, token: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM sessions WHERE token_hash = ?", (_digest(token),))

    def delete_all_sessions(self) -> int:
        with self._lock:
            return self._db.execute("DELETE FROM sessions").rowcount

    # -- failed attempts ------------------------------------------------------

    def record_failure(self, address: str, now: float) -> None:
        with self._lock:
            self._db.execute("INSERT INTO failures VALUES (?, ?)", (address, now))

    def failures_since(self, address: str, since: float) -> int:
        with self._lock:
            self._db.execute("DELETE FROM failures WHERE at < ?", (since,))
            row = self._db.execute(
                "SELECT COUNT(*) FROM failures WHERE address = ? AND at >= ?", (address, since)
            ).fetchone()
        return int(row[0])

    def clear_failures(self, address: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM failures WHERE address = ?", (address,))

    # -- TOTP replay ----------------------------------------------------------

    def claim_totp_step(self, step: int) -> bool:
        """Record ``step`` as used. False when it, or a later step, was used already."""
        with self._lock:
            row = self._db.execute("SELECT step FROM totp_used WHERE id = 1").fetchone()
            if row is not None and int(row[0]) >= step:
                return False
            self._db.execute(
                "INSERT INTO totp_used (id, step) VALUES (1, ?) "
                "ON CONFLICT (id) DO UPDATE SET step = excluded.step",
                (step,),
            )
        return True
