"""The owner edits a whole note from the site (§8a): any block, a section, the whole
body, and Undo. The frontmatter is never changed, except edited_by and updated."""

from __future__ import annotations

from pathlib import Path

import pytest

from micelio.editing import Edit, EditError, NoteEditor, file_hash

from .test_said_edit import NOTE, TODAY, apply, body


@pytest.fixture
def editor(tmp_path: Path) -> NoteEditor:
    (tmp_path / "vault" / "notes").mkdir(parents=True)
    (tmp_path / "vault" / "notes" / "n.md").write_text(NOTE, encoding="utf-8")
    return NoteEditor(tmp_path / "vault", tmp_path / "data" / "edits", "marcos")


def front(text: str) -> str:
    return text.split("---\n", 2)[1]


def test_any_block_can_be_changed(editor: NoteEditor) -> None:
    text = apply(editor, Edit("block", start=2, text="A new\n\nfirst part."))
    assert body(text).startswith("# Title\n\nA new\n\nfirst part.\n\n> [!said]\n")
    assert "Second paragraph." in text


def test_a_block_written_empty_is_deleted(editor: NoteEditor) -> None:
    text = apply(editor, Edit("block", start=8, text="  \n"))
    assert "Second paragraph" not in text
    assert "> my **own** words\n\n## Links\n" in text


def test_drop_deletes_any_block_a_callout_too(editor: NoteEditor) -> None:
    text = apply(editor, Edit("drop", start=5))
    assert "[!said]" not in text
    assert "goes on.\n\nSecond paragraph.\n" in text


def test_a_section_goes_with_everything_under_it(editor: NoteEditor) -> None:
    path = editor.root / "notes" / "n.md"
    path.write_text(
        NOTE + "\n### Sub\nunder links\n\n> [!takeaway]\n> keep in mind\n\n## Next\nstays\n",
        encoding="utf-8",
    )
    text = apply(editor, Edit("section", start=10))
    assert "## Links" not in text
    assert "### Sub" not in text
    assert "takeaway" not in text
    assert "Second paragraph.\n\n## Next\nstays\n" in text


def test_a_section_needs_a_heading(editor: NoteEditor) -> None:
    with pytest.raises(EditError) as refused:
        apply(editor, Edit("section", start=8))
    assert refused.value.code == "not-heading"


def test_no_block_starts_inside_another(editor: NoteEditor) -> None:
    with pytest.raises(EditError) as refused:
        apply(editor, Edit("drop", start=3))
    assert refused.value.code == "not-block"


def test_the_whole_body_keeps_the_frontmatter(editor: NoteEditor) -> None:
    text = apply(editor, Edit("body", text="# Title\n\nAll new.\n"))
    assert body(text) == "# Title\n\nAll new.\n"
    assert "tags: [a]" in front(text)
    assert "edited_by: marcos" in front(text)
    assert "updated: 2026-11-11" in front(text)


def test_an_empty_body_is_refused(editor: NoteEditor) -> None:
    with pytest.raises(EditError) as refused:
        apply(editor, Edit("body", text="\n \n"))
    assert refused.value.code == "empty"


def test_a_note_without_frontmatter_never_gets_one(editor: NoteEditor) -> None:
    path = editor.root / "notes" / "n.md"
    path.write_text("Just text.\n", encoding="utf-8")
    with pytest.raises(EditError) as refused:
        apply(editor, Edit("body", text="---\ntype: note\n---\nHi\n"))
    assert refused.value.code == "frontmatter"
    assert path.read_text(encoding="utf-8") == "Just text.\n"


def test_source_of_the_body_and_of_a_block(editor: NoteEditor) -> None:
    assert editor.source("notes/n.md") == body(NOTE).strip("\n")
    assert editor.source("notes/n.md", 2) == "First paragraph\ngoes on."
    assert editor.source("notes/n.md", 10) == "## Links"


def test_undo_walks_back_the_sites_changes(editor: NoteEditor) -> None:
    path = editor.root / "notes" / "n.md"
    rel = "notes/n.md"
    assert not editor.undoable(rel, file_hash(path))
    apply(editor, Edit("drop", start=8))
    once = path.read_text(encoding="utf-8")
    apply(editor, Edit("section", start=8))
    assert editor.undoable(rel, file_hash(path))
    editor.apply(rel, file_hash(path), Edit("undo"), TODAY)
    assert path.read_text(encoding="utf-8") == once
    editor.apply(rel, file_hash(path), Edit("undo"), TODAY)
    assert path.read_text(encoding="utf-8") == NOTE
    with pytest.raises(EditError) as refused:
        editor.apply(rel, file_hash(path), Edit("undo"), TODAY)
    assert refused.value.code == "nothing"


def test_undo_never_throws_away_someone_elses_words(editor: NoteEditor) -> None:
    path = editor.root / "notes" / "n.md"
    apply(editor, Edit("drop", start=8))
    path.write_text(path.read_text(encoding="utf-8") + "\nThe MCP wrote this.\n", "utf-8")
    assert not editor.undoable("notes/n.md", file_hash(path))
    with pytest.raises(EditError) as refused:
        editor.apply("notes/n.md", file_hash(path), Edit("undo"), TODAY)
    assert refused.value.code == "not-last"
    assert "The MCP wrote this." in path.read_text(encoding="utf-8")
