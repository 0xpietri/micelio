"""Find one ``##`` section of a note by its heading, outside code fences (§3.4)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from micelio.vault.parser import slugify

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^[ \t]*(```|~~~)")


def _lines(body: str) -> Iterator[tuple[str, int | None, str]]:
    """Each line, with its heading level and text (level None: not a heading)."""
    fence: str | None = None
    for line in body.splitlines(keepends=True):
        opened = _FENCE.match(line)
        if fence:
            if opened and opened.group(1) == fence:
                fence = None
            yield line, None, line
            continue
        if opened:
            fence = opened.group(1)
            yield line, None, line
            continue
        heading = _HEADING.match(line.rstrip("\r\n"))
        if heading:
            yield line, len(heading.group(1)), heading.group(2)
        else:
            yield line, None, line


def _wanted(headings: Iterable[str]) -> set[str]:
    return {slugify(h) for h in headings}


def section(body: str, headings: Iterable[str]) -> list[tuple[str | None, str]] | None:
    """The lines under the first ``## <heading>`` named in ``headings`` (no case or
    accents), each with the deeper heading it sits under; None when there is none."""
    wanted = _wanted(headings)
    found: list[tuple[str | None, str]] | None = None
    chapter: str | None = None
    for _, level, text in _lines(body):
        if found is None:
            if level == 2 and slugify(text) in wanted:
                found = []
            continue
        if level is not None and level <= 2:
            break
        if level is not None:
            chapter = text
            continue
        found.append((chapter, text))
    return found


def drop_section(body: str, headings: Iterable[str]) -> str:
    """``body`` without that section, heading included."""
    wanted = _wanted(headings)
    kept: list[str] = []
    inside = done = False
    for line, level, text in _lines(body):
        if inside:
            if level is not None and level <= 2:
                inside, done = False, True
            else:
                continue
        if not done and level == 2 and slugify(text) in wanted:
            inside = True
            continue
        kept.append(line)
    return "".join(kept)
