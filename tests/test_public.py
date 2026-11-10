"""Public notes (§9): anonymous visitors see only notes with ``public: true``.

The core test crawls every page an anonymous visitor can reach and checks that no
private title, path, slug, tag or alias appears in any response.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from micelio.app import create_app
from micelio.config import Config, VaultConfig
from micelio.render import Renderer
from micelio.vault import PublicView, VaultIndex

from .conftest import EXAMPLE_VAULT, VaultFactory, config_for
from .test_auth_web import ENV, START, Site

# Every private name below carries this marker, so one search finds any leak.
MARK = "xq"

VAULT = {
    "projects/Open garden.md": (
        "---\ntype: project\ncategory: science\nstatus: active\npublic: true\n---\n"
        "# Open garden\n\nNotes: [[Seed idea]], [[Shared root]], [[Hidden thing]], "
        "[[Nowhere at all]].\n"
    ),
    "projects/Vault xq plan.md": (
        "---\ntype: project\ncategory: philosophy\nstatus: active\n"
        "tags: [tagxq]\n---\n# Secret xq plan\n\n[[Shared root]] [[Seed idea]] [[Lonely xq]]\n"
    ),
    "notes/Seed idea.md": (
        "---\npublic: true\ntags: [garden]\n---\n# Seed idea\n\n"
        "It grows from [[Hidden thing]] and from [[Shared root|the root]].\n"
    ),
    "notes/Shared root.md": "---\npublic: true\n---\n# Shared root\n\nA common base.\n",
    "notes/Private xq.md": (
        "---\naliases: [Hidden thing]\ntags: [tagxq]\n---\n# Secret note xq\n\n"
        "Links back to [[Seed idea]].\n"
    ),
    "notes/Lonely xq.md": "# Lonely xq\n\nOnly the private project knows me.\n",
    "journal/2026-11-01 Chat xq.md": (
        "---\ncreated: 2026-11-01\n---\n# Chat xq\n\nAbout [[Seed idea]] and [[Open garden]].\n"
    ),
    "journal/2026-11-02 Open chat.md": (
        "---\npublic: true\ncreated: 2026-11-02\n---\n# Open chat\n\nAbout [[Seed idea]].\n"
    ),
    "sources/Source xq.md": "# Source xq\n\nCited by [[Seed idea]].\n",
    "sources/Open source.md": "---\npublic: true\n---\n# Open source\n\n[[Seed idea]]\n",
}

SiteFor = Callable[..., Site]


@pytest.fixture
def site_for(tmp_path: Path) -> Iterator[SiteFor]:
    """A site with sign-in on, over the given files (or the sample vault)."""
    with ExitStack() as stack:

        def factory(files: dict[str, str] | None = None, language: str = "en") -> Site:
            root = EXAMPLE_VAULT
            if files is not None:
                root = tmp_path / "vault"
                for rel, text in files.items():
                    path = root / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
                root.mkdir(exist_ok=True)
            config = config_for(root, data=tmp_path / "data")
            config = config.model_copy(
                update={"site": config.site.model_copy(update={"language": language})}
            )
            now = [START]
            app = create_app(config, environ=ENV, clock=lambda: now[0])
            client = stack.enter_context(TestClient(app, base_url="https://micelio.example"))
            return Site(client, now)

        yield factory


_HREF = re.compile(r'(?:href|data-graph)="(/[^"#]*)"')
_JSON_HREF = re.compile(r'"href":\s*"(/[^"]*)"')
_START = (
    "/",
    "/api/landing",
    "/explore",
    "/api/graph",
    "/projects",
    "/journal",
    "/healthz",
    "/theme.css",
    "/static/locales/en.json",
    "/static/locales/es.json",
    "/no-such-page",
    "/notes/no-such-note",
)


def crawl(client: TestClient) -> dict[str, str]:
    """Every same-site page reachable without signing in, by following links."""
    seen: dict[str, str] = {}
    queue = list(_START)
    while queue:
        path = queue.pop()
        if path in seen or path.startswith(("/static/vendor/", "/static/js/", "/static/css/")):
            continue
        response = client.get(path.replace("&amp;", "&"), follow_redirects=False)
        seen[path] = response.text
        if response.status_code in (301, 302, 303, 307, 308):
            target = response.headers["location"]
            if not target.startswith("/login"):
                queue.append(target)
            continue
        for found in [*_HREF.findall(response.text), *_JSON_HREF.findall(response.text)]:
            if not found.startswith(("/login", "/static/img/")):
                queue.append(found)
    return seen


def test_no_private_name_in_any_anonymous_response(site_for: SiteFor) -> None:
    site = site_for(VAULT)
    pages = crawl(site.client)
    assert "/notes/seed-idea" in pages
    assert "/projects/open-garden" in pages
    assert "/api/graph?scope=project%3Aopen-garden" in pages
    assert "/api/graph?scope=note%3Aseed-idea" in pages
    for path, body in pages.items():
        assert MARK not in body.lower(), path


def test_signed_in_still_sees_everything(site_for: SiteFor) -> None:
    site = site_for(VAULT)
    site.sign_in()
    assert "Secret xq plan" in site.client.get("/projects").text
    nodes = site.client.get("/api/graph").json()["nodes"]
    assert any(n["title"] == "Secret note xq" for n in nodes)
    assert any(n["ghost"] for n in nodes)
    assert "Secret note xq" in site.client.get("/notes/seed-idea").text


@pytest.mark.parametrize(
    "path",
    [
        "/notes/private-xq",
        "/notes/lonely-xq",
        "/notes/2026-11-01-chat-xq",
        "/notes/source-xq",
        "/projects/vault-xq-plan",
        "/notes/vault-xq-plan",
        "/api/graph?scope=note:private-xq",
        "/api/graph?scope=project:vault-xq-plan",
    ],
)
def test_private_notes_do_not_exist_for_visitors(site_for: SiteFor, path: str) -> None:
    response = site_for(VAULT).client.get(path, follow_redirects=False)
    assert response.status_code == 404
    # The sign-in link echoes the path the visitor typed; nothing else may name the note.
    assert MARK not in re.sub(r'next=[^"]*', "", response.text).lower()


def test_links_to_private_or_missing_notes_are_plain_text(site_for: SiteFor) -> None:
    client = site_for(VAULT).client
    seed = client.get("/notes/seed-idea").text
    assert "It grows from Hidden thing and from" in seed
    assert 'href="/notes/shared-root" rel="noopener noreferrer nofollow">the root</a>' in seed
    garden = client.get("/projects/open-garden").text
    assert "Nowhere at all" in garden
    assert 'class="ghost"' not in garden
    assert 'class="ghost"' not in seed


def test_public_counts_leave_private_notes_out(site_for: SiteFor) -> None:
    client = site_for(VAULT).client
    projects = client.get("/projects").text
    assert "2 notes" in projects
    landing = client.get("/api/landing").json()
    assert [p["id"] for p in landing["projects"]] == ["open-garden"]
    assert landing["projects"][0]["notes"] == 2
    assert landing["hidden"] == 0
    assert [j["id"] for j in landing["journal"]] == ["2026-11-02-open-chat"]
    graph = client.get("/api/graph").json()
    degree = {n["id"]: n["degree"] for n in graph["nodes"]}
    # Seed idea: linked from the project, the open chat and the source; links Shared root.
    assert degree["seed-idea"] == 4
    assert {n["type"] for n in graph["nodes"]} == {"project", "note", "journal", "source"}
    # Shared root belongs to a private project too, but visitors only see one project.
    assert not any(n["bridge"] for n in graph["nodes"])
    assert "notes" not in client.get("/healthz").json()


def test_journal_and_explore_list_public_notes_only(site_for: SiteFor) -> None:
    client = site_for(VAULT).client
    journal = client.get("/journal").text
    assert "Open chat" in journal
    explore = client.get("/explore").text
    assert "Seed idea" in explore
    assert 'value="ghost"' not in explore


def test_signed_in_only_pages_stay_closed(site_for: SiteFor) -> None:
    client = site_for(VAULT).client
    for path in ("/health", "/appearance"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/login")
    for path in ("/appearance", "/appearance/background", "/appearance/background/remove", "/"):
        assert client.post(path, follow_redirects=False).status_code == 401


def test_visitor_navigation_offers_sign_in(site_for: SiteFor) -> None:
    client = site_for(VAULT).client
    page = client.get("/projects").text
    assert 'href="/login?next=/projects"' in page
    assert 'href="/health"' not in page
    assert 'href="/appearance"' not in page
    assert "Sign out" not in page
    landing = client.get("/").text
    assert 'href="/explore"' in landing
    assert 'href="/appearance"' not in landing
    missing = client.get("/notes/whatever").text
    assert "If this notebook is yours, sign in to see every note." in missing


def test_nothing_public_shows_soil_and_sign_in(site_for: SiteFor) -> None:
    files = {k: v.replace("public: true\n", "") for k, v in VAULT.items()}
    client = site_for(files).client
    landing = client.get("/").text
    assert "Nothing here is public yet." in landing
    assert '<a class="btn btn-main" href="/login">Sign in</a>' in landing
    assert 'href="/explore"' not in landing
    data = client.get("/api/landing").json()
    assert data["projects"] == data["notes"] == data["sources"] == data["journal"] == []
    assert client.get("/api/graph").json()["nodes"] == []


def test_spanish_visitor_pages(site_for: SiteFor) -> None:
    files = {k: v.replace("public: true\n", "") for k, v in VAULT.items()}
    client = site_for(files, language="es").client
    landing = client.get("/").text
    assert "Todavía no hay nada público acá." in landing
    assert ">Iniciar sesión</a>" in landing
    missing = client.get("/notes/whatever").text
    assert "Si este cuaderno es tuyo, iniciá sesión para ver todas las notas." in missing
    for english in ("Sign in", "Nothing here", "If this notebook"):
        assert english not in landing + missing


def test_sample_vault_leaks_no_private_title(site_for: SiteFor, example_index: VaultIndex) -> None:
    pages = crawl(site_for().client)
    assert any(path.startswith("/notes/") for path in pages)
    private = [n for n in example_index.notes.values() if not n.public]
    assert private
    # A public note may name a private one in its own words; that text is the author's.
    public_text = " ".join(n.body for n in example_index.notes.values() if n.public).lower()
    for note in private:
        for body in pages.values():
            assert f"/notes/{note.slug}" not in body
            assert f"/projects/{note.slug}" not in body
            assert note.path not in body
            if note.title.lower() not in public_text:
                assert note.title not in body, note.title


# -- the view itself ------------------------------------------------------------------


def test_public_view_follows_the_vault(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "a.md").write_text("---\npublic: true\n---\n# A\n\n[[b]]\n", "utf-8")
    (root / "notes" / "b.md").write_text("# B\n", "utf-8")
    index = VaultIndex(config_for(root))
    index.refresh(force=True)
    view = PublicView(index)
    assert set(view.notes) == {"a"}
    assert view.outlinks["a"] == set()
    assert view.resolve("b") is None
    (root / "notes" / "b.md").write_text("---\npublic: true\n---\n# B\n", "utf-8")
    assert view.refresh(force=True)
    assert view.outlinks["a"] == {"b"}
    assert view.resolve("b") == "b"
    assert not view.refresh(force=True) or view.generation == index.generation


def test_a_private_note_that_wins_a_name_is_not_swapped(make_vault: VaultFactory) -> None:
    index = make_vault(
        {
            "notes/topic.md": "# Private topic\n",
            "notes/deep/topic.md": "---\npublic: true\n---\n# Public topic\n",
            "notes/reader.md": "---\npublic: true\n---\n# Reader\n\nSee [[topic]].\n",
        }
    )
    view = PublicView(index)
    assert index.resolve("topic") == "topic"
    assert view.resolve("topic") is None
    html = Renderer(view, ghosts=False).html(view.notes["reader"])
    assert "See topic." in html
    assert "<a" not in html


def test_mode_none_shows_everything(tmp_path: Path) -> None:
    config = Config.model_validate(
        {
            "vault": VaultConfig(root=EXAMPLE_VAULT),
            "data": {"dir": tmp_path},
            "auth": {"mode": "none"},
        }
    )
    with TestClient(create_app(config, environ={})) as client:
        nodes = client.get("/api/graph").json()["nodes"]
        assert any(not n["public"] for n in nodes)
        assert "notes" in client.get("/healthz").json()
