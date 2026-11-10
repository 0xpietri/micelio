"""Nodes and edges for ``/api/graph``, independent of any renderer.

The payload is plain data: a 2D page draws it with Cytoscape.js today and a 3D view
can read the same JSON later. Colors, shapes and fading are decided by the page; the
API only says what a node is (``type``, ``category``, ``status``, ``degree``, ...).
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Literal, TypedDict

from mycelium.appearance import PALETTES, category_colors
from mycelium.config import Config
from mycelium.i18n import category_names
from mycelium.render import href_for
from mycelium.vault.index import IndexView, Note
from mycelium.vault.parser import link_key

GHOST_PREFIX = "ghost:"

ScopeKind = Literal["all", "project", "note"]


class NodeData(TypedDict):
    id: str
    title: str
    type: str
    category: str | None
    categories: list[str]
    bridge: bool
    status: str | None
    degree: int
    public: bool
    href: str | None
    ghost: bool
    faded: bool
    focus: bool


class EdgeData(TypedDict):
    id: str
    source: str
    target: str
    faded: bool


class CategoryData(TypedDict):
    key: str
    name: str
    color: str


class GraphData(TypedDict):
    scope: str
    nodes: list[NodeData]
    edges: list[EdgeData]
    categories: list[CategoryData]
    hidden_types: list[str]


class ScopeError(ValueError):
    """The ``scope`` parameter is not ``all``, ``project:<slug>`` or ``note:<slug>``."""


class UnknownNodeError(LookupError):
    """The scope names a note or project that does not exist."""


@dataclass(frozen=True, slots=True)
class Scope:
    kind: ScopeKind
    slug: str = ""

    def __str__(self) -> str:
        return self.kind if self.kind == "all" else f"{self.kind}:{self.slug}"


def parse_scope(raw: str) -> Scope:
    raw = raw.strip()
    if raw == "all":
        return Scope("all")
    kind, sep, slug = raw.partition(":")
    if sep and slug and kind in ("project", "note"):
        return Scope("project" if kind == "project" else "note", slug)
    raise ScopeError(raw)


def ghost_id(target: str) -> str:
    return GHOST_PREFIX + link_key(target)


class GraphBuilder:
    def __init__(
        self,
        config: Config,
        index: IndexView,
        colors: Callable[[], dict[str, str]] | None = None,
    ) -> None:
        self.config = config
        self.index = index
        self.colors = colors or (lambda: category_colors(config, PALETTES[config.landing.palette]))

    # -- pieces --------------------------------------------------------------------

    def _degree(self, slug: str) -> int:
        index = self.index
        return len(index.outlinks.get(slug, ())) + len(index.backlinks.get(slug, ()))

    def _node(self, note: Note, *, faded: bool = False, focus: bool = False) -> NodeData:
        categories = sorted(self.index.categories_of(note.slug))
        return {
            "id": note.slug,
            "title": note.title,
            "type": note.type,
            "category": categories[0] if len(categories) == 1 else None,
            "categories": categories,
            "bridge": len(categories) > 1,
            "status": note.status,
            "degree": self._degree(note.slug),
            "public": note.public,
            "href": href_for(note),
            "ghost": False,
            "faded": faded,
            "focus": focus,
        }

    def _ghost(self, target: str) -> NodeData:
        return {
            "id": ghost_id(target),
            "title": target,
            "type": "ghost",
            "category": None,
            "categories": [],
            "bridge": False,
            "status": None,
            "degree": len(self.index.ghosts.get(target, ())),
            "public": False,
            "href": None,
            "ghost": True,
            "faded": False,
            "focus": False,
        }

    def _categories(self) -> list[CategoryData]:
        language = self.config.site.language
        names = category_names(language)
        colors = self.colors()
        return [
            {"key": c.key, "name": c.name(language, names.get(c.key)), "color": colors[c.key]}
            for c in self.config.categories
        ]

    # -- scopes --------------------------------------------------------------------

    def build(self, scope: Scope) -> GraphData:
        if scope.kind != "all":
            note = self.index.notes.get(scope.slug)
            if note is None or (scope.kind == "project") != (note.type == "project"):
                raise UnknownNodeError(str(scope))
        if scope.kind == "all":
            nodes, edges = self._all()
        elif scope.kind == "project":
            nodes, edges = self._project(scope.slug)
        else:
            nodes, edges = self._neighborhood(scope.slug)
        return {
            "scope": str(scope),
            "nodes": nodes,
            "edges": edges,
            "categories": self._categories(),
            "hidden_types": list(self.config.graph.hide_by_default) if scope.kind == "all" else [],
        }

    def _assemble(
        self,
        slugs: set[str],
        *,
        faded: AbstractSet[str] = frozenset(),
        focus: str | None = None,
        ghost_sources: AbstractSet[str] | None = None,
    ) -> tuple[list[NodeData], list[EdgeData]]:
        """Nodes for ``slugs`` and every edge among them, plus ghosts linked from
        ``ghost_sources``. An edge touching a faded node is faded too."""
        notes = self.index.notes
        everyone = slugs | set(faded)
        nodes = [
            self._node(notes[s], faded=s in faded, focus=s == focus)
            for s in sorted(everyone, key=lambda s: (notes[s].type, notes[s].title.lower(), s))
        ]
        edges: list[EdgeData] = [
            {
                "id": f"{e.source}->{e.target}",
                "source": e.source,
                "target": e.target,
                "faded": e.source in faded or e.target in faded,
            }
            for e in self.index.edges
            if e.source in everyone
            and e.target in everyone
            # Two faded neighbours of a project are not part of its story.
            and not (e.source in faded and e.target in faded)
        ]
        sources = everyone if ghost_sources is None else ghost_sources
        seen: set[str] = set()
        for target, linked_from in sorted(self.index.ghosts.items()):
            hits = sorted(linked_from & sources)
            if not hits:
                continue
            gid = ghost_id(target)
            if gid not in seen:
                seen.add(gid)
                nodes.append(self._ghost(target))
            edges.extend(
                {"id": f"{s}->{gid}", "source": s, "target": gid, "faded": s in faded} for s in hits
            )
        return nodes, edges

    def _all(self) -> tuple[list[NodeData], list[EdgeData]]:
        return self._assemble(set(self.index.notes))

    def _project(self, slug: str) -> tuple[list[NodeData], list[EdgeData]]:
        """The index note, its notes, the links among them and, faded, the other
        projects its notes also belong to (the bridges out)."""
        members = self.index.members.get(slug, set())
        core = {slug, *members}
        others = {
            project
            for member in members
            for project in self.index.projects_of.get(member, ())
            if project != slug
        }
        return self._assemble(core, faded=others - core, focus=slug, ghost_sources=core)

    def _neighborhood(self, slug: str) -> tuple[list[NodeData], list[EdgeData]]:
        """The note and everything one link away, either direction."""
        around = {
            slug,
            *self.index.outlinks.get(slug, ()),
            *self.index.backlinks.get(slug, ()),
        }
        return self._assemble(around, focus=slug, ghost_sources={slug})
