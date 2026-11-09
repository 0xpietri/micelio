"""The reading pages: projects, notes, journal and the health of the vault."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from mycelium.config import STATUSES, Category, Config
from mycelium.formatting import Dates
from mycelium.render import Renderer, href_for
from mycelium.vault.index import Note, VaultIndex

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


def theme_css(config: Config) -> str:
    """Category colors as CSS classes, so pages need no inline styles (CSP)."""
    rules = [f".cat-{c.key} {{ --cat: {c.color}; }}" for c in config.categories]
    return "\n".join(rules) + "\n"


class Pages:
    def __init__(
        self, config: Config, index: VaultIndex, templates: Jinja2Templates, dates: Dates
    ) -> None:
        self.config = config
        self.index = index
        self.templates = templates
        self.dates = dates
        self.renderer = Renderer(index)
        templates.env.globals.update(
            href=href_for,
            show_date=dates.show,
            created=dates.created,
            updated=dates.updated,
            category_of=self.category_of,
            excerpt=self.renderer.excerpt,
            is_bridge=index.is_bridge,
            categories_of=index.categories_of,
        )
        self._theme = theme_css(config)

    # -- helpers ---------------------------------------------------------------------

    def category_of(self, key: str | None) -> Category | None:
        return self.config.category(key)

    def _note(self, slug: str) -> Note:
        self.index.refresh()
        note = self.index.notes.get(slug)
        if note is None:
            raise HTTPException(status_code=404)
        return note

    def _journals_touching(self, slugs: set[str]) -> list[Note]:
        journals = [
            n
            for n in self.index.notes.values()
            if n.type == "journal" and self.index.outlinks.get(n.slug, set()) & slugs
        ]
        return sorted(journals, key=lambda n: (self.dates.created(n), n.slug), reverse=True)

    def _project_row(self, project: Note) -> ProjectRow:
        members = self.index.members.get(project.slug, set())
        notes = {m for m in members if self.index.notes[m].type != "journal"}
        journals = self._journals_touching({project.slug, *members})
        last = journals[0] if journals else None
        return ProjectRow(project, len(notes), last, self.dates.created(last) if last else None)

    def _groups(self) -> list[CategoryGroup]:
        rows: dict[str | None, list[ProjectRow]] = {}
        for project in self.index.projects():
            rows.setdefault(project.category, []).append(self._project_row(project))
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
        render = self.templates.TemplateResponse

        @router.get("/theme.css", include_in_schema=False)
        def theme() -> Response:
            return PlainTextResponse(
                self._theme,
                media_type="text/css",
                headers={"Cache-Control": "no-cache"},
            )

        @router.get("/projects", include_in_schema=False)
        def projects(request: Request) -> Response:
            self.index.refresh()
            return render(request, "projects.html", {"groups": self._groups(), "nav": "projects"})

        @router.get("/projects/{slug}", include_in_schema=False)
        def project(request: Request, slug: str) -> Response:
            note = self._note(slug)
            if note.type != "project":
                return RedirectResponse(href_for(note), status_code=308)
            member_slugs = self.index.members.get(slug, set())
            members = sorted(
                (self.index.notes[m] for m in member_slugs),
                key=lambda n: (n.type != "note", n.title.lower()),
            )
            context = {
                "note": note,
                "body": self.renderer.html(note),
                "members": [m for m in members if m.type != "journal"],
                "journals": self._journals_touching({slug, *member_slugs})[:10],
                "nav": "projects",
            }
            return render(request, "project.html", context)

        @router.get("/notes/{slug}", include_in_schema=False)
        def note_page(request: Request, slug: str) -> Response:
            note = self._note(slug)
            if note.type == "project":
                return RedirectResponse(href_for(note), status_code=308)
            backlinks = sorted(
                (self.index.notes[s] for s in self.index.backlinks.get(slug, set())),
                key=lambda n: n.title.lower(),
            )
            projects = sorted(
                (self.index.notes[s] for s in self.index.projects_of.get(slug, set())),
                key=lambda n: n.title.lower(),
            )
            context = {
                "note": note,
                "body": self.renderer.html(note),
                "backlinks": [b for b in backlinks if b.type != "project"],
                "projects": projects,
                "nav": "journal" if note.type == "journal" else "",
            }
            return render(request, "note.html", context)

        @router.get("/journal", include_in_schema=False)
        def journal(request: Request) -> Response:
            self.index.refresh()
            entries = sorted(
                (n for n in self.index.notes.values() if n.type == "journal"),
                key=lambda n: (self.dates.created(n), n.slug),
                reverse=True,
            )
            return render(request, "journal.html", {"entries": entries, "nav": "journal"})

        @router.get("/health", include_in_schema=False)
        def health(request: Request) -> Response:
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
            return render(request, "health.html", context)

        return router
