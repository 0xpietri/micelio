"""The owner's said bubbles written into the vault (§8a): the one write Micelio makes."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from micelio.app import create_app
from micelio.editing import KEEP_VERSIONS, Edit, EditError, SaidEditor, file_hash, said_lines
from micelio.render import Renderer

from .conftest import VaultFactory, config_for
from .test_auth_web import ENV, START, Site

TODAY = date(2026, 11, 11)
NOTE = (
    "---\ntype: note\ntags: [a]\nedited_by: claude-opus-5-5   # who\nupdated: 2026-01-01\n---\n"
    "# Title\n"
    "\n"
    "First paragraph\n"  # body line 2
    "goes on.\n"
    "\n"
    "> [!said]\n"  # body line 5
    "> my **own** words\n"
    "\n"
    "Second paragraph.\n"  # body line 8
    "\n"
    "## Links\n"  # body line 10
    "- [[Other]]\n"
)


@pytest.fixture
def editor(tmp_path: Path) -> SaidEditor:
    (tmp_path / "vault" / "notes").mkdir(parents=True)
    (tmp_path / "vault" / "notes" / "n.md").write_text(NOTE, encoding="utf-8")
    return SaidEditor(tmp_path / "vault", tmp_path / "data" / "edits", "marcos")


def apply(editor: SaidEditor, edit: Edit) -> str:
    path = editor.root / "notes" / "n.md"
    editor.apply("notes/n.md", file_hash(path), edit, TODAY)
    return path.read_text(encoding="utf-8")


def body(text: str) -> str:
    return text.split("---\n", 2)[2]


def test_said_lines_quote_every_line() -> None:
    assert said_lines("one\n\ntwo\n") == ["> [!said]", "> one", ">", "> two"]
    assert said_lines("x", "Title") == ["> [!said] Title", "> x"]


def test_insert_between_two_paragraphs(editor: SaidEditor) -> None:
    text = apply(editor, Edit("insert", at=8, text="new words"))
    assert "> my **own** words\n\n> [!said]\n> new words\n\nSecond paragraph." in text


def test_insert_at_the_end_and_before_the_first_block(editor: SaidEditor) -> None:
    text = apply(editor, Edit("insert", at=12, text="last"))
    assert text.endswith("- [[Other]]\n\n> [!said]\n> last\n")
    text = apply(editor, Edit("insert", at=2, text="first"))
    assert "# Title\n\n> [!said]\n> first\n\nFirst paragraph" in text


def test_frontmatter_gets_edited_by_and_updated_and_nothing_else(editor: SaidEditor) -> None:
    text = apply(editor, Edit("insert", at=8, text="x"))
    head = text.split("---\n")[1]
    assert head == "type: note\ntags: [a]\nedited_by: marcos\nupdated: 2026-11-11\n"


def test_no_place_inside_a_block(editor: SaidEditor) -> None:
    for at in (3, 6, 99, None):
        with pytest.raises(EditError) as error:
            apply(editor, Edit("insert", at=at, text="x"))
        assert error.value.code == "place"


def test_edit_keeps_its_place(editor: SaidEditor) -> None:
    assert editor.words("notes/n.md", 5) == "my **own** words"
    text = apply(editor, Edit("edit", start=5, text="changed\nin two lines"))
    assert "goes on.\n\n> [!said]\n> changed\n> in two lines\n\nSecond paragraph." in text


def test_delete_leaves_one_empty_line(editor: SaidEditor) -> None:
    text = apply(editor, Edit("delete", start=5))
    assert body(text) == NOTE.split("---\n", 2)[2].replace("> [!said]\n> my **own** words\n\n", "")


def test_move_down_and_back_up(editor: SaidEditor) -> None:
    text = apply(editor, Edit("move", start=5, at=12))
    assert "goes on.\n\nSecond paragraph." in text
    assert text.endswith("- [[Other]]\n\n> [!said]\n> my **own** words\n")
    text = apply(editor, Edit("move", start=10, at=2))
    assert "# Title\n\n> [!said]\n> my **own** words\n\nFirst paragraph\ngoes on.\n\nSecond" in text


def test_only_said_bubbles_change(editor: SaidEditor) -> None:
    for start in (2, 8, 10, 4):
        with pytest.raises(EditError) as error:
            apply(editor, Edit("delete", start=start))
        assert error.value.code == "not-said"


def test_a_changed_file_is_never_written(editor: SaidEditor) -> None:
    path = editor.root / "notes" / "n.md"
    seen = file_hash(path)
    path.write_text(NOTE + "\nWritten by the MCP meanwhile.\n", encoding="utf-8")
    with pytest.raises(EditError) as error:
        editor.apply("notes/n.md", seen, Edit("insert", at=8, text="x"), TODAY)
    assert error.value.code == "changed"
    assert error.value.status == 409
    assert path.read_text(encoding="utf-8").endswith("meanwhile.\n")


def test_empty_words_and_unknown_ops_are_refused(editor: SaidEditor) -> None:
    for edit in (Edit("insert", at=8, text="  \n"), Edit("rename", start=5)):
        with pytest.raises(EditError):
            apply(editor, edit)


def test_line_endings_permissions_and_no_temporary_files(editor: SaidEditor) -> None:
    path = editor.root / "notes" / "n.md"
    path.write_bytes(NOTE.replace("\n", "\r\n").encode())
    path.chmod(0o640)
    mode = path.stat().st_mode & 0o777  # 0o640 on POSIX; Windows keeps only read-only
    apply(editor, Edit("insert", at=8, text="x"))
    raw = path.read_bytes()
    assert b"\r\n> [!said]\r\n> x\r\n" in raw
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert path.stat().st_mode & 0o777 == mode
    assert sorted(p.name for p in path.parent.iterdir()) == ["n.md"]


def test_versions_replaced_are_kept_in_the_data_folder(editor: SaidEditor) -> None:
    apply(editor, Edit("insert", at=8, text="x"))
    kept = list(editor.history.iterdir())
    assert len(kept) == 1
    assert kept[0].read_text(encoding="utf-8") == NOTE
    for _ in range(KEEP_VERSIONS + 3):
        apply(editor, Edit("edit", start=5, text="again"))
    assert len(list(editor.history.iterdir())) == KEEP_VERSIONS


def test_paths_outside_the_vault_are_refused(editor: SaidEditor) -> None:
    for rel in ("../outside.md", "notes/n.txt"):
        with pytest.raises(EditError):
            editor.apply(rel, "x", Edit("delete", start=5), TODAY)


# -- the website ------------------------------------------------------------------------

SiteFor = Callable[..., Site]


@pytest.fixture
def site_for(tmp_path: Path) -> Iterator[SiteFor]:
    with ExitStack() as stack:

        def factory(*, editing: bool = True) -> Site:
            root = tmp_path / "vault"
            (root / "notes").mkdir(parents=True, exist_ok=True)
            (root / "notes" / "n.md").write_text(NOTE.replace("type: note", "public: true"))
            config = config_for(root, data=tmp_path / "data")
            config = config.model_copy(
                update={"editing": config.editing.model_copy(update={"enabled": editing})}
            )
            app = create_app(config, environ=ENV, clock=lambda: START)
            client = stack.enter_context(TestClient(app, base_url="https://micelio.example"))
            return Site(client, [START])

        yield factory


def page_keys(site: Site) -> dict[str, str]:
    html = site.client.get("/notes/n").text
    found = dict(re.findall(r'data-said-(url|hash|token)="([^"]*)"', html))
    return found


def test_the_owner_page_carries_lines_and_keys(site_for: SiteFor) -> None:
    site = site_for()
    site.sign_in()
    html = site.client.get("/notes/n").text
    assert 'data-l="2-4"' in html
    assert 'class="callout callout-said" data-l="5-7"' in html
    assert "said-edit.js" in html
    keys = page_keys(site)
    assert keys["url"] == "/api/notes/n/said"


def test_the_owner_inserts_a_bubble(site_for: SiteFor, tmp_path: Path) -> None:
    site = site_for()
    site.sign_in()
    keys = page_keys(site)
    sent = {"op": "insert", "at": 8, "text": "hello", "hash": keys["hash"]}
    response = site.client.post(keys["url"], json=sent, headers={"x-micelio-form": keys["token"]})
    assert response.status_code == 200, response.text
    assert "> [!said]\n> hello\n" in (tmp_path / "vault" / "notes" / "n.md").read_text()
    # The page shows it at once, with the new hash; the old one is refused now.
    assert "<p>hello</p>" in site.client.get("/notes/n").text
    again = site.client.post(keys["url"], json=sent, headers={"x-micelio-form": keys["token"]})
    assert again.status_code == 409
    assert again.json()["error"] == "changed"


def test_words_of_a_bubble(site_for: SiteFor) -> None:
    site = site_for()
    site.sign_in()
    response = site.client.get("/api/notes/n/said?start=5")
    assert response.json() == {"ok": True, "text": "my **own** words"}


def test_a_wrong_key_writes_nothing(site_for: SiteFor, tmp_path: Path) -> None:
    site = site_for()
    site.sign_in()
    keys = page_keys(site)
    sent = {"op": "delete", "start": 5, "hash": keys["hash"]}
    response = site.client.post(keys["url"], json=sent, headers={"x-micelio-form": "nope"})
    assert response.status_code == 403
    assert (tmp_path / "vault" / "notes" / "n.md").read_text() == NOTE.replace(
        "type: note", "public: true"
    )


def test_visitors_get_nothing(site_for: SiteFor) -> None:
    site = site_for()
    html = site.client.get("/notes/n").text
    assert "data-said" not in html
    assert "data-l=" not in html
    assert "said-edit.js" not in html
    words = site.client.get("/api/notes/n/said?start=5", follow_redirects=False)
    assert words.status_code in (303, 401, 404)
    response = site.client.post("/api/notes/n/said", json={"op": "delete", "start": 5})
    assert response.status_code in (401, 404)


def test_editing_off_by_default(site_for: SiteFor) -> None:
    site = site_for(editing=False)
    site.sign_in()
    html = site.client.get("/notes/n").text
    assert "data-said" not in html
    assert "data-l=" not in html
    assert site.client.post("/api/notes/n/said", json={}).status_code == 404


def test_hidden_parts_keep_the_line_numbers(make_vault: VaultFactory) -> None:
    """The title and a project's guide are not shown, but blanked, never cut: the numbers
    on the blocks after them are still the note's own lines."""
    text = "---\ntype: project\n---\n# P\n\nIntro.\n\n## Guía\n- [[a]]\n- [[b]]\n\n## After\nEnd.\n"
    index = make_vault({"projects/P.md": text})
    html = Renderer(index, guide_headings=["Guía"], anchors=True).html(index.notes["p"])
    assert '<p data-l="2-3">Intro.</p>' in html
    assert '<h2 data-l="8-9">After</h2>' in html
    assert '<p data-l="9-10">End.</p>' in html
    assert "data-l" not in Renderer(index, guide_headings=["Guía"]).html(index.notes["p"])
