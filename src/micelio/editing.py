"""The owner's said bubbles, written into the vault (§8a).

The one place Micelio writes a note, and only ``> [!said]`` callouts at the top level of
its body: insert one between two blocks, change its words, move it or delete it. Nothing
else of the note changes, except ``edited_by`` and ``updated`` in its frontmatter.

Safe against the other writers (the notes MCP, Obsidian through Syncthing):

- **Conflict check.** The page carries the SHA-256 of the file it showed; a change is
  refused, writing nothing, when the file on disk is not that file any more.
- **Atomic.** The new text goes to a temporary file in the same folder, named the way
  Syncthing names its own temporary files (so it never syncs it), then replaces the
  note in one rename. The note keeps its permissions and its line endings.
- **A copy of each version replaced** goes to the data folder (``edits/``), never to the
  vault: the last ``KEEP_VERSIONS``, to undo a mistake by hand.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from markdown_it import MarkdownIt

from micelio.vault.parser import split_frontmatter

MAX_SAID_CHARS = 5000
KEEP_VERSIONS = 50
_SAID = re.compile(r"^[ \t]{0,3}>[ \t]?\[!said\][+-]?(.*)$", re.IGNORECASE)
_FRONTMATTER_END = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.DOTALL)
# Holds the place a moved bubble goes to while it is cut out (never a line of a note).
_MARK = "\x00micelio-move\x00"
_BLOCKS = MarkdownIt("commonmark").enable(["table", "strikethrough"])


class EditError(Exception):
    """A change that was refused; ``code`` says why, for the page."""

    def __init__(self, code: str, status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


def content_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_hash(path: Path) -> str:
    return content_hash(path.read_bytes())


@dataclass(frozen=True, slots=True)
class Edit:
    """One change asked by the page. Lines count from 0 in the note's body (the text
    after the frontmatter), the numbers the owner's renderer puts on each block."""

    op: str  # insert | edit | move | delete
    at: int | None = None  # insert, move: the body line the bubble goes before
    start: int | None = None  # edit, move, delete: the first line of the bubble
    text: str = ""  # insert, edit: the words, Markdown allowed


def said_lines(text: str, title: str = "") -> list[str]:
    """``text`` as a said callout, one ``>`` line per line, empty lines kept."""
    words = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    head = "> [!said]" + (f" {title}" if title else "")
    return [head, *(f"> {line}".rstrip() if line.strip() else ">" for line in words.split("\n"))]


def _blocks(body: str) -> list[tuple[int, int, str]]:
    """Each top-level block of ``body``: first line, line after it, token type."""
    found = []
    for token in _BLOCKS.parse(body):
        if token.level == 0 and token.nesting in (0, 1) and token.map:
            found.append((token.map[0], token.map[1], token.type))
    return found


def _set_field(front: list[str], key: str, value: str) -> list[str]:
    """``front`` (the lines between the ``---``) with ``key: value``, the rest untouched."""
    line = f"{key}: {value}"
    pattern = re.compile(rf"^{re.escape(key)}[ \t]*:")
    for i, existing in enumerate(front):
        if pattern.match(existing):
            # A value that runs on over indented lines (a list) is replaced whole.
            end = i + 1
            while end < len(front) and front[end][:1] in (" ", "\t", "-") and front[end].strip():
                end += 1
            return [*front[:i], line, *front[end:]]
    return [*front, line]


def _tidy(lines: list[str], i: int) -> None:
    """Leave exactly one empty line where two runs of text met at ``i`` after a cut."""
    while 0 < i < len(lines) and not lines[i].strip() and not lines[i - 1].strip():
        del lines[i]


def _place(lines: list[str], i: int, block: list[str]) -> None:
    """Put ``block`` at ``i`` with an empty line on each side that has text."""
    after = [""] if i < len(lines) and lines[i].strip() else []
    before = [""] if i > 0 and lines[i - 1].strip() else []
    lines[i:i] = [*before, *block, *after]


class SaidEditor:
    def __init__(self, root: Path, history: Path, author: str) -> None:
        self.root = root
        self.history = history
        self.author = author

    def path_of(self, rel: str) -> Path:
        path = (self.root / rel).resolve()
        if path.suffix.lower() != ".md" or not path.is_relative_to(self.root.resolve()):
            raise EditError("path", 404)
        return path

    def apply(self, rel: str, expected: str, edit: Edit, today: date) -> str:
        """Make ``edit`` in the note at ``rel`` if it is still the file hashed ``expected``.
        Returns the new file's hash."""
        path = self.path_of(rel)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise EditError("missing", 404) from exc
        if not secrets.compare_digest(content_hash(raw), expected):
            raise EditError("changed", 409)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EditError("encoding") from exc
        newline = "\r\n" if "\r\n" in text else "\n"
        # Normalized the way the index read it, so the lines are the ones the page numbered.
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        match = _FRONTMATTER_END.match(text)
        if split_frontmatter(text)[2]:
            raise EditError("frontmatter")
        head = text[: match.end()] if match else ""
        body = text[len(head) :]
        lines = self._change(body, body.split("\n"), edit)

        if head:
            front = head.rstrip("\n").split("\n")[1:-1]
            front = _set_field(front, "updated", today.isoformat())
            if self.author:
                front = _set_field(front, "edited_by", self.author)
            head = "\n".join(["---", *front, "---"]) + "\n"
        new = head + "\n".join(lines)
        if not new.endswith("\n"):
            new += "\n"
        data = new.replace("\n", newline).encode("utf-8")
        self._keep(rel, raw)
        self._write(path, data)
        return content_hash(data)

    def words(self, rel: str, start: int) -> str:
        """The words of the said bubble at ``start`` as written (Markdown kept), for the
        page's editor."""
        path = self.path_of(rel)
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise EditError("missing", 404) from exc
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        match = _FRONTMATTER_END.match(text)
        body = text[match.end() :] if match else text
        lines = body.split("\n")
        first, end = self._said(_blocks(body), lines, start)
        inner = [re.sub(r"^[ \t]{0,3}>[ \t]?", "", line) for line in lines[first + 1 : end]]
        return "\n".join(inner).strip("\n")

    def _change(self, body: str, lines: list[str], edit: Edit) -> list[str]:
        blocks = _blocks(body)
        lines = list(lines)
        if edit.op in ("insert", "edit"):
            words = edit.text.strip()
            if not words:
                raise EditError("empty")
            if len(words) > MAX_SAID_CHARS:
                raise EditError("too-long")
        if edit.op == "insert":
            at = self._gap(blocks, lines, edit.at)
            _place(lines, at, said_lines(edit.text))
            return lines
        start, end = self._said(blocks, lines, edit.start)
        if edit.op == "edit":
            title = _SAID.match(lines[start])
            lines[start:end] = said_lines(edit.text, title.group(1).strip() if title else "")
            return lines
        if edit.op == "delete":
            del lines[start:end]
            _tidy(lines, start)
            return lines
        if edit.op == "move":
            at = self._gap(blocks, lines, edit.at)
            if start <= at <= end:
                return lines  # already there
            moved = lines[start:end]
            slots = [*lines]
            slots.insert(at, _MARK)
            cut = start + 1 if at < start else start
            del slots[cut : cut + len(moved)]
            _tidy(slots, cut)
            where = slots.index(_MARK)
            del slots[where]
            _tidy(slots, where)
            _place(slots, where, moved)
            return slots
        raise EditError("op")

    @staticmethod
    def _gap(blocks: list[tuple[int, int, str]], lines: list[str], at: int | None) -> int:
        """``at`` if it is a place between two top-level blocks (or before the first or
        after the last), never inside one."""
        if at is None:
            raise EditError("place")
        gaps = {0, len(lines)} | {b[0] for b in blocks} | {b[1] for b in blocks}
        if at not in gaps or any(b[0] < at < b[1] for b in blocks):
            raise EditError("place")
        return at

    @staticmethod
    def _said(
        blocks: list[tuple[int, int, str]], lines: list[str], start: int | None
    ) -> tuple[int, int]:
        """The lines of the top-level said bubble starting at ``start``."""
        for first, after, kind in blocks:
            if first == start and kind == "blockquote_open" and _SAID.match(lines[first]):
                end = after
                while end > first and not lines[end - 1].strip():
                    end -= 1
                return first, end
        raise EditError("not-said")

    def _keep(self, rel: str, raw: bytes) -> None:
        """The version being replaced, into the data folder; the oldest ones go."""
        try:
            self.history.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            name = re.sub(r"[^\w.-]+", "_", rel)
            (self.history / f"{stamp}--{name}").write_bytes(raw)
            kept = sorted(self.history.iterdir())
            for old in kept[: max(0, len(kept) - KEEP_VERSIONS)]:
                old.unlink(missing_ok=True)
        except OSError as exc:
            raise EditError("history", 500) from exc

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        temp = path.with_name(f".syncthing.{path.name}.{secrets.token_hex(4)}.tmp")
        mode = path.stat().st_mode & 0o7777
        try:
            with temp.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            temp.chmod(mode)
            temp.replace(path)
        except OSError as exc:
            temp.unlink(missing_ok=True)
            raise EditError("write", 500) from exc
