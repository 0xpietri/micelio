"""The FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

from mycelium import __version__
from mycelium.config import Config
from mycelium.vault import VaultIndex


def create_app(config: Config, *, index: VaultIndex | None = None) -> FastAPI:
    vault = index or VaultIndex(config)
    vault.refresh(force=True)

    app = FastAPI(
        title=config.site.title,
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.config = config
    app.state.vault = vault

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, object]:
        """Liveness for containers and monitoring. Reveals counts only, never titles."""
        vault.refresh()
        return {
            "status": "ok" if config.vault.root.is_dir() else "vault-missing",
            "version": __version__,
            "notes": len(vault.notes),
        }

    return app
