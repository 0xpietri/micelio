"""The landing (``/``, ``/api/landing``) and the Appearance page (``/appearance``)."""

from __future__ import annotations

import hmac
from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException

from mycelium.appearance import (
    MAX_UPLOAD_BYTES,
    MEDIA_TYPES,
    PALETTES,
    Appearance,
    AppearanceStore,
    ImageError,
    clean_text,
    palette_named,
)
from mycelium.auth.web import SignIn
from mycelium.config import PALETTE_NAMES, SOIL_MAX, SOIL_MIN, Config
from mycelium.i18n import Translate
from mycelium.landing import LandingBuilder, background_url
from mycelium.vault import VaultIndex

PROMPT_FIELDS = ("style", "sky", "horizon", "underground", "colors", "mood")
_MESSAGES = frozenset({"saved", "uploaded", "removed"})
_ERRORS = frozenset({"empty", "size", "type", "small", "form"})


class LandingPages:
    def __init__(
        self,
        config: Config,
        index: VaultIndex,
        store: AppearanceStore,
        templates: Jinja2Templates,
        sign_in: SignIn,
        t: Translate,
    ) -> None:
        self.config = config
        self.index = index
        self.store = store
        self.templates = templates
        self.sign_in = sign_in
        self.t = t
        self.builder = LandingBuilder(config, index)

    # -- texts ------------------------------------------------------------------------

    def default_headline(self) -> str:
        site, language = self.config.site, self.config.site.language
        configured = site.headline_for(language)
        if configured:
            return configured
        if site.owner:
            return self.t("site.owners_mycelium", owner=site.owner)
        return site.title

    def default_tagline(self) -> str:
        return self.config.site.tagline_for(self.config.site.language) or self.t("landing.tagline")

    def texts(self, appearance: Appearance) -> tuple[str, str]:
        return (
            appearance.headline or self.default_headline(),
            appearance.tagline or self.default_tagline(),
        )

    def default_prompt(self, appearance: Appearance) -> dict[str, str]:
        values = {
            name: self.t(f"prompt.{name}_default") for name in PROMPT_FIELDS if name != "colors"
        }
        values["colors"] = ", ".join(appearance.colors.swatch)
        return values

    # -- routes -----------------------------------------------------------------------

    def _form_ok(self, request: Request, token: str) -> bool:
        return hmac.compare_digest(token, self.sign_in.form_token(request, "appearance"))

    def router(self) -> APIRouter:
        router = APIRouter()
        render = self.templates.TemplateResponse

        @router.get("/", include_in_schema=False)
        def landing(request: Request) -> Response:
            self.index.refresh()
            appearance = self.store.current()
            data = self.builder.build(appearance)
            headline, tagline = self.texts(appearance)
            context = {
                "headline": headline,
                "tagline": tagline,
                "data": data,
                "palette": appearance.colors,
                "background": background_url(appearance),
            }
            return render(request, "landing.html", context)

        @router.get("/api/landing", include_in_schema=False)
        def landing_data() -> Response:
            self.index.refresh()
            data = self.builder.build(self.store.current())
            return JSONResponse(dict(data), headers={"Cache-Control": "no-store"})

        @router.get("/appearance/background", include_in_schema=False)
        def own_background() -> Response:
            appearance = self.store.current()
            if not appearance.own_type:
                raise HTTPException(status_code=404)
            return FileResponse(
                self.store.own_path(appearance.own_type),
                media_type=MEDIA_TYPES[appearance.own_type],
                headers={"Cache-Control": "private, max-age=31536000, immutable"},
            )

        @router.get("/appearance", include_in_schema=False)
        def appearance_page(request: Request, done: str = "", error: str = "") -> Response:
            appearance = self.store.current()
            prompt_values = self.default_prompt(appearance)
            context = {
                "nav": "appearance",
                "appearance": appearance,
                "palettes": [PALETTES[k] for k in PALETTE_NAMES],
                "background": background_url(appearance),
                "default_headline": self.default_headline(),
                "default_tagline": self.default_tagline(),
                "form_token": self.sign_in.form_token(request, "appearance"),
                "done": done if done in _MESSAGES else "",
                "error": error if error in _ERRORS else "",
                "soil_min": SOIL_MIN,
                "soil_max": SOIL_MAX,
                "max_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
                "prompt_fields": PROMPT_FIELDS,
                "prompt_values": prompt_values,
                "prompt": self.t(
                    "prompt.template",
                    soil=appearance.soil,
                    rest=100 - appearance.soil,
                    **prompt_values,
                ),
            }
            return render(request, "appearance.html", context)

        @router.post("/appearance", include_in_schema=False)
        def save(
            request: Request,
            csrf: Annotated[str, Form()] = "",
            palette: Annotated[str, Form()] = "",
            background: Annotated[str, Form()] = "builtin",
            recolor: Annotated[str, Form()] = "",
            soil: Annotated[int, Form()] = 0,
            headline: Annotated[str, Form()] = "",
            tagline: Annotated[str, Form()] = "",
        ) -> Response:
            if not self._form_ok(request, csrf):
                return _back(error="form")
            now = self.store.current()
            chosen = replace(
                now,
                palette=palette_named(palette, now.palette),
                background="own" if background == "own" and now.own_type else "builtin",
                recolor=recolor == "on",
                soil=soil if SOIL_MIN <= soil <= SOIL_MAX else now.soil,
                headline=clean_text(headline),
                tagline=clean_text(tagline),
            )
            self.store.save(chosen)
            return _back(done="saved")

        @router.post("/appearance/background", include_in_schema=False)
        async def upload(
            request: Request,
            image: Annotated[UploadFile | None, File()] = None,
            csrf: Annotated[str, Form()] = "",
        ) -> Response:
            if not self._form_ok(request, csrf):
                return _back(error="form")
            data = await image.read(MAX_UPLOAD_BYTES + 1) if image is not None else b""
            try:
                self.store.store_background(data)
            except ImageError as exc:
                return _back(error=exc.code)
            return _back(done="uploaded")

        @router.post("/appearance/background/remove", include_in_schema=False)
        def remove(request: Request, csrf: Annotated[str, Form()] = "") -> Response:
            if not self._form_ok(request, csrf):
                return _back(error="form")
            self.store.remove_background()
            return _back(done="removed")

        return router


def _back(*, done: str = "", error: str = "") -> Response:
    """Back to the page with a message (post, redirect, get)."""
    target = "/appearance" + (f"?error={error}" if error else f"?done={done}")
    return RedirectResponse(target, status_code=303)
