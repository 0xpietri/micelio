"""The FastAPI application."""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from mycelium import __version__
from mycelium.auth import resolve_auth
from mycelium.auth.store import AuthStore
from mycelium.auth.web import Clock, SignIn, install_security_headers
from mycelium.config import Config
from mycelium.formatting import Dates
from mycelium.i18n import available_languages, browser_strings, translator
from mycelium.pages import Pages
from mycelium.vault import VaultIndex

PACKAGE = Path(str(files("mycelium")))
AUTH_DB = "auth.sqlite3"


def create_app(
    config: Config,
    *,
    index: VaultIndex | None = None,
    environ: Mapping[str, str] | None = None,
    local_only: bool = False,
    clock: Clock = time.time,
) -> FastAPI:
    """Build the app. Raises ``AuthSetupError`` when sign-in is on but not set up."""
    vault = index or VaultIndex(config)
    vault.refresh(force=True)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if store is not None:
            store.close()

    settings = resolve_auth(
        config, os.environ if environ is None else environ, local_only=local_only
    )
    store = AuthStore(config.data.dir / AUTH_DB) if settings.enabled else None

    app = FastAPI(
        lifespan=lifespan,
        title=config.site.title,
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.config = config
    app.state.vault = vault

    language = config.site.language
    t = translator(language)
    templates = Jinja2Templates(directory=PACKAGE / "templates")
    templates.env.globals.update(t=t, site=config.site, language=language)

    sign_in = SignIn(config, settings, store, templates, t, clock)
    app.state.sign_in = sign_in
    templates.env.globals["sign_in"] = sign_in

    browser_locales = {lang: browser_strings(lang) for lang in available_languages()}

    # Registered before the static mount, which would otherwise answer first.
    @app.get("/static/locales/{name}", include_in_schema=False)
    def browser_locale(name: str) -> Response:
        """Browser strings, generated at start from ``locales/<lang>.toml`` (§5a)."""
        language, dot, extension = name.rpartition(".")
        strings = browser_locales.get(language) if dot and extension == "json" else None
        if strings is None:
            raise StarletteHTTPException(status_code=404)
        return JSONResponse(strings, headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")
    sign_in.install(app)
    install_security_headers(app)

    dates = Dates(language, config.site.timezone)
    app.include_router(Pages(config, vault, templates, dates).router())

    @app.exception_handler(StarletteHTTPException)
    async def not_found(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code != 404:
            return await http_exception_handler(request, exc)
        return templates.TemplateResponse(request, "not_found.html", {}, status_code=404)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, object]:
        """Liveness for containers and monitoring. Reveals counts only, never titles."""
        vault.refresh()
        return {
            "status": "ok" if config.vault.root.is_dir() else "vault-missing",
            "version": __version__,
            "notes": len(vault.notes),
        }

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(request: Request) -> Response:
        vault.refresh()
        return templates.TemplateResponse(request, "home.html", {"note_count": len(vault.notes)})

    return app
