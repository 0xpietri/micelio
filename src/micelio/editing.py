"""The owner's own changes to a note, written into the vault (§8a).

The one place Micelio writes a note. From the note's page the signed-in owner can:

- write ``> [!said]`` bubbles at the top level of its body: insert one between two
  blocks, change its words, move it or delete it;
- change or delete any top-level block (a paragraph, a list, a callout such as the
  takeaway, a table), or delete a heading with everything under it (a section);
- replace the whole body, written as Markdown;
- undo the site's last change, while nobody else has written the note since.

The frontmatter is never changed from the site, except ``edited_by`` and ``updated``.

Safe against the other writers (the notes MCP, Obsidian through Syncthing):

- **Conflict check.** The page carries the SHA-256 of the file it showed; a change is
  refused, writing nothing, when the file on disk is not that file any more.
- **Atomic.** The new text goes to a temporary file in the same folder, named the way
  Syncthing names its own temporary files (so it never syncs it), then replaces the
  note in one rename. The note keeps its permissions and its line endings.
- **A copy of each version replaced** goes to the data folder (``edits/<note>/``), never
  to the vault: the last ``KEEP_VERSIONS`` of each note, with the hash of the file that
  change wrote, so Undo restores it only while the note is still that file.
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
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

from micelio.vault.parser import split_frontmatter

MAX_SAID_CHARS = 5000
MAX_BODY_CHARS = 200_000
KEEP_VERSIONS = 20  # of each note
_SAID = re.compile(r"^[ \t]{0,3}>[ \t]?\[!said\][+-]?(.*)$", re.IGNORECASE)
_FRONTMATTER_END = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.DOTALL)
# Holds the place a moved bubble goes to while it is cut out (never a line of a note).
_MARK = "\x00micelio-move\x00"
# The renderer's own block rules, so a block's lines here are the ones its page shows.
_BLOCKS = (
    MarkdownIt("commonmark", {"html": True})
    .enable(["table", "strikethrough"])
    .use(tasklists_plugin)
    .use(footnote_plugin)
)
_HEADING = re.compile(r"^h([1-6])$")

Block = tuple[int, int, str, str]  # first line, line after it, token type, tag


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

    # Said bubbles: insert | edit | move | delete. Any top-level block: block (its new
    # text; empty deletes it) | drop | section (a heading and everything under it).
    # The whole note: body (its new text, frontmatter kept) | undo.
    op: str
    at: int | None = None  # insert, move: the body line the bubble goes before
    start: int | None = None  # edit, move, delete, block, drop, section: the first line
    text: str = ""  # insert, edit, block, body: the words, Markdown allowed


def said_lines(text: str, title: str = "") -> list[str]:
    """``text`` as a said callout, one ``>`` line per line, empty lines kept."""
    words = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    head = "> [!said]" + (f" {title}" if title else "")
    return [head, *(f"> {line}".rstrip() if line.strip() else ">" for line in words.split("\n"))]


def _blocks(body: str) -> list[Block]:
    """Each top-level block of ``body``: first line, line after it, token type, tag."""
    found = []
    for token in _BLOCKS.parse(body):
        if token.level == 0 and token.nesting in (0, 1) and token.map and token.type != "inline":
            found.append((token.map[0], token.map[1], token.type, token.tag))
    return found


def _text_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip("\n").split("\n")


def _trim(lines: list[str], first: int, after: int) -> int:
    """``after`` moved up past the empty lines that end a block."""
    while after > first and not lines[after - 1].strip():
        after -= 1
    return after


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


class NoteEditor:
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
        if edit.op == "undo":
            return self._undo(rel, path, raw)
        newline = "\r\n" if "\r\n" in text else "\n"
        # Normalized the way the index read it, so the lines are the ones the page numbered.
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        match = _FRONTMATTER_END.match(text)
        if split_frontmatter(text)[2]:
            raise EditError("frontmatter")
        head = text[: match.end()] if match else ""
        body = text[len(head) :]
        lines = self._change(body, body.split("\n"), edit)
        if not head and _FRONTMATTER_END.match("\n".join(lines)):
            raise EditError("frontmatter")  # the new text would turn into frontmatter

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
        if data == raw:
            return content_hash(raw)
        self._keep(rel, raw, content_hash(data))
        self._write(path, data)
        return content_hash(data)

    def source(self, rel: str, start: int | None = None) -> str:
        """The note's body as written (frontmatter left out), or with ``start`` the text of
        the top-level block that starts there, for the page's editors."""
        lines = self._body_lines(rel)
        if start is None:
            return "\n".join(lines).strip("\n")
        first, end = self._block(_blocks("\n".join(lines)), lines, start)
        return "\n".join(lines[first:end])

    def undoable(self, rel: str, current: str) -> bool:
        """Whether Undo can put back what the site's last change replaced: it was the
        last to write the note, which is still the file hashed ``current``."""
        latest = self._latest(rel)
        return latest is not None and _after(latest) == current

    def _body_lines(self, rel: str) -> list[str]:
        path = self.path_of(rel)
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise EditError("missing", 404) from exc
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        match = _FRONTMATTER_END.match(text)
        body = text[match.end() :] if match else text
        return body.split("\n")

    def words(self, rel: str, start: int) -> str:
        """The words of the said bubble at ``start`` as written (Markdown kept), for the
        page's editor."""
        lines = self._body_lines(rel)
        first, end = self._said(_blocks("\n".join(lines)), lines, start)
        inner = [re.sub(r"^[ \t]{0,3}>[ \t]?", "", line) for line in lines[first + 1 : end]]
        return "\n".join(inner).strip("\n")

    def _change(self, body: str, lines: list[str], edit: Edit) -> list[str]:
        blocks = _blocks(body)
        lines = list(lines)
        if edit.op == "body":
            if not edit.text.strip():
                raise EditError("empty")
            if len(edit.text) > MAX_BODY_CHARS:
                raise EditError("too-long")
            return _text_lines(edit.text)
        if edit.op in ("block", "drop", "section"):
            if len(edit.text) > MAX_BODY_CHARS:
                raise EditError("too-long")
            if edit.op == "section":
                start, end = self._section(blocks, lines, edit.start)
            else:
                start, end = self._block(blocks, lines, edit.start)
            if edit.op == "block" and edit.text.strip():
                lines[start:end] = _text_lines(edit.text)
                return lines
            del lines[start:end]
            _tidy(lines, start)
            return lines
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
    def _gap(blocks: list[Block], lines: list[str], at: int | None) -> int:
        """``at`` if it is a place between two top-level blocks (or before the first or
        after the last), never inside one."""
        if at is None:
            raise EditError("place")
        gaps = {0, len(lines)} | {b[0] for b in blocks} | {b[1] for b in blocks}
        if at not in gaps or any(b[0] < at < b[1] for b in blocks):
            raise EditError("place")
        return at

    @staticmethod
    def _said(blocks: list[Block], lines: list[str], start: int | None) -> tuple[int, int]:
        """The lines of the top-level said bubble starting at ``start``."""
        for first, after, kind, _tag in blocks:
            if first == start and kind == "blockquote_open" and _SAID.match(lines[first]):
                return first, _trim(lines, first, after)
        raise EditError("not-said")

    @staticmethod
    def _block(blocks: list[Block], lines: list[str], start: int | None) -> tuple[int, int]:
        """The lines of the top-level block starting at ``start``, whatever it is."""
        for first, after, _kind, _tag in blocks:
            if first == start:
                return first, _trim(lines, first, after)
        raise EditError("not-block")

    @staticmethod
    def _section(blocks: list[Block], lines: list[str], start: int | None) -> tuple[int, int]:
        """A heading at ``start`` and everything under it: up to the next heading of the
        same level or a higher one, or the end of the note."""
        for i, (first, _after, kind, tag) in enumerate(blocks):
            level = _HEADING.match(tag)
            if first != start or kind != "heading_open" or not level:
                continue
            end = len(lines)
            for other_first, _a, other_kind, other_tag in blocks[i + 1 :]:
                other = _HEADING.match(other_tag)
                if other_kind == "heading_open" and other and other.group(1) <= level.group(1):
                    end = other_first
                    break
            return first, _trim(lines, first, end)
        raise EditError("not-heading")

    # -- the versions replaced, and Undo ------------------------------------------------

    def _folder(self, rel: str) -> Path:
        return self.history / re.sub(r"[^\w.-]+", "_", rel)

    def _latest(self, rel: str) -> Path | None:
        try:
            kept = sorted(self._folder(rel).glob("*.md"))
        except OSError:
            return None
        return kept[-1] if kept else None

    def _keep(self, rel: str, raw: bytes, after: str) -> None:
        """The version being replaced, into the data folder, with the hash of the file
        replacing it; the oldest ones of this note go."""
        try:
            folder = self._folder(rel)
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            (folder / f"{stamp}.md").write_bytes(raw)
            (folder / f"{stamp}.after").write_text(after, encoding="utf-8")
            kept = sorted(folder.glob("*.md"))
            for old in kept[: max(0, len(kept) - KEEP_VERSIONS)]:
                old.unlink(missing_ok=True)
                old.with_suffix(".after").unlink(missing_ok=True)
        except OSError as exc:
            raise EditError("history", 500) from exc

    def _undo(self, rel: str, path: Path, raw: bytes) -> str:
        """The version the site's last change replaced, back in the vault. Refused when
        someone else wrote the note after that change: Undo would throw their words away."""
        latest = self._latest(rel)
        if latest is None:
            raise EditError("nothing", 409)
        if _after(latest) != content_hash(raw):
            raise EditError("not-last", 409)
        try:
            data = latest.read_bytes()
        except OSError as exc:
            raise EditError("history", 500) from exc
        self._write(path, data)
        latest.unlink(missing_ok=True)
        latest.with_suffix(".after").unlink(missing_ok=True)
        return content_hash(data)

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


def _after(version: Path) -> str:
    try:
        return version.with_suffix(".after").read_text(encoding="utf-8").strip()
    except OSError:
        return ""
