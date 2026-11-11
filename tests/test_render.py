from __future__ import annotations

import pytest
from markupsafe import Markup

from micelio.render import Renderer, fill_callout_titles
from micelio.vault import VaultIndex

from .conftest import VaultFactory


@pytest.fixture
def vault(make_vault: VaultFactory) -> VaultIndex:
    return make_vault(
        {
            "projects/Big idea.md": "---\ncategory: science\n---\n# Big idea\n[[Target]]",
            "notes/Target.md": "---\naliases: [Alias]\n---\n# The target note\n",
            "notes/Page.md": "placeholder",
        }
    )


def render(vault: VaultIndex, body: str) -> str:
    note = vault.notes["page"]
    note.body = body
    vault.generation += 1  # the body changed behind the index's back
    return str(Renderer(vault).html(note))


def test_wikilinks(vault: VaultIndex) -> None:
    html = render(vault, "[[Target]] [[Alias|label]] [[Target#Part]] [[Big idea]]")
    assert '<a class="wikilink" href="/notes/target"' in html
    assert ">The target note</a>" in html
    assert ">label</a>" in html
    assert ">Target &gt; Part</a>" in html
    assert 'href="/projects/big-idea"' in html


def test_ghosts_and_attachments(vault: VaultIndex) -> None:
    html = render(vault, "[[Nowhere]] and ![[photo.jpg]]")
    assert '<span class="ghost" title="Nowhere">Nowhere</span>' in html
    assert '<span class="attachment">photo.jpg</span>' in html


def test_wikilinks_in_code_stay_text(vault: VaultIndex) -> None:
    html = render(vault, "`[[Target]]`\n\n```\n[[Target]]\n```")
    assert "wikilink" not in html
    assert html.count("[[Target]]") == 2


def test_leading_title_is_not_repeated(vault: VaultIndex) -> None:
    html = render(vault, "# Title\n\nBody\n\n# Later heading")
    assert "Title" not in html
    assert "<h1>Later heading</h1>" in html


@pytest.mark.parametrize(
    "dangerous",
    [
        "<script>alert(1)</script>",
        '<img src="x" onerror="alert(1)">',
        '<a href="javascript:alert(1)">x</a>',
        "[x](javascript:alert(1))",
        '<iframe src="https://evil.example"></iframe>',
        '<div style="background:url(x)">x</div>',
        "<style>body{display:none}</style>",
        '<form action="https://evil.example"><input name="p"></form>',
    ],
)
def test_html_is_sanitized(vault: VaultIndex, dangerous: str) -> None:
    html = render(vault, f"before\n\n{dangerous}\n\nafter").lower()
    for bad in ("<script", "onerror", 'href="javascript:', "<iframe", "style=", "<style", "<form"):
        assert bad not in html
    assert "after" in html


def test_external_links_get_rel(vault: VaultIndex) -> None:
    html = render(vault, "[site](https://example.com)")
    assert 'href="https://example.com"' in html
    assert "noopener" in html


def test_callouts(vault: VaultIndex) -> None:
    html = render(vault, "> [!warning] Careful\n> Body text\n\n> [!tip]\n> Only body\n\n> plain")
    assert '<div class="callout callout-warning">' in html
    assert '<p class="callout-title">Careful</p>' in html
    assert "<p>Body text</p>" in html
    assert '<p class="callout-title">Tip</p>' in html
    assert "<blockquote>" in html


def test_callout_with_title_only(vault: VaultIndex) -> None:
    html = render(vault, "> [!info] Just a title")
    assert '<p class="callout-title">Just a title</p>' in html
    assert "<p></p>" not in html


def test_task_lists_tables_footnotes(vault: VaultIndex) -> None:
    html = render(
        vault, "- [ ] open\n- [x] done\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nx[^1]\n\n[^1]: f"
    )
    assert 'type="checkbox"' in html
    assert "checked" in html
    assert "<table>" in html
    assert 'class="footnotes"' in html


def test_cache_follows_the_vault(make_vault: VaultFactory) -> None:
    vault = make_vault({"notes/A.md": "[[B]]"})
    renderer = Renderer(vault)
    assert "ghost" in renderer.html(vault.notes["a"])
    (vault.root / "notes" / "B.md").write_text("", encoding="utf-8")
    vault.refresh(force=True)
    assert 'href="/notes/b"' in renderer.html(vault.notes["a"])


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("# T\n## Heading\nFirst line\nsecond line\n\nNext", "First line second line"),
        ("Talk about [[Target|that]] and **bold** `code`", "Talk about that and bold code"),
        ("```\ncode only\n```\n\n- a list item", "a list item"),
        ("# Only a title", ""),
        ("word " * 100, ("word " * 100)[:219].rstrip() + "…"),
    ],
)
def test_excerpt(vault: VaultIndex, body: str, expected: str) -> None:
    note = vault.notes["page"]
    note.body = body
    assert Renderer(vault).excerpt(note) == expected


def test_said_and_takeaway_callouts_have_no_heading(vault: VaultIndex) -> None:
    html = render(vault, "> [!said]\n> Exactly as I said it.\n\n> [!takeaway]\n>\n> Closing line.")
    assert '<div class="callout callout-said">' in html
    assert "<p>Exactly as I said it.</p>" in html
    assert '<div class="callout callout-takeaway">' in html
    assert "<p>Closing line.</p>" in html
    # The bubble has no heading; the sign keeps a placeholder for its default one.
    assert html.count("callout-title") == 2
    assert '<p class="callout-title callout-title-takeaway"></p>' in html
    assert "<p></p>" not in html


def test_takeaway_gets_its_default_title_in_the_readers_language(vault: VaultIndex) -> None:
    html = render(vault, "> [!takeaway]\n> Closing line.\n\n> [!takeaway] Own title\n> More")
    filled = fill_callout_titles(Markup(html), {"takeaway": "Lo que <tendrías> saber"})  # noqa: S704
    assert (
        '<p class="callout-title callout-title-takeaway">Lo que &lt;tendrías&gt; saber</p>'
        in filled
    )
    assert '<p class="callout-title">Own title</p>' in filled


def test_said_callout_keeps_a_given_heading(vault: VaultIndex) -> None:
    html = render(vault, "> [!said] Marcos\n> Words")
    assert '<p class="callout-title">Marcos</p>' in html
