"""Command line: ``mycelium serve``, ``mycelium check`` and ``mycelium user``."""

from __future__ import annotations

import argparse
import getpass
import io
import secrets
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from mycelium import __version__
from mycelium.auth import AuthSetupError
from mycelium.auth.passwords import MIN_LENGTH, hash_password
from mycelium.auth.settings import (
    PASSWORD_HASH_ENV,
    SESSION_KEY_ENV,
    TOTP_SECRET_ENV,
    is_loopback,
)
from mycelium.auth.totp import generate_secret, matching_step, provisioning_uri
from mycelium.config import Config, ConfigError, load_config
from mycelium.vault import VaultIndex

DEFAULT_PORT = 8765

Prompt = Callable[[str], str]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mycelium", description=__doc__)
    parser.add_argument("--version", action="version", version=f"mycelium {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path, help="path to mycelium.toml")
    common.add_argument("--vault", type=Path, help="vault folder (overrides the config)")

    serve = sub.add_parser("serve", parents=[common], help="run the website")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve.add_argument(
        "--forwarded-allow-ips",
        default="127.0.0.1",
        help="proxies trusted for X-Forwarded-For/-Proto (comma-separated, default 127.0.0.1)",
    )

    sub.add_parser("check", parents=[common], help="scan the vault and list problems")

    user = sub.add_parser("user", help="set up sign-in secrets")
    user_sub = user.add_subparsers(dest="action", required=True)
    user_sub.add_parser("set-password", help=f"print {PASSWORD_HASH_ENV} for a new password")
    totp = user_sub.add_parser("totp", help=f"print {TOTP_SECRET_ENV} and a QR code")
    totp.add_argument("--account", default="owner", help="name shown in the authenticator app")
    user_sub.add_parser("session-key", help=f"print a new {SESSION_KEY_ENV}")
    user_sub.add_parser(
        "sign-out-all",
        parents=[common],
        help="end every session (deletes them from the data folder)",
    )
    return parser


def _env_line(name: str, value: str) -> str:
    # Single quotes keep the `$` signs of an argon2 hash literal in .env files and Compose.
    return f"{name}='{value}'"


def _set_password(prompt: Prompt) -> int:
    first = prompt("New password: ")
    if first != prompt("Repeat it: "):
        print("mycelium: the passwords do not match", file=sys.stderr)
        return 1
    try:
        hashed = hash_password(first)
    except ValueError as exc:
        print(f"mycelium: {exc}", file=sys.stderr)
        return 1
    print("\nAdd this line to your environment (.env):\n")
    print(_env_line(PASSWORD_HASH_ENV, hashed))
    return 0


def _qr_text(data: str) -> str:
    import qrcode

    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    out = io.StringIO()
    qr.print_ascii(out=out, invert=True)
    return out.getvalue()


def _can_print(text: str) -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def _totp(account: str, issuer: str, prompt: Prompt, clock: Callable[[], float]) -> int:
    secret = generate_secret()
    uri = provisioning_uri(secret, account=account, issuer=issuer)
    qr = _qr_text(uri)
    if _can_print(qr):
        print("Scan this with your authenticator app (or enter the secret by hand):\n")
        print(qr)
    else:
        print("This terminal cannot draw the QR code. Paste this link into a QR generator")
        print("you trust, or type the secret below into your authenticator app:\n")
        print(uri + "\n")
    print(f"Secret: {secret}\n")
    for _ in range(3):
        code = prompt("Type the 6-digit code it shows, to confirm: ")
        if matching_step(secret, code, clock()) is not None:
            print("\nConfirmed. Add this line to your environment (.env):\n")
            print(_env_line(TOTP_SECRET_ENV, secret))
            return 0
        print("That code does not match; check the phone's clock and try again.")
    print("mycelium: not confirmed; nothing to save", file=sys.stderr)
    return 1


def _sign_out_all(config: Config) -> int:
    from mycelium.app import AUTH_DB
    from mycelium.auth.store import AuthStore

    path = config.data.dir / AUTH_DB
    if not path.exists():
        print("No sessions.")
        return 0
    store = AuthStore(path)
    count = store.delete_all_sessions()
    store.close()
    print(f"Ended {count} session(s).")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    prompt: Prompt = getpass.getpass,
    clock: Callable[[], float] = time.time,
) -> int:
    args = _parser().parse_args(argv)

    if args.command == "user" and args.action == "set-password":
        print(f"Use at least {MIN_LENGTH} characters; a passphrase of a few words is ideal.")
        return _set_password(prompt)
    if args.command == "user" and args.action == "session-key":
        print(_env_line(SESSION_KEY_ENV, secrets.token_urlsafe(48)))
        return 0

    try:
        config = load_config(
            getattr(args, "config", None), vault_override=getattr(args, "vault", None)
        )
    except ConfigError as exc:
        print(f"mycelium: {exc}", file=sys.stderr)
        return 2

    if args.command == "user" and args.action == "totp":
        return _totp(args.account, config.site.title, input_prompt(prompt), clock)
    if args.command == "user":
        return _sign_out_all(config)

    if not config.vault.root.is_dir():
        print(f"mycelium: vault folder not found: {config.vault.root}", file=sys.stderr)
        return 2

    if args.command == "check":
        index = VaultIndex(config)
        index.refresh(force=True)
        print(f"{len(index.notes)} notes, {len(index.edges)} links, {len(index.issues)} issues")
        for issue in index.issues:
            print(f"  {issue.kind:<18} {issue.path}: {issue.detail}")
        return 1 if index.issues else 0

    import uvicorn

    from mycelium.app import create_app

    try:
        app = create_app(config, local_only=is_loopback(args.host))
    except AuthSetupError as exc:
        print(f"mycelium: {exc}", file=sys.stderr)
        return 2
    if not app.state.sign_in.enabled:
        print(f"mycelium: sign-in is off ({app.state.sign_in.settings.reason})", file=sys.stderr)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        proxy_headers=True,
        forwarded_allow_ips=args.forwarded_allow_ips,
    )
    return 0


def input_prompt(prompt: Prompt) -> Prompt:
    """The TOTP code is not secret once used; show it while typing unless a test overrides."""
    return input if prompt is getpass.getpass else prompt


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
