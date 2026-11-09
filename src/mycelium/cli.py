"""Command line: ``mycelium serve`` and ``mycelium check``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from mycelium import __version__
from mycelium.config import ConfigError, load_config
from mycelium.vault import VaultIndex

DEFAULT_PORT = 8765


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

    sub.add_parser("check", parents=[common], help="scan the vault and list problems")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config, vault_override=args.vault)
    except ConfigError as exc:
        print(f"mycelium: {exc}", file=sys.stderr)
        return 2

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

    uvicorn.run(create_app(config), host=args.host, port=args.port, proxy_headers=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
