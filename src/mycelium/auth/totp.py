"""Time-based one-time passwords (RFC 6238) with the standard library only.

Six digits, HMAC-SHA1, 30-second steps: what every authenticator app expects.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote, urlencode

STEP_SECONDS = 30
DIGITS = 6
DRIFT_STEPS = 1


def generate_secret() -> str:
    """A new random base32 secret (160 bits, as RFC 4226 recommends)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes:
    cleaned = secret.replace(" ", "").upper()
    padded = cleaned + "=" * (-len(cleaned) % 8)
    try:
        return base64.b32decode(padded, casefold=True)
    except ValueError as exc:
        raise ValueError("the TOTP secret is not valid base32") from exc


def is_valid_secret(secret: str) -> bool:
    try:
        return len(_key(secret)) >= 10
    except ValueError:
        return False


def code_at(secret: str, step: int, *, digits: int = DIGITS) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def step_for(timestamp: float) -> int:
    return int(timestamp // STEP_SECONDS)


def matching_step(secret: str, code: str, timestamp: float) -> int | None:
    """The time step ``code`` belongs to, allowing one step of clock drift."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    now = step_for(timestamp)
    for step in (now, now - DRIFT_STEPS, now + DRIFT_STEPS):
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, *, account: str, issuer: str) -> str:
    """The ``otpauth://`` link an authenticator app reads from a QR code."""
    label = quote(f"{issuer}:{account}")
    params = urlencode({"secret": secret, "issuer": issuer, "digits": DIGITS, "period": 30})
    return f"otpauth://totp/{label}?{params}"
