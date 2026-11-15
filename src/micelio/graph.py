"""Nodes and edges for ``/api/graph``, independent of any renderer.

The payload is plain data: a 2D page draws it as mycelium in SVG today and a 3D view
can read the same JSON later. Colors, shapes and fading are decided by the page; the
API only says what a node is (``type``, ``category``, ``status``, ``degree``, ...).
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Literal, TypedDict

from micelio.appearance import PALETTES, category_colors
from micelio.config import Config
from micelio.i18n import active_language, category_names
from micelio.looks import Look
from micelio.render import href_for
from micelio.vault.index import IndexView, Note
from micelio.vault.parser import link_key

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
    tags: list[str]
    degree: int
    public: bool
    href: str | None
    ghost: bool
    faded: bool
    focus: bool
    look: Look | None


class EdgeData(TypedDict):
    id: str
    source: str
    target: str
    faded: bool
    # In a project's scope, the threads of its mycelium: one per note, branching from the
    # project through its most linked notes. The page draws only these until asked for
    # every connection. Every edge of the other scopes is part of it.
    spine: bool
    # The two notes link each other: drawn as one thread, read both ways.
    both: bool


class CategoryData(TypedDict):
    key: str
    name: str
    color: str
    species: str


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
        dress: Callable[[], dict[str, Look]] | None = None,
    ) -> None:
        self.config = config
        self.index = index
        self.colors = colors or (lambda: category_colors(config, PALETTES[config.landing.palette]))
        # How the owner dressed projects and sources (looks.py), read once per build.
        self.dress = dress or dict
        self._dressed: dict[str, Look] = {}

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
            "tags": list(note.tags),
            "degree": self._degree(note.slug),
            "public": note.public,
            "href": href_for(note),
            "ghost": False,
            "faded": faded,
            "focus": focus,
            "look": self._dressed.get(note.slug) if note.type in ("project", "source") else None,
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
            "tags": [],
            "degree": len(self.index.ghosts.get(target, ())),
            "public": False,
            "href": None,
            "ghost": True,
            "faded": False,
            "focus": False,
            "look": None,
        }

    def _categories(self) -> list[CategoryData]:
        language = active_language(self.config.site.language)
        names = category_names(language)
        colors = self.colors()
        return [
            {
                "key": c.key,
                "name": c.name(language, names.get(c.key)),
                "color": colors[c.key],
                "species": c.species,
            }
            for c in self.config.categories
        ]

    # -- scopes --------------------------------------------------------------------

    def build(self, scope: Scope) -> GraphData:
        self._dressed = self.dress()
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
        # One thread per pair: a note that links back to its project (or any two notes
        # that link each other) would otherwise be drawn twice, one over the other.
        # The direction kept starts at the project, else at the first link found.
        pairs: dict[frozenset[str], tuple[str, str]] = {}
        seen_ways: set[tuple[str, str]] = set()
        for e in self.index.edges:
            if e.source not in everyone or e.target not in everyone:
                continue
            # Two faded neighbours of a project are not part of its story.
            if e.source in faded and e.target in faded:
                continue
            seen_ways.add((e.source, e.target))
            key = frozenset((e.source, e.target))
            if key not in pairs or (
                notes[e.source].type == "project" and notes[e.target].type != "project"
            ):
                pairs[key] = (e.source, e.target)
        edges: list[EdgeData] = [
            {
                "id": f"{source}->{target}",
                "source": source,
                "target": target,
                "faded": source in faded or target in faded,
                "spine": True,
                "both": (target, source) in seen_ways,
            }
            for source, target in pairs.values()
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
                {
                    "id": f"{h}->{gid}",
                    "source": h,
                    "target": gid,
                    "faded": h in faded,
                    "spine": True,
                    "both": False,
                }
                for h in hits
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
        nodes, edges = self._assemble(core, faded=others - core, focus=slug, ghost_sources=core)
        mark_spine(slug, nodes, edges)
        return nodes, edges

    def _neighborhood(self, slug: str) -> tuple[list[NodeData], list[EdgeData]]:
        """The note and everything one link away, either direction."""
        around = {
            slug,
            *self.index.outlinks.get(slug, ()),
            *self.index.backlinks.get(slug, ()),
        }
        return self._assemble(around, focus=slug, ghost_sources={slug})


def mark_spine(root: str, nodes: list[NodeData], edges: list[EdgeData]) -> None:
    """Keep one thread per note of a project, so its underground reads as a mycelium
    rather than a hairball. The project feeds its most linked notes (about the square
    root of their number); every other note hangs from its most linked neighbour that is
    already on the mycelium, else from the project. A ghost's thread is left out, and each
    other project keeps a single thread: the one to its most linked bridge note."""
    ghosts = {n["id"] for n in nodes if n["ghost"]}
    faded = {n["id"] for n in nodes if n["faded"]}
    near: dict[str, set[str]] = {n["id"]: set() for n in nodes if n["id"] not in ghosts | faded}
    for e in edges:
        a, b = e["source"], e["target"]
        if a in near and b in near:
            near[a].add(b)
            near[b].add(a)

    def degree(slug: str) -> int:
        return len(near[slug] - {root})

    notes = sorted((s for s in near if s != root), key=lambda s: (-degree(s), s))
    hubs = max(3, round(len(notes) ** 0.5))
    placed = {root}
    kept: set[frozenset[str]] = set()

    def attach(slug: str, parent: str) -> None:
        placed.add(slug)
        kept.add(frozenset((slug, parent)))

    waiting = notes
    while waiting:
        later: list[str] = []
        for slug in waiting:
            on = sorted(near[slug] & placed - {root}, key=lambda p: (-degree(p), p))
            if root in near[slug] and (len(placed) <= hubs or not on):
                attach(slug, root)
            elif on:
                attach(slug, on[0])
            else:
                later.append(slug)
        if len(later) == len(waiting):
            # Linked to the project's notes only through each other: start a strand anyway.
            first = later.pop(0)
            if near[first]:
                attach(first, min(near[first]))
            else:
                placed.add(first)
        waiting = later

    bridges: dict[str, list[str]] = {}
    for e in edges:
        a, b = e["source"], e["target"]
        if a in faded and b in near:
            bridges.setdefault(a, []).append(b)
        elif b in faded and a in near:
            bridges.setdefault(b, []).append(a)
    for other, members in bridges.items():
        kept.add(frozenset((other, min(members, key=lambda m: (-degree(m), m)))))
    for e in edges:
        e["spine"] = frozenset((e["source"], e["target"])) in kept
