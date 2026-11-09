"""Turn a note's Markdown into safe HTML, the way Obsidian shows it.

- Wikilinks become links to the note's page; links to missing notes become "ghost" text.
- Callouts (``> [!warning] Title``) become boxes; task lists become disabled checkboxes.
- Everything goes through nh3 at the end, so a note can never inject script or style.
"""

from __future__ import annotations

import re
import threading
from html import escape

import nh3
from markdown_it import MarkdownIt
from markdown_it.rules_core import StateCore
from markdown_it.rules_inline import StateInline
from markdown_it.token import Token
from markupsafe import Markup
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

from mycelium.vault.index import Note, VaultIndex, is_attachment

_WIKILINK = re.compile(r"(!?)\[\[([^\[\]|#\n]*)(#[^\[\]|\n]*)?(?:\|([^\[\]\n]*))?\]\]")
_CALLOUT = re.compile(r"^\[!([A-Za-z][\w-]*)\][+-]?[ \t]*(.*)$")
_LEADING_H1 = re.compile(r"\A\s*#[ \t]+[^\n]*\n?")
_FENCE_BLOCK = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.DOTALL | re.MULTILINE)

_CLASSED = {"a", "div", "span", "p", "li", "ul", "ol", "input", "section", "sup"}
_ATTRIBUTES: dict[str, set[str]] = {
    tag: set(attrs) for tag, attrs in nh3.ALLOWED_ATTRIBUTES.items()
}
for _tag in _CLASSED:
    _ATTRIBUTES.setdefault(_tag, set()).add("class")
_ATTRIBUTES["input"] |= {"type", "checked", "disabled"}
_ATTRIBUTES["a"] |= {"title", "id"}
_ATTRIBUTES["li"] |= {"id"}
_ATTRIBUTES["sup"] |= {"id"}
_TAGS = set(nh3.ALLOWED_TAGS) | {"input", "section"}
_SCHEMES = {"http", "https", "mailto"}


def href_for(note: Note) -> str:
    return f"/projects/{note.slug}" if note.type == "project" else f"/notes/{note.slug}"


def _wikilink_rule(state: StateInline, silent: bool) -> bool:
    if not state.src.startswith(("[[", "![["), state.pos):
        return False
    match = _WIKILINK.match(state.src, state.pos)
    if not match or not match.group(2).strip():
        return False
    if not silent:
        token = state.push("wikilink", "", 0)
        embed, target, heading, label = match.groups()
        token.meta = {
            "embed": bool(embed),
            "target": target.strip(),
            "heading": heading[1:].strip() if heading else "",
            "label": (label or "").strip(),
        }
        token.content = match.group(0)
    state.pos = match.end()
    return True


def _callout_rule(state: StateCore) -> None:
    tokens = state.tokens
    i = 0
    while i < len(tokens):
        opening = tokens[i]
        if (
            opening.type == "blockquote_open"
            and i + 2 < len(tokens)
            and tokens[i + 1].type == "paragraph_open"
            and tokens[i + 2].type == "inline"
        ):
            inline = tokens[i + 2]
            first, _, rest = inline.content.partition("\n")
            match = _CALLOUT.match(first)
            if match:
                kind = match.group(1).lower()
                title = match.group(2).strip() or kind.capitalize()
                opening.tag = "div"
                opening.attrSet("class", f"callout callout-{kind}")
                depth = opening.level
                for closing in tokens[i + 1 :]:
                    if closing.type == "blockquote_close" and closing.level == depth:
                        closing.tag = "div"
                        break
                head_open = Token("paragraph_open", "p", 1)
                head_open.attrSet("class", "callout-title")
                head_inline = Token("inline", "", 0, content=title, children=[])
                head_close = Token("paragraph_close", "p", -1)
                if rest.strip():
                    inline.content = rest
                    tokens[i + 1 : i + 1] = [head_open, head_inline, head_close]
                else:
                    tokens[i + 1 : i + 4] = [head_open, head_inline, head_close]
        i += 1


class Renderer:
    """Renders notes of one vault; results are cached until the vault changes."""

    def __init__(self, index: VaultIndex) -> None:
        self.index = index
        self._cache: dict[str, Markup] = {}
        self._generation = -1
        self._lock = threading.Lock()
        md = MarkdownIt("commonmark", {"html": True, "linkify": False, "typographer": False})
        md.enable(["table", "strikethrough"])
        md.use(tasklists_plugin).use(footnote_plugin)
        md.inline.ruler.before("link", "wikilink", _wikilink_rule)
        md.core.ruler.before("inline", "callouts", _callout_rule)
        render_wikilink = self._render_wikilink

        def wikilink_rule(_renderer: object, tokens: list[Token], idx: int, *_rest: object) -> str:
            return render_wikilink(tokens, idx)

        md.add_render_rule("wikilink", wikilink_rule)
        self.md = md

    def _render_wikilink(self, tokens: list[Token], idx: int) -> str:
        meta = tokens[idx].meta
        target, heading, label = meta["target"], meta["heading"], meta["label"]
        text = label or (f"{target} > {heading}" if heading else target)
        slug = self.index.resolve(target)
        if slug is None:
            if is_attachment(target):
                return f'<span class="attachment">{escape(text)}</span>'
            return f'<span class="ghost" title="{escape(target)}">{escape(text)}</span>'
        note = self.index.notes[slug]
        if not label and not heading:
            text = note.title
        kind = "wikilink embed" if meta["embed"] else "wikilink"
        return f'<a class="{kind}" href="{escape(href_for(note))}">{escape(text)}</a>'

    def html(self, note: Note) -> Markup:
        with self._lock:
            if self._generation != self.index.generation:
                self._cache.clear()
                self._generation = self.index.generation
            cached = self._cache.get(note.slug)
            if cached is not None:
                return cached
        body = _LEADING_H1.sub("", note.body, count=1)
        raw = self.md.render(body)
        clean = nh3.clean(
            raw,
            tags=_TAGS,
            attributes=_ATTRIBUTES,
            url_schemes=_SCHEMES,
            link_rel="noopener noreferrer nofollow",
        )
        result = Markup(clean)  # noqa: S704 - sanitized by nh3 just above
        with self._lock:
            self._cache[note.slug] = result
        return result

    def excerpt(self, note: Note, limit: int = 220) -> str:
        """The first paragraph of prose as plain text, for lists."""
        body = _FENCE_BLOCK.sub("", _LEADING_H1.sub("", note.body, count=1))
        paragraph: list[str] = []
        for line in [*body.splitlines(), ""]:
            stripped = line.strip()
            if stripped.startswith(("#", "|", "---", "<")) or not stripped:
                if paragraph:
                    break
                continue
            paragraph.append(stripped)
        text = " ".join(paragraph)
        text = _WIKILINK.sub(lambda m: m.group(4) or m.group(2), text)
        text = re.sub(r"[*_`>\[\]]", "", text)
        text = re.sub(r"^[-+] ", "", re.sub(r"\s+", " ", text)).strip()
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
