"""What the landing draws (§7a), as plain JSON for ``/api/landing``.

Projects become mushrooms, notes knots in the mycelium, links hyphae, sources crystals
and the latest journal notes spores. The browser decides positions and shapes; this
module only says what exists and how things connect.
"""

from __future__ import annotations

from typing import TypedDict

from mycelium.appearance import BUILTIN_BACKGROUND, Appearance, category_colors
from mycelium.config import Config
from mycelium.render import href_for
from mycelium.vault.index import IndexView, Note

SPORES = 5
UNCATEGORIZED_SPECIES = "glowing-bonnets"


class ProjectData(TypedDict):
    id: str
    title: str
    href: str
    category: str | None
    species: str
    color: str
    status: str
    notes: int


class NoteData(TypedDict):
    id: str
    title: str
    href: str
    projects: list[str]
    degree: int


class LinkedData(TypedDict):
    id: str
    title: str
    href: str
    links: list[str]


class BackgroundData(TypedDict):
    url: str
    recolor: bool
    soil: int


class LandingData(TypedDict):
    projects: list[ProjectData]
    notes: list[NoteData]
    links: list[list[str]]
    sources: list[LinkedData]
    journal: list[LinkedData]
    hidden: int
    palette: dict[str, object]
    background: BackgroundData


def background_url(appearance: Appearance) -> str:
    if appearance.uses_own:
        return f"/appearance/background?v={appearance.own_version}"
    return f"/static/{BUILTIN_BACKGROUND}"


class LandingBuilder:
    def __init__(self, config: Config, index: IndexView) -> None:
        self.config = config
        self.index = index

    def _degree(self, slug: str) -> int:
        return len(self.index.outlinks.get(slug, ())) + len(self.index.backlinks.get(slug, ()))

    def _neighbours(self, slug: str) -> set[str]:
        return self.index.outlinks.get(slug, set()) | self.index.backlinks.get(slug, set())

    def build(self, appearance: Appearance) -> LandingData:
        index = self.index
        palette = appearance.colors
        colors = category_colors(self.config, palette)
        notes = index.notes

        projects: list[ProjectData] = []
        for project in sorted(
            index.projects(), key=lambda n: (n.created or "", n.title.lower(), n.slug)
        ):
            category = self.config.category(project.category)
            members = index.members.get(project.slug, set())
            projects.append(
                {
                    "id": project.slug,
                    "title": project.title,
                    "href": href_for(project),
                    "category": category.key if category else None,
                    "species": category.species if category else UNCATEGORIZED_SPECIES,
                    "color": colors[category.key] if category else palette.spare[3],
                    "status": project.status if project.status in _GROWTH else "active",
                    "notes": sum(1 for m in members if notes[m].type == "note"),
                }
            )
        project_ids = {p["id"] for p in projects}

        # Over the limit, only the most connected notes are drawn (§7a).
        all_notes = [n for n in notes.values() if n.type == "note"]
        all_notes.sort(key=lambda n: (-self._degree(n.slug), n.title.lower(), n.slug))
        drawn = all_notes[: self.config.landing.max_notes]
        drawn.sort(key=lambda n: (n.title.lower(), n.slug))
        drawn_ids = {n.slug for n in drawn}

        note_rows: list[NoteData] = [
            {
                "id": n.slug,
                "title": n.title,
                "href": href_for(n),
                "projects": sorted(index.projects_of.get(n.slug, set()) & project_ids),
                "degree": self._degree(n.slug),
            }
            for n in drawn
        ]
        links = sorted(
            {
                tuple(sorted((e.source, e.target)))
                for e in index.edges
                if e.source in drawn_ids and e.target in drawn_ids
            }
        )

        reachable = drawn_ids | project_ids
        sources: list[LinkedData] = [
            self._linked(n, sorted(self._neighbours(n.slug) & reachable))
            for n in sorted(notes.values(), key=lambda n: (n.title.lower(), n.slug))
            if n.type == "source"
        ]

        journals = sorted(
            (n for n in notes.values() if n.type == "journal"),
            key=lambda n: (n.created or "", n.slug),
            reverse=True,
        )[:SPORES]
        journal = [self._linked(j, self._touched(j, project_ids)) for j in journals]

        return {
            "projects": projects,
            "notes": note_rows,
            "links": [list(pair) for pair in links],
            "sources": sources,
            "journal": journal,
            "hidden": len(all_notes) - len(drawn),
            "palette": palette.to_json(),
            "background": {
                "url": background_url(appearance),
                "recolor": appearance.recolors and palette.ramp is not None,
                "soil": appearance.soil,
            },
        }

    def _touched(self, journal: Note, project_ids: set[str]) -> list[str]:
        """Projects a journal note touched: linked directly or through their notes."""
        touched: set[str] = set()
        for slug in self._neighbours(journal.slug):
            if slug in project_ids:
                touched.add(slug)
            touched |= self.index.projects_of.get(slug, set()) & project_ids
        return sorted(touched)

    @staticmethod
    def _linked(note: Note, links: list[str]) -> LinkedData:
        return {"id": note.slug, "title": note.title, "href": href_for(note), "links": links}


_GROWTH = frozenset({"draft", "active", "paused", "closed"})
