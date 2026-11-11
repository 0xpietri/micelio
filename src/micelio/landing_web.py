"""The landing (``/``, ``/api/landing``) and the Appearance page (``/appearance``)."""

from __future__ import annotations

import hmac
from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException

from micelio.appearance import (
    MAX_NAME,
    MAX_UPLOAD_BYTES,
    MEDIA_TYPES,
    PALETTES,
    Appearance,
    AppearanceStore,
    ImageError,
    clean_text,
    in_range,
    palette_named,
    text_font_named,
    title_effect_named,
    title_font_named,
)
from micelio.auth.web import SignIn
from micelio.config import (
    LABEL_SIZE_MAX,
    LABEL_SIZE_MIN,
    PALETTE_NAMES,
    SOIL_MAX,
    SOIL_MIN,
    TEXT_FONTS,
    TEXT_SIZE_MAX,
    TEXT_SIZE_MIN,
    TITLE_EFFECTS,
    TITLE_FONTS,
    TITLE_SIZE_MAX,
    TITLE_SIZE_MIN,
    Config,
)
from micelio.i18n import Translate, active_language
from micelio.landing import LandingBuilder, background_url
from micelio.looks import NodeLooks
from micelio.vault import PublicView, VaultIndex

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
        public: PublicView,
    ) -> None:
        self.config = config
        self.index = index
        self.store = store
        self.templates = templates
        self.sign_in = sign_in
        self.t = t
        dress = NodeLooks(store).all
        self.everything = LandingBuilder(config, index, dress)
        self.public = LandingBuilder(config, public, dress)
        templates.env.globals["site_name"] = self.site_name
        templates.env.globals["look_choices"] = self.look_choices

    def look_choices(self) -> dict[str, object]:
        """What a visitor may pick for their own look (§7b): kept in their browser only,
        it never changes the site for anyone else. The owner's look is the default."""
        look = self.store.current()
        return {
            "palettes": [PALETTES[k] for k in PALETTE_NAMES],
            "title_fonts": TITLE_FONTS,
            "text_fonts": TEXT_FONTS,
            "title_effects": TITLE_EFFECTS,
            "sizes": {
                "title_size": (TITLE_SIZE_MIN, TITLE_SIZE_MAX, 5, "%"),
                "text_size": (TEXT_SIZE_MIN, TEXT_SIZE_MAX, 1, "px"),
                "graph_labels": (LABEL_SIZE_MIN, LABEL_SIZE_MAX, 5, "%"),
            },
            "owner": look,
            "recolors": look.recolors,
        }

    # -- texts ------------------------------------------------------------------------

    def default_headline(self) -> str:
        site, language = self.config.site, active_language(self.config.site.language)
        configured = site.headline_for(language)
        if configured:
            return configured
        if site.owner:
            return self.t("site.owners_micelio", owner=site.owner)
        return self.site_name()

    def site_name(self) -> str:
        """The site's name: the Appearance page's, else the config's ``site.title``."""
        return self.store.current().site_name or self.config.site.title

    def default_tagline(self) -> str:
        language = active_language(self.config.site.language)
        return self.config.site.tagline_for(language) or self.t("landing.tagline")

    def texts(self, appearance: Appearance) -> tuple[str, str]:
        return (
            appearance.headline or self.default_headline(),
            self.default_tagline() if appearance.tagline is None else appearance.tagline,
        )

    def default_prompt(self, appearance: Appearance) -> dict[str, str]:
        values = {
            name: self.t(f"prompt.{name}_default") for name in PROMPT_FIELDS if name != "colors"
        }
        values["colors"] = ", ".join(appearance.colors.swatch)
        return values

    # -- routes -----------------------------------------------------------------------

    def builder(self, request: Request) -> LandingBuilder:
        """The whole vault when signed in, the public notes otherwise (§9). Refreshed."""
        builder = self.everything if self.sign_in.sees_everything(request) else self.public
        builder.index.refresh()
        return builder

    def _form_ok(self, request: Request, token: str) -> bool:
        return hmac.compare_digest(token, self.sign_in.form_token(request, "appearance"))

    def router(self) -> APIRouter:
        router = APIRouter()
        render = self.templates.TemplateResponse

        @router.get("/", include_in_schema=False)
        def landing(request: Request) -> Response:
            appearance = self.store.current()
            data = self.builder(request).build(appearance)
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
        def landing_data(request: Request, palette: str = Query("", max_length=40)) -> Response:
            look = self.store.current()
            if palette:  # a visitor's own palette, kept in their browser (§7b)
                look = replace(look, palette=palette_named(palette, look.palette))
            data = self.builder(request).build(look)
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
            if not self.sign_in.sees_everything(request):  # signed-in only, never public
                raise HTTPException(status_code=404)
            appearance = self.store.current()
            prompt_values = self.default_prompt(appearance)
            context = {
                "nav": "appearance",
                "appearance": appearance,
                "palettes": [PALETTES[k] for k in PALETTE_NAMES],
                "background": background_url(appearance),
                "default_headline": self.default_headline(),
                "default_tagline": self.default_tagline(),
                "max_name": MAX_NAME,
                "form_token": self.sign_in.form_token(request, "appearance"),
                "done": done if done in _MESSAGES else "",
                "error": error if error in _ERRORS else "",
                "soil_min": SOIL_MIN,
                "soil_max": SOIL_MAX,
                "title_fonts": TITLE_FONTS,
                "text_fonts": TEXT_FONTS,
                "title_effects": TITLE_EFFECTS,
                "sizes": {
                    "title_size": (TITLE_SIZE_MIN, TITLE_SIZE_MAX, 5, "%"),
                    "text_size": (TEXT_SIZE_MIN, TEXT_SIZE_MAX, 1, "px"),
                    "graph_labels": (LABEL_SIZE_MIN, LABEL_SIZE_MAX, 5, "%"),
                },
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
            site_name: Annotated[str, Form()] = "",
            title_font: Annotated[str, Form()] = "",
            text_font: Annotated[str, Form()] = "",
            title_size: Annotated[int, Form()] = 0,
            text_size: Annotated[int, Form()] = 0,
            graph_labels: Annotated[int, Form()] = 0,
            title_effect: Annotated[str, Form()] = "",
        ) -> Response:
            quiet = _wants_json(request)
            if not self._form_ok(request, csrf):
                if quiet:
                    return JSONResponse({"ok": False, "error": "form"}, status_code=403)
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
                site_name=clean_text(site_name)[:MAX_NAME],
                title_font=title_font_named(title_font, now.title_font),
                text_font=text_font_named(text_font, now.text_font),
                title_size=in_range(title_size, TITLE_SIZE_MIN, TITLE_SIZE_MAX, now.title_size),
                text_size=in_range(text_size, TEXT_SIZE_MIN, TEXT_SIZE_MAX, now.text_size),
                graph_labels=in_range(
                    graph_labels, LABEL_SIZE_MIN, LABEL_SIZE_MAX, now.graph_labels
                ),
                title_effect=title_effect_named(title_effect, now.title_effect),
            )
            self.store.save(chosen)
            if quiet:
                # The page saved itself (autosave): it repaints the background in place.
                ramp = chosen.colors.ramp if chosen.recolors else None
                backdrop = {
                    "url": background_url(chosen),
                    "soil": chosen.soil,
                    "ramp": " ".join(ramp) if ramp else "",
                }
                return JSONResponse({"ok": True, "backdrop": backdrop})
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


def _wants_json(request: Request) -> bool:
    """The Appearance page's own script saving a change, not a plain form post."""
    return "application/json" in request.headers.get("accept", "")


def _back(*, done: str = "", error: str = "") -> Response:
    """Back to the page with a message (post, redirect, get)."""
    target = "/appearance" + (f"?error={error}" if error else f"?done={done}")
    return RedirectResponse(target, status_code=303)
