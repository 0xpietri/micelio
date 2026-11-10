from __future__ import annotations

import os
from pathlib import Path

import pytest

from micelio.vault import Edge, VaultIndex
from micelio.vault import index as index_module

from .conftest import VaultFactory, config_for


def kinds(index: VaultIndex) -> list[tuple[str, str]]:
    return sorted((i.kind, i.path) for i in index.issues)


# -- the sample vault ---------------------------------------------------------


def test_example_vault_counts(example_index: VaultIndex) -> None:
    types = [n.type for n in example_index.notes.values()]
    assert types.count("project") == 5
    assert types.count("journal") == 2
    assert types.count("source") == 2
    assert len(example_index.notes) == 27


def test_skips_hidden_folders_and_sync_conflicts(example_index: VaultIndex) -> None:
    paths = {n.path for n in example_index.notes.values()}
    assert not any(".obsidian" in p or "sync-conflict" in p for p in paths)


def test_example_vault_only_issue_is_the_ghost(example_index: VaultIndex) -> None:
    assert kinds(example_index) == [
        ("broken-link", "notes/Can planetary gravity affect a newborn.md")
    ]
    assert example_index.ghosts == {
        "Tidal forces explained": {"can-planetary-gravity-affect-a-newborn"}
    }


def test_bridges_and_categories(example_index: VaultIndex) -> None:
    bridges = {s for s in example_index.notes if example_index.is_bridge(s)}
    assert bridges == {
        "is-a-measured-tendency-a-cause",
        "priors-are-beliefs-you-can-update",
        "effects-too-small-to-matter-can-still-be-real",
    }
    assert example_index.categories_of("priors-are-beliefs-you-can-update") == {
        "philosophy",
        "study",
    }
    assert example_index.categories_of("learning-bayesian-statistics") == {"study"}
    assert example_index.categories_of("a-stray-thought-with-no-home") == set()


def test_membership_and_backlinks(example_index: VaultIndex) -> None:
    members = example_index.members["learning-bayesian-statistics"]
    assert "bayes-theorem-in-one-line" in members
    assert example_index.projects_of["bayes-theorem-in-one-line"] == {
        "learning-bayesian-statistics"
    }
    assert "learning-bayesian-statistics" in example_index.backlinks["bayes-theorem-in-one-line"]


def test_alias_accent_and_code_links(example_index: VaultIndex) -> None:
    assert example_index.resolve("Bayes rule") == "bayes-theorem-in-one-line"
    assert example_index.resolve("café conversations shape ideas") == (
        "cafe-conversations-shape-ideas"
    )
    targets = {link.target for n in example_index.notes.values() for link in n.links}
    assert not any("code" in t.lower() and "not" in t.lower() for t in targets)


def test_orphans_and_projects(example_index: VaultIndex) -> None:
    assert example_index.orphans() == ["a-stray-thought-with-no-home", "an-abandoned-idea"]
    titles = [p.title for p in example_index.projects()]
    assert titles == sorted(titles, key=str.lower)


def test_public_flag(example_index: VaultIndex) -> None:
    assert example_index.notes["learning-bayesian-statistics"].public is True
    assert example_index.notes["free-will-in-a-determined-world"].public is False


# -- focused vaults -------------------------------------------------------------


def test_type_from_folder_and_frontmatter(make_vault: VaultFactory) -> None:
    index = make_vault(
        {
            "projects/P.md": "# P\n",
            "notes/N.md": "---\ntype: source\n---\n",
            "Loose.md": "text",
            "notes/Odd.md": "---\ntype: essay\n---\n",
        }
    )
    assert index.notes["p"].type == "project"
    assert index.notes["n"].type == "source"
    assert index.notes["loose"].type == "note"
    assert index.notes["odd"].type == "note"
    assert ("unknown-type", "notes/Odd.md") in kinds(index)


def test_frontmatter_problems_are_issues(make_vault: VaultFactory) -> None:
    index = make_vault(
        {
            "projects/A.md": "---\ncategory: cooking\nstatus: dreaming\n---\n",
            "notes/B.md": "---\ncategory: science\n---\n",
            "notes/C.md": "---\n[broken\n---\n",
        }
    )
    assert kinds(index) == [
        ("category-ignored", "notes/B.md"),
        ("frontmatter", "notes/C.md"),
        ("unknown-category", "projects/A.md"),
        ("unknown-status", "projects/A.md"),
    ]
    assert index.notes["a"].category is None
    assert index.notes["a"].status is None


def test_tags_and_aliases_are_normalized(make_vault: VaultFactory) -> None:
    index = make_vault(
        {
            "notes/A.md": "---\ntags: '#one, two, one'\naliases: [X, null, 3]\n---\n",
            "notes/B.md": "---\ntags: 7\n---\n",
        }
    )
    assert index.notes["a"].tags == ("one", "two")
    assert index.notes["a"].aliases == ("X", "3")
    assert index.notes["b"].tags == ("7",)


def test_slug_collision_falls_back_to_path(make_vault: VaultFactory) -> None:
    index = make_vault({"Idea.md": "", "notes/Idea.md": ""})
    assert index.notes["idea"].path == "Idea.md"
    assert index.notes["notes-idea"].path == "notes/Idea.md"


def test_resolution_prefers_shortest_path_and_supports_paths(make_vault: VaultFactory) -> None:
    index = make_vault(
        {
            "notes/deep/Idea.md": "",
            "notes/Idea.md": "",
            "journal/Day.md": "[[Idea]] [[deep/Idea]] [[notes/Idea.md]] [[nowhere/Idea]]",
        }
    )
    assert index.resolve("Idea") == "idea"
    assert index.resolve("deep/Idea") == "notes-deep-idea"
    assert index.resolve("/notes/Idea.md") == "idea"
    assert index.resolve("nowhere/Idea") == "idea"
    assert index.resolve("Missing") is None


def test_edges_skip_self_links_and_duplicates(make_vault: VaultFactory) -> None:
    index = make_vault({"notes/A.md": "[[A]] [[B]] [[b]]", "notes/B.md": ""})
    assert index.edges == [Edge("a", "b")]
    assert index.backlinks["b"] == {"a"}


def test_projects_are_not_members_of_projects(make_vault: VaultFactory) -> None:
    index = make_vault({"projects/A.md": "[[B]] [[N]]", "projects/B.md": "", "notes/N.md": ""})
    assert index.members["a"] == {"n"}


def test_large_files_are_skipped(make_vault: VaultFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_module, "MAX_NOTE_BYTES", 10)
    index = make_vault({"notes/Big.md": "x" * 50, "notes/Small.md": "x"})
    assert set(index.notes) == {"small"}
    assert ("too-large", "notes/Big.md") in kinds(index)


def test_only_markdown_files(make_vault: VaultFactory) -> None:
    index = make_vault({"notes/A.MD": "", "notes/pic.png": "", ".trash/Old.md": ""})
    assert set(index.notes) == {"a"}


def test_missing_root_gives_empty_index(tmp_path: Path) -> None:
    index = VaultIndex(config_for(tmp_path / "nope"))
    assert index.refresh(force=True) is True
    assert index.notes == {}


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_symlinks_leaving_the_vault_are_ignored(tmp_path: Path) -> None:
    outside = tmp_path / "secret.md"
    outside.write_text("secret", encoding="utf-8")
    root = tmp_path / "vault"
    root.mkdir()
    (root / "Inside.md").write_text("", encoding="utf-8")
    (root / "Link.md").symlink_to(outside)
    (root / "Alias.md").symlink_to(root / "Inside.md")
    index = VaultIndex(config_for(root))
    index.refresh(force=True)
    assert set(index.notes) == {"alias", "inside"}


# -- freshness ------------------------------------------------------------------


def test_refresh_is_throttled_and_picks_up_changes(
    make_vault: VaultFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [1000.0]
    monkeypatch.setattr(index_module.time, "monotonic", lambda: clock[0])
    index = make_vault({"notes/A.md": "# A\n"})
    note = index.root / "notes" / "A.md"

    assert index.refresh() is False  # within the throttle window
    clock[0] += 5
    assert index.refresh() is False  # nothing changed

    note.write_text("# A renamed\n[[B]]\n", encoding="utf-8")
    st = note.stat()
    os.utime(note, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    (index.root / "notes" / "B.md").write_text("", encoding="utf-8")
    clock[0] += 5
    assert index.refresh() is True
    assert index.notes["a"].title == "A renamed"
    assert index.edges == [Edge("a", "b")]

    note.unlink()
    clock[0] += 5
    assert index.refresh() is True
    assert set(index.notes) == {"b"}


def test_unchanged_files_are_not_reparsed(
    make_vault: VaultFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = make_vault({"notes/A.md": "# A\n", "notes/B.md": "# B\n"})
    calls: list[str] = []
    real = index_module.parse_note

    def spy(text: str, *, fallback_title: str) -> object:
        calls.append(fallback_title)
        return real(text, fallback_title=fallback_title)

    monkeypatch.setattr(index_module, "parse_note", spy)
    (index.root / "notes" / "C.md").write_text("", encoding="utf-8")
    index.refresh(force=True)
    assert calls == ["C"]


def test_attachments_are_not_ghosts(make_vault: VaultFactory) -> None:
    index = make_vault({"notes/A.md": "![[photo.PNG]] [[file.pdf]] [[Version 1.5]] [[B]]"})
    # A missing "Version 1.5" looks like a file with a ".5" extension: not a ghost either.
    assert set(index.ghosts) == {"B"}
    assert ("broken-link", "notes/A.md") in kinds(index)


def test_generation_changes_on_rebuild(make_vault: VaultFactory) -> None:
    index = make_vault({"notes/A.md": ""})
    before = index.generation
    index.refresh(force=True)
    assert index.generation == before + 1
