"""Parse one Markdown note: frontmatter, title and wikilinks."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import yaml

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_FENCE = re.compile(r"^(```|~~~).*?^\1", re.DOTALL | re.MULTILINE)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_WIKILINK = re.compile(r"(!?)\[\[([^\[\]|#\n]*)(#[^\[\]|\n]*)?(?:\|([^\[\]\n]*))?\]\]")
_H1 = re.compile(r"^#[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class WikiLink:
    """A ``[[target#heading|label]]`` found in a note's body."""

    target: str
    heading: str | None = None
    label: str | None = None
    embed: bool = False


@dataclass(slots=True)
class ParsedNote:
    frontmatter: dict[str, Any]
    title: str
    body: str
    links: list[WikiLink] = field(default_factory=list)
    frontmatter_error: str | None = None


def slugify(text: str) -> str:
    """Lowercase ASCII slug: accents stripped, runs of other characters become '-'."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or "note"


def link_key(text: str) -> str:
    """How link targets and file names compare: case-insensitive, NFC and NFD names match."""
    normalized = unicodedata.normalize("NFKC", text).strip().casefold()
    return re.sub(r"\s+", " ", normalized)


def _yaml_safe(value: Any) -> Any:
    """YAML turns ``2026-11-09`` into a date; keep everything JSON-friendly."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _yaml_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_yaml_safe(v) for v in value]
    return value


def split_frontmatter(text: str) -> tuple[dict[str, Any], str, str | None]:
    """Return (frontmatter, body, error). A broken block is reported, never raised."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text, None
    body = text[match.end() :]
    try:
        loaded = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return {}, body, f"invalid frontmatter: {exc.__class__.__name__}"
    if loaded is None:
        return {}, body, None
    if not isinstance(loaded, dict):
        return {}, body, "frontmatter is not a key/value block"
    return _yaml_safe(loaded), body, None


def extract_links(body: str) -> list[WikiLink]:
    """Wikilinks outside code blocks and inline code, in order of appearance."""
    visible = _INLINE_CODE.sub("", _FENCE.sub("", body))
    links: list[WikiLink] = []
    for embed, target, heading, label in _WIKILINK.findall(visible):
        target = target.strip()
        if not target:
            continue
        links.append(
            WikiLink(
                target=target,
                heading=heading[1:].strip() or None if heading else None,
                label=label.strip() or None if label else None,
                embed=bool(embed),
            )
        )
    return links


def parse_note(text: str, *, fallback_title: str) -> ParsedNote:
    frontmatter, body, error = split_frontmatter(text)
    title_value = frontmatter.get("title")
    if isinstance(title_value, str) and title_value.strip():
        title = title_value.strip()
    else:
        h1 = _H1.search(_FENCE.sub("", body))
        title = h1.group(1).strip() if h1 else fallback_title
    return ParsedNote(
        frontmatter=frontmatter,
        title=title,
        body=body,
        links=extract_links(body),
        frontmatter_error=error,
    )
