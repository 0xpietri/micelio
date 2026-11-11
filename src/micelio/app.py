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
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from micelio import __version__
from micelio.appearance import AppearanceStore
from micelio.auth import resolve_auth
from micelio.auth.store import AuthStore
from micelio.auth.web import Clock, SignIn, install_security_headers
from micelio.changes import Changes
from micelio.config import Config
from micelio.formatting import Dates
from micelio.i18n import (
    LANGUAGE_COOKIE,
    ActiveLanguage,
    LanguageMiddleware,
    available_languages,
    browser_strings,
    language_menu,
    translator,
)
from micelio.landing_web import LandingPages
from micelio.pages import Pages
from micelio.static_files import ClearStaleCache, FreshStaticFiles, fingerprint
from micelio.vault import PublicView, VaultIndex

PACKAGE = Path(str(files("micelio")))
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
        looks.close()

    settings = resolve_auth(
        config, os.environ if environ is None else environ, local_only=local_only
    )
    store = AuthStore(config.data.dir / AUTH_DB) if settings.enabled else None
    looks = AppearanceStore(config)

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
    templates.env.globals.update(
        t=t, site=config.site, language=ActiveLanguage(language), languages=language_menu
    )

    changes = Changes()
    templates.env.globals["changes"] = changes

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

    @app.get("/language/{code}", include_in_schema=False)
    def choose_language(code: str, next: str = "/") -> Response:
        """The flag in the header: remember the language in a cookie, go back (§5a)."""
        if code not in browser_locales:
            raise StarletteHTTPException(status_code=404)
        back = (
            next if next.startswith("/") and not next.startswith("//") and "\\" not in next else "/"
        )
        response = RedirectResponse(back, status_code=303)
        response.set_cookie(
            LANGUAGE_COOKIE, code, max_age=365 * 24 * 3600, samesite="lax", path="/"
        )
        return response

    app.mount("/static", FreshStaticFiles(directory=PACKAGE / "static"), name="static")
    sign_in.install(app)
    install_security_headers(app)

    dates = Dates(language, config.site.timezone)
    public = PublicView(vault)
    app.include_router(Pages(config, vault, templates, dates, looks, sign_in, public).router())
    app.include_router(LandingPages(config, vault, looks, templates, sign_in, t, public).router())

    @app.get("/changes", include_in_schema=False)
    def changelog(request: Request) -> Response:
        """Everything each version brought, newest first: the packaged CHANGELOG.md."""
        return templates.TemplateResponse(request, "changes.html", {"nav": "changes"})

    @app.exception_handler(StarletteHTTPException)
    async def not_found(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code != 404:
            return await http_exception_handler(request, exc)
        return templates.TemplateResponse(request, "not_found.html", {}, status_code=404)

    @app.get("/healthz", include_in_schema=False)
    def healthz(request: Request) -> dict[str, object]:
        """Liveness for containers and monitoring. Never titles; the number of notes
        only when signed in, since private notes are not even counts for visitors (§9)."""
        vault.refresh()
        body: dict[str, object] = {
            "status": "ok" if config.vault.root.is_dir() else "vault-missing",
            "version": __version__,
        }
        if sign_in.sees_everything(request):
            body["notes"] = len(vault.notes)
        return body

    # Browsers that kept an older build's CSS and JS drop them on their next page.
    app.add_middleware(ClearStaleCache, build=fingerprint(PACKAGE / "static"))
    # Outermost, so the visitor's language is set before anything else runs.
    app.add_middleware(LanguageMiddleware, languages=available_languages())
    return app
