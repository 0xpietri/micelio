"""Dates for people: per language with Babel, in the configured time zone."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from babel.dates import format_date, format_skeleton

from micelio.i18n import active_language
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

    def short(self, value: date) -> str:
        """Day, month and year in numbers, in the language's order (1/10/2026, 10/1/2026)."""
        return format_skeleton("yMd", value, locale=active_language(self.language))

    def show(self, value: date) -> str:
        return format_date(value, format="medium", locale=active_language(self.language))


_MODEL_ID = re.compile(r"^claude-([a-z]+)-(\d+(?:-\d+)*)$")


def author_name(value: object) -> str:
    """Who wrote a note (``created_by`` / ``edited_by``), for people: a model id such as
    ``claude-opus-5-5`` reads "Claude Opus 5.5"; anything else is shown as written."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    match = _MODEL_ID.match(text.lower())
    if match:
        return f"Claude {match[1].capitalize()} {match[2].replace('-', '.')}"
    return text


def authors(note: Note) -> tuple[str, str]:
    """``(created_by, edited_by)`` for people; edited_by is empty when it is the same."""
    created = author_name(note.frontmatter.get("created_by"))
    edited = author_name(note.frontmatter.get("edited_by"))
    return created, "" if edited == created else edited
