"""A project's guide (§3.4): its notes as a numbered outline to follow, with the gaps still
to fill and the conversations that grew it.

The structured order is written in the project's index, under a ``## Guide`` heading (the
names come from ``[guide] headings``): a nested list. An item without a link is a section
and the items under it hang from it; an item with a link is a note. ``###`` and ``####``
headings inside the section are sections too. Nobody writes numbers: Micelio numbers the
outline (1, 1.1, 1.2, 2 …) from its shape, so inserting a line renumbers everything after
it, and Obsidian renumbers an ordered list the same way.

A project without that section is guided in the order its index first links each note.
Notes the index links outside the guide come last, so the guide always shows every note of
the project. The chronological order lists the same notes by their creation date.

A gap is a note with ``type: gap`` (a primordium, something still missing to understand
the project). A link in the guide to a note that does not exist yet is shown as a gap
too, without a page; visitors never see those, because ``PublicView`` has no ghosts.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from micelio.render import href_for
from micelio.vault.index import IndexView, Note, is_attachment
from micelio.vault.parser import extract_links, link_key
from micelio.vault.sections import section_outline

Order = Literal["guide", "time"]

# Notes the guide never lists as steps: other projects, and conversations (they have their
# own list at the top of the guide).
_LEFT_OUT = ("project", "journal")
_ITEM = re.compile(r"^(?P<indent>[ \t]*)(?:[-*+]|\d+[.)])[ \t]+(?P<text>.*)$")
_LINK_TEXT = re.compile(r"!?\[\[[^\]]*\]\]")
_MARKUP = re.compile(r"[*_`]")


@dataclass(slots=True)
class GuideEntry:
    title: str
    note: Note | None  # None: a section, or a link to a note that does not exist yet
    href: str | None
    depth: int = 0
    section: bool = False
    number: str = ""
    placed: bool = True  # False: linked by the index, but outside its guide

    @property
    def slug(self) -> str | None:
        return self.note.slug if self.note else None

    @property
    def is_gap(self) -> bool:
        return not self.section and (self.note is None or self.note.type == "gap")

    @property
    def kind(self) -> str:
        """What the guide's checkboxes filter by: note, question or gap."""
        if self.section:
            return "section"
        if self.is_gap:
            return "gap"
        return "question" if self.note and self.note.type == "question" else "note"


@dataclass(frozen=True, slots=True)
class Pager:
    previous: GuideEntry | None
    next: GuideEntry | None
    position: int  # 1-based, 0 when the note is not in this order
    total: int


@dataclass(frozen=True, slots=True)
class Guide:
    project: Note
    steps: list[GuideEntry]  # the outline, sections included, in reading order
    by_time: list[GuideEntry]  # the same notes by creation date; no sections, no missing notes
    authored: bool  # the index has a guide section
    gaps: int = 0
    journals: list[Note] = field(default_factory=list)  # newest first
    others: list[Note] = field(default_factory=list)  # the other projects of the note shown

    def order(self, name: Order) -> list[GuideEntry]:
        return self.steps if name == "guide" else self.by_time

    def number_of(self, slug: str) -> str:
        return next((s.number for s in self.steps if s.slug == slug and s.placed), "")

    def pager(self, slug: str, name: Order) -> Pager:
        steps = [s for s in self.order(name) if s.note is not None]
        for i, step in enumerate(steps):
            if step.slug == slug:
                return Pager(
                    steps[i - 1] if i else None,
                    steps[i + 1] if i + 1 < len(steps) else None,
                    i + 1,
                    len(steps),
                )
        return Pager(None, None, 0, len(steps))


@dataclass(slots=True)
class _Node:
    entry: GuideEntry | None  # None: the root
    children: list[_Node] = field(default_factory=list)


def _indent(text: str) -> int:
    return len(text.expandtabs(4))


def _section_title(text: str) -> str:
    title = _MARKUP.sub("", _LINK_TEXT.sub("", text)).strip(" \t:·-—")
    return title


class GuideBuilder:
    def __init__(self, headings: Iterable[str], created: Callable[[Note], date]) -> None:
        self.headings = tuple(headings)
        self.created = created

    def build(self, vault: IndexView, project: Note, journals: Iterable[Note] = ()) -> Guide:
        outline = section_outline(project.body, self.headings)
        authored = outline is not None
        seen: set[str] = set()
        root = _Node(None)

        def href(note: Note) -> str:
            # A note in more than one project keeps the guide it was reached from.
            if len(vault.projects_of.get(note.slug, ())) > 1:
                return f"{href_for(note)}?guide={project.slug}"
            return href_for(note)

        def steps_in(text: str) -> list[GuideEntry]:
            found: list[GuideEntry] = []
            for link in extract_links(text):
                if link.embed:
                    continue
                slug = vault.resolve(link.target)
                if slug is not None:
                    note = vault.notes[slug]
                    if slug in seen or slug == project.slug or note.type in _LEFT_OUT:
                        continue
                    seen.add(slug)
                    found.append(GuideEntry(note.title, note, href(note)))
                elif link.target in vault.ghosts and not is_attachment(link.target):
                    key = "ghost:" + link_key(link.target)
                    if key not in seen:
                        seen.add(key)
                        found.append(GuideEntry(link.label or link.target, None, None))
            return found

        if outline is None:
            for entry in steps_in(project.body):
                root.children.append(_Node(entry))
        else:
            # Two stacks: headings (by level) and list items (by indent) under the last one.
            headings: list[tuple[int, _Node]] = [(2, root)]
            items: list[tuple[int, _Node]] = []
            for level, text in outline:
                if level is not None:
                    while headings[-1][0] >= level:
                        headings.pop()
                    node = _Node(GuideEntry(_section_title(text), None, None, section=True))
                    headings[-1][1].children.append(node)
                    headings.append((level, node))
                    items = []
                    continue
                match = _ITEM.match(text)
                if not match:
                    continue
                indent = _indent(match.group("indent"))
                while items and items[-1][0] >= indent:
                    items.pop()
                parent = items[-1][1] if items else headings[-1][1]
                entries = steps_in(match.group("text"))
                if not entries:
                    title = _section_title(match.group("text"))
                    if not title:
                        continue
                    entries = [GuideEntry(title, None, None, section=True)]
                nodes = [_Node(e) for e in entries]
                parent.children.extend(nodes)
                # Items indented under this one hang from its first entry.
                items.append((indent, nodes[0]))

        def prune(node: _Node) -> bool:
            """Drop sections with nothing under them; True when ``node`` stays."""
            node.children = [c for c in node.children if prune(c)]
            return node.entry is None or not node.entry.section or bool(node.children)

        prune(root)
        steps: list[GuideEntry] = []

        def flatten(node: _Node, prefix: str, depth: int) -> None:
            for i, child in enumerate(node.children, start=1):
                entry = child.entry
                if entry is None:  # only the root has no entry
                    continue
                entry.number = f"{prefix}{i}"
                entry.depth = depth
                steps.append(entry)
                flatten(child, f"{entry.number}.", depth + 1)

        flatten(root, "", 0)

        rest = sorted(
            (
                vault.notes[m]
                for m in vault.members.get(project.slug, ())
                if m not in seen and vault.notes[m].type not in _LEFT_OUT
            ),
            key=lambda n: (self.created(n), n.title.lower()),
        )
        for note in rest:
            steps.append(GuideEntry(note.title, note, href(note), placed=False))

        notes = [s for s in steps if s.note is not None]
        notes.sort(key=lambda s: (self.created(s.note) if s.note else date.min, s.title.lower()))
        by_time = [
            GuideEntry(s.title, s.note, s.href, number=str(i)) for i, s in enumerate(notes, start=1)
        ]
        return Guide(
            project,
            steps,
            by_time,
            authored,
            sum(1 for s in steps if s.is_gap),
            journals=list(journals),
        )
