"""Decide whether sign-in is on, and with which secrets.

Secrets only ever come from the environment:

- ``MYCELIUM_PASSWORD_HASH``: argon2 hash from ``mycelium user set-password``
- ``MYCELIUM_TOTP_SECRET``: base32 secret from ``mycelium user totp``
- ``MYCELIUM_SESSION_KEY``: 32+ random characters from ``mycelium user session-key``
"""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass

from mycelium.auth.passwords import is_valid_hash
from mycelium.auth.totp import is_valid_secret
from mycelium.config import Config

PASSWORD_HASH_ENV = "MYCELIUM_PASSWORD_HASH"  # noqa: S105 (a variable name)
TOTP_SECRET_ENV = "MYCELIUM_TOTP_SECRET"  # noqa: S105 (a variable name)
SESSION_KEY_ENV = "MYCELIUM_SESSION_KEY"
MIN_SESSION_KEY = 32


class AuthSetupError(ValueError):
    """Sign-in is required but its secrets are missing or malformed."""


@dataclass(frozen=True, slots=True)
class AuthSettings:
    enabled: bool
    password_hash: str = ""
    totp_secret: str = ""
    session_key: str = ""
    reason: str = ""


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def resolve_auth(config: Config, environ: Mapping[str, str], *, local_only: bool) -> AuthSettings:
    """Work out the sign-in settings.

    ``local_only`` is true when the server listens on a loopback address only. There, with
    no secrets set, sign-in stays off so ``mycelium serve`` just works on a personal
    computer. Anywhere else, ``auth.mode = "local"`` needs all three secrets.
    """
    if config.auth.mode == "none":
        return AuthSettings(enabled=False, reason='auth.mode = "none"')

    password_hash = environ.get(PASSWORD_HASH_ENV, "").strip()
    totp_secret = environ.get(TOTP_SECRET_ENV, "").strip()
    session_key = environ.get(SESSION_KEY_ENV, "").strip()

    if local_only and not (password_hash or totp_secret or session_key):
        return AuthSettings(enabled=False, reason="listening on localhost with no secrets set")

    problems = []
    if not is_valid_hash(password_hash):
        problems.append(f"{PASSWORD_HASH_ENV} (run `mycelium user set-password`)")
    if not is_valid_secret(totp_secret):
        problems.append(f"{TOTP_SECRET_ENV} (run `mycelium user totp`)")
    if len(session_key) < MIN_SESSION_KEY:
        problems.append(f"{SESSION_KEY_ENV} (run `mycelium user session-key`)")
    if problems:
        raise AuthSetupError(
            'sign-in is on (auth.mode = "local") but these are missing or invalid: '
            + "; ".join(problems)
            + '. Set them, or set auth.mode = "none" if a gateway in front handles sign-in.'
        )
    return AuthSettings(
        enabled=True,
        password_hash=password_hash,
        totp_secret=totp_secret,
        session_key=session_key,
    )
