"""The reading pages: projects, notes, journal, the graph and the health of the vault."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from mycelium.appearance import AppearanceStore, Palette, category_colors
from mycelium.auth.web import SignIn
from mycelium.config import NOTE_TYPES, STATUSES, Category, Config
from mycelium.formatting import Dates
from mycelium.graph import GraphBuilder, ScopeError, UnknownNodeError, parse_scope
from mycelium.i18n import category_names
from mycelium.render import Renderer, href_for
from mycelium.vault.index import IndexView, Note, VaultIndex
from mycelium.vault.public import PublicView

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


def theme_css(colors: dict[str, str], palette: Palette) -> str:
    """Category colors as CSS classes and the palette as custom properties, so pages
    need no inline styles (CSP)."""
    tokens = {
        "sun": palette.sun,
        "accent": palette.accent,
        "button": palette.button,
        "button-alt": palette.button_alt,
        "ink": palette.ink,
        "thread": palette.thread,
    }
    rules = [":root { " + " ".join(f"--pal-{k}: {v};" for k, v in tokens.items()) + " }"]
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
        self.index = index
        self.templates = templates
        self.dates = dates
        self.sign_in = sign_in
        self.everything = Reader(index, Renderer(index), GraphBuilder(config, index, self.colors))
        self.public = Reader(
            public, Renderer(public, ghosts=False), GraphBuilder(config, public, self.colors)
        )
        templates.env.globals.update(
            href=href_for,
            show_date=dates.show,
            created=dates.created,
            updated=dates.updated,
            category_of=self.category_of,
            category_name=self.category_name,
            excerpt=self.everything.renderer.excerpt,
        )

    # -- helpers ---------------------------------------------------------------------

    def colors(self) -> dict[str, str]:
        """Category colors from the palette chosen on the Appearance page (§7b)."""
        return category_colors(self.config, self.looks.current().colors)

    def category_of(self, key: str | None) -> Category | None:
        return self.config.category(key)

    def category_name(self, category: Category) -> str:
        language = self.config.site.language
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
        def theme() -> Response:
            return PlainTextResponse(
                theme_css(self.colors(), self.looks.current().colors),
                media_type="text/css",
                headers={"Cache-Control": "no-cache"},
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

        @router.get("/api/graph", include_in_schema=False)
        def graph(request: Request, scope: str = Query("all", max_length=300)) -> Response:
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
