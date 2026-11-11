"""A project's guide (§3.4): its notes in an order to follow, with the gaps still to fill.

The logical order is written in the project's index, under a ``## Guide`` heading (the
names come from ``[guide] headings``): an ordered list of links, with ``###`` headings
for its stretches. A project without that section is guided in the order its index
first links each note. Notes the index links outside the guide come last, so the guide
always shows every note of the project. The chronological order sorts the same notes by
their creation date.

A gap is a note with ``type: gap`` (a primordium, something still missing to understand
the project). A link in the guide to a note that does not exist yet is shown as a gap
too, without a page; visitors never see those, because ``PublicView`` has no ghosts.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from micelio.render import href_for
from micelio.vault.index import IndexView, Note, is_attachment
from micelio.vault.parser import extract_links, link_key
from micelio.vault.sections import section as guide_section

Order = Literal["guide", "time"]

# Notes the guide never lists: the project's own conversations and other projects.
_LEFT_OUT = ("project", "journal")


@dataclass(frozen=True, slots=True)
class GuideStep:
    title: str
    note: Note | None  # None: a link to a note that does not exist yet
    href: str | None
    chapter: str | None = None
    placed: bool = True  # False: linked by the index, but outside its guide

    @property
    def slug(self) -> str | None:
        return self.note.slug if self.note else None

    @property
    def is_gap(self) -> bool:
        return self.note is None or self.note.type == "gap"


@dataclass(frozen=True, slots=True)
class Pager:
    previous: GuideStep | None
    next: GuideStep | None
    position: int  # 1-based, 0 when the note is not in this order
    total: int


@dataclass(frozen=True, slots=True)
class Guide:
    project: Note
    steps: list[GuideStep]  # the logical order
    by_time: list[GuideStep]  # the same notes by creation date; no missing notes
    authored: bool  # the index has a guide section
    gaps: int = 0
    others: list[Note] = field(default_factory=list)  # the other projects of the note shown

    def order(self, name: Order) -> list[GuideStep]:
        return self.steps if name == "guide" else self.by_time

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


class GuideBuilder:
    def __init__(self, headings: Iterable[str], created: Callable[[Note], date]) -> None:
        self.headings = tuple(headings)
        self.created = created

    def build(self, vault: IndexView, project: Note) -> Guide:
        section = guide_section(project.body, self.headings)
        authored = section is not None
        lines = section if section is not None else [(None, project.body)]

        steps: list[GuideStep] = []
        seen: set[str] = set()

        def href(note: Note) -> str:
            # A note in more than one project keeps the guide it was reached from.
            if len(vault.projects_of.get(note.slug, ())) > 1:
                return f"{href_for(note)}?guide={project.slug}"
            return href_for(note)

        def add(note: Note, chapter: str | None, *, placed: bool) -> None:
            if note.slug in seen or note.slug == project.slug or note.type in _LEFT_OUT:
                return
            seen.add(note.slug)
            steps.append(GuideStep(note.title, note, href(note), chapter, placed))

        for chapter, text in lines:
            for link in extract_links(text):
                if link.embed:
                    continue
                slug = vault.resolve(link.target)
                if slug is not None:
                    add(vault.notes[slug], chapter, placed=True)
                elif link.target in vault.ghosts and not is_attachment(link.target):
                    key = "ghost:" + link_key(link.target)
                    if key not in seen:
                        seen.add(key)
                        steps.append(GuideStep(link.label or link.target, None, None, chapter))

        rest = sorted(
            (vault.notes[m] for m in vault.members.get(project.slug, ()) if m not in seen),
            key=lambda n: (self.created(n), n.title.lower()),
        )
        for note in rest:
            add(note, None, placed=False)

        by_time = sorted(
            (s for s in steps if s.note is not None),
            key=lambda s: (self.created(s.note), s.title.lower()) if s.note else (date.min, ""),
        )
        by_time = [GuideStep(s.title, s.note, s.href) for s in by_time]
        return Guide(project, steps, by_time, authored, sum(1 for s in steps if s.is_gap))
