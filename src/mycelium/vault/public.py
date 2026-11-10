"""The part of a vault anonymous visitors may see (§9).

``PublicView`` answers the same questions as ``VaultIndex`` but only knows notes with
``public: true``. Private notes are not hidden from it, they are absent: no titles, no
links, no counts, no ghosts. Every page built from it therefore cannot leak them, and a
link from a public note to a private one resolves to nothing, so it renders as text.

Ghost nodes (links to missing notes) are left out too. Showing them would tell a visitor
which unresolved links point at nothing and, by elimination, which point at a private note.
"""

from __future__ import annotations

import threading

from mycelium.vault.index import Edge, IndexView, Issue, Note, VaultIndex


class PublicView(IndexView):
    def __init__(self, index: VaultIndex) -> None:
        self.index = index
        self._lock = threading.Lock()
        self.generation = -1
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
        """Rebuild from the index when it changed since the last look."""
        with self._lock:
            index = self.index
            if self.generation == index.generation:
                return False
            notes = {slug: note for slug, note in index.notes.items() if note.public}
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
            return True

    def resolve(self, target: str) -> str | None:
        """The same answer as the whole vault, or nothing when that note is private.

        Resolving against the public notes alone would be wrong: when a private note
        wins a name, the signed-in page links to it, so the public page must not link a
        different, public note of the same name instead."""
        slug = self.index.resolve(target)
        return slug if slug in self.notes else None
