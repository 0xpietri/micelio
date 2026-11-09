"""The in-memory index of a vault: notes, links, backlinks, projects and bridges.

The files are the truth. The index is rebuilt from them and kept fresh by
comparing modification times, so a note written during a conversation shows
up on the next page load.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from mycelium.config import NOTE_TYPES, STATUSES, Config, NoteType
from mycelium.vault.parser import ParsedNote, WikiLink, link_key, parse_note, slugify

REFRESH_INTERVAL_S = 2.0
MAX_NOTE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Issue:
    """Something in the vault that Mycelium had to guess about or ignore."""

    path: str
    kind: str
    detail: str


@dataclass(slots=True)
class Note:
    path: str
    slug: str
    title: str
    type: NoteType
    body: str
    links: list[WikiLink]
    mtime_ns: int
    category: str | None = None
    status: str | None = None
    tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    created: str | None = None
    updated: str | None = None
    public: bool = False
    frontmatter: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Edge:
    source: str
    target: str


@dataclass(slots=True)
class _Cached:
    stamp: tuple[int, int]
    parsed: ParsedNote


def _is_skipped(name: str) -> bool:
    return name.startswith(".") or ".sync-conflict-" in name


class VaultIndex:
    """Thread-safe index over one vault root."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.root = config.vault.root
        self._lock = threading.Lock()
        self._cache: dict[str, _Cached] = {}
        self._stamps: dict[str, tuple[int, int]] = {}
        self._last_check = 0.0
        self.notes: dict[str, Note] = {}
        self.issues: list[Issue] = []
        self.edges: list[Edge] = []
        self.ghosts: dict[str, set[str]] = {}
        self.backlinks: dict[str, set[str]] = {}
        self.outlinks: dict[str, set[str]] = {}
        self.members: dict[str, set[str]] = {}
        self.projects_of: dict[str, set[str]] = {}
        self._by_key: dict[str, list[str]] = {}
        self._by_path: dict[str, str] = {}

    # -- scanning -----------------------------------------------------------

    def _walk(self) -> Iterator[tuple[str, Path]]:
        root = self.root
        root_real = root.resolve()
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if not _is_skipped(d))
            for name in sorted(filenames):
                if _is_skipped(name) or not name.lower().endswith(".md"):
                    continue
                full = Path(dirpath) / name
                if full.is_symlink() and not full.resolve().is_relative_to(root_real):
                    continue
                rel = full.relative_to(root).as_posix()
                yield rel, full

    def _snapshot(self) -> dict[str, tuple[int, int]]:
        stamps: dict[str, tuple[int, int]] = {}
        if not self.root.is_dir():
            return stamps
        for rel, full in self._walk():
            try:
                st = full.stat()
            except OSError:
                continue
            stamps[rel] = (st.st_mtime_ns, st.st_size)
        return stamps

    def refresh(self, *, force: bool = False) -> bool:
        """Rebuild if any file changed. Returns True when the index changed."""
        with self._lock:
            now = time.monotonic()
            if not force and now - self._last_check < REFRESH_INTERVAL_S:
                return False
            self._last_check = now
            stamps = self._snapshot()
            if not force and stamps == self._stamps:
                return False
            self._build(stamps)
            return True

    def _parse(self, rel: str, stamp: tuple[int, int], issues: list[Issue]) -> ParsedNote | None:
        cached = self._cache.get(rel)
        if cached and cached.stamp == stamp:
            return cached.parsed
        if stamp[1] > MAX_NOTE_BYTES:
            issues.append(Issue(rel, "too-large", f"skipped, over {MAX_NOTE_BYTES} bytes"))
            return None
        try:
            text = (self.root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            issues.append(Issue(rel, "unreadable", exc.__class__.__name__))
            return None
        parsed = parse_note(text, fallback_title=PurePosixPath(rel).stem)
        self._cache[rel] = _Cached(stamp, parsed)
        return parsed

    def _infer_type(self, rel: str, declared: object, issues: list[Issue]) -> NoteType:
        if declared is not None:
            for t in NOTE_TYPES:
                if declared == t:
                    return t
            issues.append(
                Issue(rel, "unknown-type", f"type {declared!r} is not one of {NOTE_TYPES}")
            )
        top = PurePosixPath(rel).parts[0] if "/" in rel else ""
        for t in NOTE_TYPES:
            if top == self.config.vault.folder_for(t):
                return t
        return "note"

    def _build(self, stamps: dict[str, tuple[int, int]]) -> None:
        issues: list[Issue] = []
        notes: dict[str, Note] = {}
        used_slugs: set[str] = set()
        for rel in sorted(stamps, key=lambda p: (p.count("/"), p)):
            parsed = self._parse(rel, stamps[rel], issues)
            if parsed is None:
                continue
            if parsed.frontmatter_error:
                issues.append(Issue(rel, "frontmatter", parsed.frontmatter_error))
            note = self._make_note(rel, stamps[rel][0], parsed, used_slugs, issues)
            used_slugs.add(note.slug)
            notes[note.slug] = note
        self._cache = {k: v for k, v in self._cache.items() if k in stamps}
        self.notes = notes
        self._stamps = stamps
        self._index_names()
        self._link(issues)
        self.issues = issues

    def _make_note(
        self,
        rel: str,
        mtime_ns: int,
        parsed: ParsedNote,
        used_slugs: set[str],
        issues: list[Issue],
    ) -> Note:
        fm = parsed.frontmatter
        path = PurePosixPath(rel)
        slug = slugify(path.stem)
        if slug in used_slugs:
            slug = slugify(str(path.with_suffix("")))
        note_type = self._infer_type(rel, fm.get("type"), issues)

        category = fm.get("category")
        if category is not None:
            category = str(category)
            if note_type != "project":
                issues.append(Issue(rel, "category-ignored", "only projects carry a category"))
                category = None
            elif self.config.category(category) is None:
                issues.append(Issue(rel, "unknown-category", f"category {category!r}"))
                category = None

        status = fm.get("status")
        if status is not None:
            status = str(status)
            if status not in STATUSES:
                issues.append(Issue(rel, "unknown-status", f"status {status!r}"))
                status = None

        return Note(
            path=rel,
            slug=slug,
            title=parsed.title,
            type=note_type,
            body=parsed.body,
            links=parsed.links,
            mtime_ns=mtime_ns,
            category=category,
            status=status,
            tags=_str_tuple(fm.get("tags")),
            aliases=_str_tuple(fm.get("aliases")),
            created=_opt_str(fm.get("created")),
            updated=_opt_str(fm.get("updated")),
            public=fm.get("public") is True,
            frontmatter=fm,
        )

    def _index_names(self) -> None:
        by_key: dict[str, list[str]] = {}
        by_path: dict[str, str] = {}
        for slug, note in self.notes.items():
            path = PurePosixPath(note.path)
            names = {path.stem, *note.aliases}
            for name in names:
                by_key.setdefault(link_key(name), []).append(slug)
            by_path[link_key(str(path.with_suffix("")))] = slug
        for slugs in by_key.values():
            slugs.sort(key=lambda s: (len(self.notes[s].path), self.notes[s].path))
        self._by_key = by_key
        self._by_path = by_path

    def resolve(self, target: str) -> str | None:
        """Find the note a wikilink points at, the way Obsidian does."""
        name = target.strip()
        if name.lower().endswith(".md"):
            name = name[:-3]
        if "/" in name:
            key = link_key(name.lstrip("/"))
            if key in self._by_path:
                return self._by_path[key]
            suffix = "/" + key
            matches = sorted(
                (p for p in self._by_path if p.endswith(suffix)), key=lambda p: (len(p), p)
            )
            if matches:
                return self._by_path[matches[0]]
            name = PurePosixPath(name).name
        candidates = self._by_key.get(link_key(name))
        return candidates[0] if candidates else None

    def _link(self, issues: list[Issue]) -> None:
        edges: list[Edge] = []
        seen: set[tuple[str, str]] = set()
        ghosts: dict[str, set[str]] = {}
        backlinks: dict[str, set[str]] = {slug: set() for slug in self.notes}
        outlinks: dict[str, set[str]] = {slug: set() for slug in self.notes}
        for slug, note in self.notes.items():
            for link in note.links:
                target = self.resolve(link.target)
                if target is None:
                    ghosts.setdefault(link.target, set()).add(slug)
                    continue
                if target == slug or (slug, target) in seen:
                    continue
                seen.add((slug, target))
                edges.append(Edge(slug, target))
                outlinks[slug].add(target)
                backlinks[target].add(slug)
        for target, sources in sorted(ghosts.items()):
            for source in sorted(sources):
                issues.append(Issue(self.notes[source].path, "broken-link", f"[[{target}]]"))

        members: dict[str, set[str]] = {}
        projects_of: dict[str, set[str]] = {slug: set() for slug in self.notes}
        for slug, note in self.notes.items():
            if note.type != "project":
                continue
            members[slug] = {t for t in outlinks[slug] if self.notes[t].type != "project"}
            for member in members[slug]:
                projects_of[member].add(slug)

        self.edges = edges
        self.ghosts = ghosts
        self.backlinks = backlinks
        self.outlinks = outlinks
        self.members = members
        self.projects_of = projects_of

    # -- questions ------------------------------------------------------------

    def categories_of(self, slug: str) -> set[str]:
        """The categories a note takes its color from (through its projects)."""
        note = self.notes[slug]
        if note.type == "project":
            return {note.category} if note.category else set()
        return {
            category
            for project in self.projects_of.get(slug, ())
            if (category := self.notes[project].category)
        }

    def is_bridge(self, slug: str) -> bool:
        """A note linked from projects of more than one category."""
        return len(self.categories_of(slug)) > 1

    def orphans(self) -> list[str]:
        return sorted(
            slug
            for slug in self.notes
            if not self.backlinks.get(slug) and not self.outlinks.get(slug)
        )

    def projects(self) -> list[Note]:
        return sorted(
            (n for n in self.notes.values() if n.type == "project"), key=lambda n: n.title.lower()
        )


def _str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        items = [str(v).strip() for v in value if v is not None]
    else:
        items = [str(value).strip()]
    return tuple(dict.fromkeys(i.lstrip("#") for i in items if i))


def _opt_str(value: object) -> str | None:
    return None if value is None else str(value)
