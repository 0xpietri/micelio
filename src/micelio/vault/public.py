"""The part of a vault anonymous visitors may see (§9).

``PublicView`` answers the same questions as ``VaultIndex`` but only knows notes with
``public: true``, plus the projects the owner shared from the site and the notes they
link to (``micelio.sharing``). Private notes are not hidden from it, they are absent: no titles, no
links, no counts, no ghosts. Every page built from it therefore cannot leak them, and a
link from a public note to a private one resolves to nothing, so it renders as text.

Ghost nodes (links to missing notes) are left out too. Showing them would tell a visitor
which unresolved links point at nothing and, by elimination, which point at a private note.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from micelio.vault.index import Edge, IndexView, Issue, Note, VaultIndex


class PublicView(IndexView):
    def __init__(self, index: VaultIndex, shared: Callable[[], frozenset[str]] = frozenset) -> None:
        self.index = index
        self.shared = shared
        self._lock = threading.Lock()
        self.generation = -1
        self._shared: frozenset[str] = frozenset()
        self.notes: dict[str, Note] = {}
        self.edges: list[Edge] = []
        self.ghosts: dict[str, set[str]] = {}
        self.backlinks: dict[str, set[str]] = {}
        self.outlinks: dict[str, set[str]] = {}
        self.members: dict[str, set[str]] = {}
        self.projects_of: dict[str, set[str]] = {}
        self.issues: list[Issue] = []
        self._sync()

    def refresh(self, *, force: bool = False) -> bool:
        changed = self.index.refresh(force=force)
        return self._sync() or changed

    def _sync(self) -> bool:
        """Rebuild from the index when it, or the shared projects, changed since the last look."""
        shared = self.shared()
        with self._lock:
            index = self.index
            if self.generation == index.generation and self._shared == shared:
                return False
            opened = {
                slug
                for project in shared
                if project in index.notes and index.notes[project].type == "project"
                for slug in (project, *index.members.get(project, ()))
            }
            notes = {
                slug: note for slug, note in index.notes.items() if note.public or slug in opened
            }
            keep = notes.keys()
            self.notes = notes
            self.edges = [e for e in index.edges if e.source in keep and e.target in keep]
            self.outlinks = {s: index.outlinks.get(s, set()) & keep for s in notes}
            self.backlinks = {s: index.backlinks.get(s, set()) & keep for s in notes}
            self.members = {
                slug: members & keep for slug, members in index.members.items() if slug in keep
            }
            self.projects_of = {
                s: {p for p in index.projects_of.get(s, set()) if p in keep} for s in notes
            }
            self.generation = index.generation
            self._shared = shared
            return True

    def resolve(self, target: str) -> str | None:
        """The same answer as the whole vault, or nothing when that note is private.

        Resolving against the public notes alone would be wrong: when a private note
        wins a name, the signed-in page links to it, so the public page must not link a
        different, public note of the same name instead."""
        slug = self.index.resolve(target)
        return slug if slug in self.notes else None
