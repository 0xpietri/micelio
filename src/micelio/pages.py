"""The reading pages: projects, notes, journal, the graph and the health of the vault."""

from __future__ import annotations

import hashlib
import hmac
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from micelio.appearance import Appearance, AppearanceStore, category_colors, palette_named
from micelio.auth.web import SignIn
from micelio.config import NOTE_TYPES, STATUSES, Category, Config
from micelio.formatting import Dates
from micelio.graph import GraphBuilder, ScopeError, UnknownNodeError, parse_scope
from micelio.growth import growth
from micelio.i18n import active_language, category_names
from micelio.landing import background_url
from micelio.looks import Look, NodeLooks, clean_look
from micelio.render import Renderer, href_for
from micelio.sharing import SharedProjects
from micelio.vault.index import IndexView, Note, VaultIndex
from micelio.vault.public import PublicView

_STATUS_ORDER = {status: i for i, status in enumerate(("active", "draft", "paused", "closed"))}


@dataclass(frozen=True, slots=True)
class ProjectRow:
    note: Note
    members: int
    last_journal: Note | None
    last_date: date | None


@dataclass(frozen=True, slots=True)
class CategoryGroup:
    category: Category | None
    projects: list[ProjectRow]


@dataclass(frozen=True, slots=True)
class Reader:
    """One way of seeing the vault: all of it, or only its public notes (§9)."""

    vault: IndexView
    renderer: Renderer
    graphs: GraphBuilder


# How each title effect is drawn, as custom properties (static/css/micelio.css reads
# them; appearance.js, look.js and look-early.js hold the same table for live previews).
_NO_PLATE = {
    "title-plate-bg": "transparent",
    "title-plate-border": "0 solid transparent",
    "title-plate-shadow": "none",
    "title-plate-pad": "0",
}
TITLE_LOOKS: dict[str, dict[str, str]] = {
    "poster": {
        "title-stroke": "0.08em",
        "title-shadow": "0.05em 0.06em 0 var(--pal-accent)",
        **_NO_PLATE,
    },
    "plain": {"title-stroke": "0", "title-shadow": "none", **_NO_PLATE},
    "sign": {
        "title-stroke": "0",
        "title-shadow": "none",
        "title-plate-bg": "color-mix(in srgb, var(--pal-ink) 88%, transparent)",
        "title-plate-border": "2px solid color-mix(in srgb, var(--pal-sun) 55%, var(--pal-ink))",
        "title-plate-shadow": (
            "0.1em 0.1em 0 color-mix(in srgb, var(--pal-accent) 80%, var(--pal-ink))"
        ),
        "title-plate-pad": "0.1em 0.42em 0.14em",
    },
}


def theme_css(colors: dict[str, str], appearance: Appearance) -> str:
    """The palette, the type settings and the category colors as CSS custom properties,
    so pages need no inline styles (CSP). Font stacks live in ``static/css/fonts.css``."""
    palette = appearance.colors
    tokens = {
        "sun": palette.sun,
        "accent": palette.accent,
        "button": palette.button,
        "button-alt": palette.button_alt,
        "ink": palette.ink,
        "thread": palette.thread,
        "stem": palette.stem,
        "spore": palette.spore,
        "crystal": palette.crystals[0],
        "crystal-alt": palette.crystals[1],
    }
    look = {
        "title-font": f"var(--font-{appearance.title_font})",
        "text-font": f"var(--font-{appearance.text_font})",
        "title-scale": f"{appearance.title_size / 100:g}",
        "text-size": f"{appearance.text_size}px",
        "label-scale": f"{appearance.graph_labels / 100:g}",
        **TITLE_LOOKS[appearance.title_effect],
    }
    rules = [":root { " + " ".join(f"--pal-{k}: {v};" for k, v in tokens.items()) + " }"]
    rules += [":root { " + " ".join(f"--{k}: {v};" for k, v in look.items()) + " }"]
    rules += [f".cat-{key} {{ --cat: {color}; }}" for key, color in colors.items()]
    return "\n".join(rules) + "\n"


class Pages:
    def __init__(
        self,
        config: Config,
        index: VaultIndex,
        templates: Jinja2Templates,
        dates: Dates,
        looks: AppearanceStore,
        sign_in: SignIn,
        public: PublicView,
    ) -> None:
        self.config = config
        self.looks = looks
        self.node_looks = NodeLooks(looks)
        self.shared = SharedProjects(looks)
        self.index = index
        self.templates = templates
        self.dates = dates
        self.sign_in = sign_in
        dress = self.node_looks.all
        self.everything = Reader(
            index, Renderer(index), GraphBuilder(config, index, self.colors, dress)
        )
        self.public = Reader(
            public, Renderer(public, ghosts=False), GraphBuilder(config, public, self.colors, dress)
        )
        templates.env.globals.update(
            href=href_for,
            show_date=dates.show,
            short_date=dates.short,
            created=dates.created,
            updated=dates.updated,
            category_of=self.category_of,
            category_name=self.category_name,
            excerpt=self.everything.renderer.excerpt,
            backdrop=self.backdrop,
            looks_token=self.looks_token,
            node_look=self.node_look,
            share_switch=self.share_switch,
            is_shared=self.is_shared,
            theme_version=self.theme_version,
        )

    # -- helpers ---------------------------------------------------------------------

    def node_look(self, slug: str) -> Look:
        return self.node_looks.get(slug) or {}

    def share_switch(self, request: Request, note: Note) -> dict[str, object] | None:
        """The Share switch on a project's page (§9). The owner can flip it; a visitor only
        ever sees it shared (a private project is not there for them) and cannot touch it."""
        if note.type != "project":
            return None
        if not self.sign_in.sees_everything(request):
            return {"owner": False, "shared": True, "in_note": False, "token": ""}
        return {
            "owner": True,
            "shared": self.shared.is_shared(note.slug),
            # Public in its own frontmatter: shown, and visitors already see it.
            "in_note": note.public,
            "token": self.sign_in.form_token(request, "share"),
        }

    def is_shared(self, note: Note) -> bool:
        """Visitors can read this project: shared from the site or public in its note."""
        return note.public or self.shared.is_shared(note.slug)

    def theme_version(self) -> str:
        """A short fingerprint of the theme, so ``/theme.css?v=…`` is a new address after
        every Appearance change: a cache in front (Cloudflare) can never serve old colors."""
        look = self.looks.current()
        css = theme_css(category_colors(self.config, look.colors), look)
        return hashlib.sha256(css.encode("utf-8")).hexdigest()[:10]

    def looks_token(self, request: Request) -> str:
        """The owner's key for dressing nodes; empty for visitors, who only look."""
        if not self.sign_in.sees_everything(request):
            return ""
        return self.sign_in.form_token(request, "looks")

    def colors(self) -> dict[str, str]:
        """Category colors from the palette chosen on the Appearance page (§7b)."""
        return category_colors(self.config, self.looks.current().colors)

    def look_for(self, palette: str) -> Appearance:
        """The saved look, or with a visitor's own palette (§7b, kept in their browser).
        Only a known palette name is taken; anything else is the owner's look."""
        look = self.looks.current()
        return replace(look, palette=palette_named(palette, look.palette)) if palette else look

    def backdrop(self) -> dict[str, object]:
        """The painted background behind every page (§7c): the image, its soil line and,
        when it is recolored, the palette's ramp for the browser's SVG filter."""
        look = self.looks.current()
        ramp = look.colors.ramp if look.recolors else None
        return {
            "url": background_url(look),
            "soil": look.soil,
            "ramp": " ".join(ramp) if ramp else "",
        }

    def category_of(self, key: str | None) -> Category | None:
        return self.config.category(key)

    def category_name(self, category: Category) -> str:
        language = active_language(self.config.site.language)
        return category.name(language, category_names(language).get(category.key))

    def reader(self, request: Request) -> Reader:
        """The whole vault when signed in, the public notes otherwise (§9). Refreshed."""
        reader = self.everything if self.sign_in.sees_everything(request) else self.public
        reader.vault.refresh()
        return reader

    def _note(self, vault: IndexView, slug: str) -> Note:
        note = vault.notes.get(slug)
        if note is None:
            raise HTTPException(status_code=404)
        return note

    def _journals_touching(self, vault: IndexView, slugs: set[str]) -> list[Note]:
        journals = [
            n
            for n in vault.notes.values()
            if n.type == "journal" and vault.outlinks.get(n.slug, set()) & slugs
        ]
        return sorted(journals, key=lambda n: (self.dates.created(n), n.slug), reverse=True)

    def _project_row(self, vault: IndexView, project: Note) -> ProjectRow:
        members = vault.members.get(project.slug, set())
        notes = {m for m in members if vault.notes[m].type != "journal"}
        journals = self._journals_touching(vault, {project.slug, *members})
        last = journals[0] if journals else None
        return ProjectRow(project, len(notes), last, self.dates.created(last) if last else None)

    def _groups(self, vault: IndexView) -> list[CategoryGroup]:
        rows: dict[str | None, list[ProjectRow]] = {}
        for project in vault.projects():
            rows.setdefault(project.category, []).append(self._project_row(vault, project))
        groups = []
        for category in [*self.config.categories, None]:
            projects = rows.get(category.key if category else None, [])
            if projects:
                projects.sort(
                    key=lambda r: (_STATUS_ORDER.get(r.note.status or "", 9), r.note.title.lower())
                )
                groups.append(CategoryGroup(category, projects))
        return groups

    # -- routes ------------------------------------------------------------------------

    def router(self) -> APIRouter:
        router = APIRouter()

        def render(
            request: Request, name: str, context: Mapping[str, object], reader: Reader
        ) -> Response:
            return self.templates.TemplateResponse(
                request, name, {**context, "vault": reader.vault}
            )

        @router.get("/theme.css", include_in_schema=False)
        def theme(palette: str = Query("", max_length=40)) -> Response:
            look = self.look_for(palette)
            return PlainTextResponse(
                theme_css(category_colors(self.config, look.colors), look),
                media_type="text/css",
                # Never kept by a shared cache: the address changes with the theme anyway.
                headers={"Cache-Control": "private, no-cache", "CDN-Cache-Control": "no-store"},
            )

        @router.get("/projects", include_in_schema=False)
        def projects(request: Request) -> Response:
            reader = self.reader(request)
            context = {"groups": self._groups(reader.vault), "nav": "projects"}
            return render(request, "projects.html", context, reader)

        @router.get("/projects/{slug}", include_in_schema=False)
        def project(request: Request, slug: str) -> Response:
            reader = self.reader(request)
            vault = reader.vault
            note = self._note(vault, slug)
            if note.type != "project":
                return RedirectResponse(href_for(note), status_code=308)
            member_slugs = vault.members.get(slug, set())
            members = sorted(
                (vault.notes[m] for m in member_slugs),
                key=lambda n: (n.type != "note", n.title.lower()),
            )
            context = {
                "note": note,
                "body": reader.renderer.html(note),
                "members": [m for m in members if m.type != "journal"],
                "journals": self._journals_touching(vault, {slug, *member_slugs})[:10],
                "growth": growth(
                    [note, *(m for m in members if m.type != "journal")],
                    self._journals_touching(vault, {slug, *member_slugs}),
                    self.dates.created,
                    self.dates.updated,
                    datetime.now(self.dates.zone).date(),
                ),
                "nav": "projects",
            }
            return render(request, "project.html", context, reader)

        @router.get("/notes/{slug}", include_in_schema=False)
        def note_page(request: Request, slug: str) -> Response:
            reader = self.reader(request)
            vault = reader.vault
            note = self._note(vault, slug)
            if note.type == "project":
                return RedirectResponse(href_for(note), status_code=308)
            backlinks = sorted(
                (vault.notes[s] for s in vault.backlinks.get(slug, set())),
                key=lambda n: n.title.lower(),
            )
            projects = sorted(
                (vault.notes[s] for s in vault.projects_of.get(slug, set())),
                key=lambda n: n.title.lower(),
            )
            context = {
                "note": note,
                "body": reader.renderer.html(note),
                "backlinks": [b for b in backlinks if b.type != "project"],
                "projects": projects,
                "nav": "journal" if note.type == "journal" else "",
            }
            return render(request, "note.html", context, reader)

        @router.get("/journal", include_in_schema=False)
        def journal(request: Request) -> Response:
            reader = self.reader(request)
            entries = sorted(
                (n for n in reader.vault.notes.values() if n.type == "journal"),
                key=lambda n: (self.dates.created(n), n.slug),
                reverse=True,
            )
            return render(request, "journal.html", {"entries": entries, "nav": "journal"}, reader)

        @router.post("/api/looks/{slug}", include_in_schema=False)
        async def dress(request: Request, slug: str) -> Response:
            """The owner dresses a project or a source (§7c): kept in the data folder."""
            if not self.sign_in.sees_everything(request):
                raise HTTPException(status_code=404)
            token = request.headers.get("x-micelio-form", "")
            if not hmac.compare_digest(token, self.sign_in.form_token(request, "looks")):
                return JSONResponse({"ok": False, "error": "form"}, status_code=403)
            self.index.refresh()
            note = self.index.notes.get(slug)
            if note is None or note.type not in ("project", "source"):
                raise HTTPException(status_code=404)
            try:
                body: object = await request.json()
            except ValueError:
                body = None
            look = clean_look(body, note.type)
            self.node_looks.save(slug, look)
            return JSONResponse({"ok": True, "look": look})

        @router.post("/projects/{slug}/share", include_in_schema=False)
        def share(
            request: Request,
            slug: str,
            csrf: Annotated[str, Form()] = "",
            shared: Annotated[str, Form()] = "",
        ) -> Response:
            """The owner shares a project with visitors, or makes it private again (§9).
            Kept in the data folder; the vault is never written."""
            if not self.sign_in.sees_everything(request):
                raise HTTPException(status_code=404)
            if not hmac.compare_digest(csrf, self.sign_in.form_token(request, "share")):
                raise HTTPException(status_code=403)
            self.index.refresh()
            note = self.index.notes.get(slug)
            if note is None or note.type != "project":
                raise HTTPException(status_code=404)
            self.shared.set(slug, shared == "on")
            return RedirectResponse(href_for(note), status_code=303)

        @router.get("/api/graph", include_in_schema=False)
        def graph(
            request: Request,
            scope: str = Query("all", max_length=300),
            palette: str = Query("", max_length=40),
        ) -> Response:
            reader = self.reader(request)
            try:
                data = reader.graphs.build(parse_scope(scope))
            except ScopeError:
                return JSONResponse(
                    {"error": "scope must be all, project:<slug> or note:<slug>"},
                    status_code=400,
                )
            except UnknownNodeError:
                return JSONResponse({"error": "not found"}, status_code=404)
            if palette:
                colors = category_colors(self.config, self.look_for(palette).colors)
                for category in data["categories"]:
                    category["color"] = colors[category["key"]]
            return JSONResponse(dict(data), headers={"Cache-Control": "no-store"})

        @router.get("/explore", include_in_schema=False)
        def explore(request: Request) -> Response:
            reader = self.reader(request)
            vault = reader.vault
            notes = sorted(vault.notes.values(), key=lambda n: (n.title.lower(), n.slug))
            journals = sorted(
                (n for n in notes if n.type == "journal"),
                key=lambda n: (self.dates.created(n), n.slug),
                reverse=True,
            )
            context = {
                "notes": notes,
                "journals": journals[:5],
                "types": [*NOTE_TYPES, "ghost"] if vault.ghosts else list(NOTE_TYPES),
                "hidden_types": set(self.config.graph.hide_by_default),
                "statuses": STATUSES,
                "site_categories": self.config.categories,
                "max_nodes": self.config.graph.max_nodes,
                "nav": "explore",
            }
            return render(request, "explore.html", context, reader)

        @router.get("/health", include_in_schema=False)
        def health(request: Request) -> Response:
            if not self.sign_in.sees_everything(request):  # signed-in only, never public
                raise HTTPException(status_code=404)
            reader = self.everything
            self.index.refresh()
            issues = sorted(self.index.issues, key=lambda i: (i.kind, i.path))
            counts = Counter(n.type for n in self.index.notes.values())
            context = {
                "issues": issues,
                "orphans": [self.index.notes[s] for s in self.index.orphans()],
                "counts": counts,
                "total": len(self.index.notes),
                "links": len(self.index.edges),
                "statuses": STATUSES,
                "nav": "health",
            }
            return render(request, "health.html", context, reader)

        return router
