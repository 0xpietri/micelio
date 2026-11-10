"""Dates for people: per language with Babel, in the configured time zone."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from babel.dates import format_date

from micelio.vault.index import Note

_LEADING_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _parse(value: str | None) -> date | None:
    if not value:
        return None
    match = _LEADING_DATE.match(value.strip())
    if not match:
        return None
    try:
        return date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None


class Dates:
    def __init__(self, language: str, timezone: str) -> None:
        self.language = language
        self.zone = ZoneInfo(timezone)

    def modified(self, note: Note) -> date:
        return datetime.fromtimestamp(note.mtime_ns / 1e9, tz=UTC).astimezone(self.zone).date()

    def created(self, note: Note) -> date:
        """``created`` from the frontmatter, else a date at the start of the file name."""
        stem = note.path.rsplit("/", 1)[-1]
        return _parse(note.created) or _parse(stem) or self.modified(note)

    def updated(self, note: Note) -> date:
        return _parse(note.updated) or self.modified(note)

    def show(self, value: date) -> str:
        return format_date(value, format="medium", locale=self.language)
