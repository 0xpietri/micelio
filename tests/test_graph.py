from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from micelio.app import create_app
from micelio.config import Config, VaultConfig
from micelio.graph import (
    GraphBuilder,
    Scope,
    ScopeError,
    UnknownNodeError,
    ghost_id,
    parse_scope,
)
from micelio.i18n import available_languages, browser_strings, load_strings
from micelio.vault import VaultIndex

from .conftest import EXAMPLE_VAULT, VaultFactory
from .test_auth_web import ENV as AUTH_ENV

STATIC = Path(__file__).resolve().parents[1] / "src" / "micelio" / "static"
BAYES = "learning-bayesian-statistics"
PLANETS = "do-planets-at-birth-leave-a-trace"
FREE_WILL = "free-will-in-a-determined-world"
PRIORS = "priors-are-beliefs-you-can-update"


def client_for(language: str = "en", root: Path = EXAMPLE_VAULT) -> TestClient:
    config = Config.model_validate(
        {
            "site": {"language": language},
            "vault": VaultConfig(root=root),
            "auth": {"mode": "none"},
        }
    )
    return TestClient(create_app(config, environ={}))


@pytest.fixture(scope="module")
def client() -> TestClient:
    return client_for()


@pytest.fixture(scope="module")
def builder(example_index: VaultIndex) -> GraphBuilder:
    return GraphBuilder(example_index.config, example_index)


def by_id(nodes: Sequence[Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    return {str(n["id"]): n for n in nodes}


# -- scope parsing -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "scope"),
    [
        ("all", Scope("all")),
        (" all ", Scope("all")),
        ("project:x", Scope("project", "x")),
        ("note:a-b", Scope("note", "a-b")),
        ("note:a:b", Scope("note", "a:b")),
    ],
)
def test_parse_scope(raw: str, scope: Scope) -> None:
    assert parse_scope(raw) == scope


@pytest.mark.parametrize("raw", ["", "everything", "project:", "tag:x", ":x", "note"])
def test_parse_scope_rejects(raw: str) -> None:
    with pytest.raises(ScopeError):
        parse_scope(raw)


def test_scope_round_trips() -> None:
    assert str(Scope("all")) == "all"
    assert str(Scope("project", "x")) == "project:x"


# -- the builder -----------------------------------------------------------------------


def test_all_has_every_note_and_the_ghost(builder: GraphBuilder, example_index: VaultIndex) -> None:
    data = builder.build(Scope("all"))
    nodes = by_id(data["nodes"])
    assert set(example_index.notes) <= set(nodes)
    ghost = nodes[ghost_id("Tidal forces explained")]
    assert ghost["ghost"] is True
    assert ghost["type"] == "ghost"
    assert ghost["href"] is None
    assert len(nodes) == len(example_index.notes) + 1
    pairs = {frozenset((e.source, e.target)) for e in example_index.edges}
    assert len(data["edges"]) == len(pairs) + 1
    assert data["hidden_types"] == ["journal", "source"]
    assert data["scope"] == "all"


def test_node_fields(builder: GraphBuilder, example_index: VaultIndex) -> None:
    nodes = by_id(builder.build(Scope("all"))["nodes"])
    project = nodes[BAYES]
    assert project["type"] == "project"
    assert project["category"] == "study"
    assert project["status"] == "active"
    assert project["public"] is True
    assert project["href"] == f"/projects/{BAYES}"
    links = example_index.outlinks[BAYES] | example_index.backlinks[BAYES]
    assert project["degree"] == len(example_index.outlinks[BAYES]) + len(
        example_index.backlinks[BAYES]
    )
    assert len(links) > 5
    bridge = nodes[PRIORS]
    assert bridge["bridge"] is True
    assert bridge["category"] is None
    assert bridge["categories"] == ["philosophy", "study"]
    assert bridge["href"] == f"/notes/{PRIORS}"
    plain = nodes["bayes-theorem-in-one-line"]
    assert plain["category"] == "study"
    assert plain["bridge"] is False
    orphan = nodes["a-stray-thought-with-no-home"]
    assert orphan["categories"] == []
    assert orphan["degree"] == 0
    assert {n["type"] for n in nodes.values()} == {
        *("project", "note", "question", "gap", "journal", "source", "ghost")
    }


def test_edges_reference_existing_nodes(builder: GraphBuilder) -> None:
    for scope in (Scope("all"), Scope("project", BAYES), Scope("note", PRIORS)):
        data = builder.build(scope)
        ids = {n["id"] for n in data["nodes"]}
        edge_ids = [e["id"] for e in data["edges"]]
        assert len(edge_ids) == len(set(edge_ids))
        for edge in data["edges"]:
            assert edge["source"] in ids
            assert edge["target"] in ids


def test_categories_carry_names_and_colors(builder: GraphBuilder) -> None:
    categories = builder.build(Scope("all"))["categories"]
    assert categories[0] == {
        "key": "science",
        "name": "Science",
        "color": "#ff2fa0",
        "species": "fly-agaric",
    }
    assert [c["key"] for c in categories] == ["science", "philosophy", "study", "free"]


def test_project_scope(builder: GraphBuilder, example_index: VaultIndex) -> None:
    data = builder.build(Scope("project", BAYES))
    nodes = by_id(data["nodes"])
    members = example_index.members[BAYES]
    core = {BAYES, *members}
    assert {k for k, n in nodes.items() if not n["faded"]} == core
    # The bridges lead out to the other projects their notes belong to, faded.
    assert {k for k, n in nodes.items() if n["faded"]} == {PLANETS, FREE_WILL}
    assert nodes[BAYES]["focus"] is True
    assert sum(1 for n in nodes.values() if n["focus"]) == 1
    for edge in data["edges"]:
        touches_faded = nodes[edge["source"]]["faded"] or nodes[edge["target"]]["faded"]
        assert edge["faded"] == touches_faded
        assert not (nodes[edge["source"]]["faded"] and nodes[edge["target"]]["faded"])
    assert data["hidden_types"] == []


def test_project_scope_shows_ghosts_of_its_notes(builder: GraphBuilder) -> None:
    nodes = by_id(builder.build(Scope("project", PLANETS))["nodes"])
    assert ghost_id("Tidal forces explained") in nodes


def test_project_without_notes(builder: GraphBuilder) -> None:
    data = builder.build(Scope("project", "an-abandoned-idea"))
    assert [n["id"] for n in data["nodes"]] == ["an-abandoned-idea"]
    assert data["edges"] == []


def test_note_scope_is_one_hop(builder: GraphBuilder, example_index: VaultIndex) -> None:
    data = builder.build(Scope("note", PRIORS))
    ids = {n["id"] for n in data["nodes"]}
    expected = {PRIORS, *example_index.outlinks[PRIORS], *example_index.backlinks[PRIORS]}
    assert ids == expected
    assert not any(n["faded"] for n in data["nodes"])
    assert [n["id"] for n in data["nodes"] if n["focus"]] == [PRIORS]


def test_note_scope_ghost_only_from_the_note(builder: GraphBuilder) -> None:
    gid = ghost_id("Tidal forces explained")
    with_ghost = by_id(
        builder.build(Scope("note", "can-planetary-gravity-affect-a-newborn"))["nodes"]
    )
    assert gid in with_ghost
    # The project links the note that has the ghost, but the ghost is two hops away.
    nodes = by_id(
        builder.build(Scope("note", "a-planet-s-tidal-pull-is-smaller-than-a-nearby-wall-s"))[
            "nodes"
        ]
    )
    assert gid not in nodes


def test_unknown_or_mismatched_slugs(builder: GraphBuilder) -> None:
    for scope in (
        Scope("project", "nope"),
        Scope("note", "nope"),
        Scope("project", PRIORS),
        Scope("note", BAYES),
    ):
        with pytest.raises(UnknownNodeError):
            builder.build(scope)


def test_hidden_types_follow_the_config(make_vault: VaultFactory) -> None:
    index = make_vault({"notes/A.md": "x"})
    config = Config.model_validate(
        {"vault": VaultConfig(root=index.root), "graph": {"hide_by_default": ["note"]}}
    )
    assert GraphBuilder(config, index).build(Scope("all"))["hidden_types"] == ["note"]
    config = Config.model_validate(
        {"vault": VaultConfig(root=index.root), "graph": {"hide_by_default": []}}
    )
    assert GraphBuilder(config, index).build(Scope("all"))["hidden_types"] == []


def test_two_notes_linking_each_other_get_one_thread(make_vault: VaultFactory) -> None:
    # A concept note links back to its project; the pair is drawn once, from the project.
    index = make_vault(
        {
            "projects/P.md": "---\ntype: project\n---\n[[A]] [[B]]",
            "notes/A.md": "back to [[P]] and to [[B]]",
            "notes/B.md": "and [[A]]",
        }
    )
    builder = GraphBuilder(index.config, index)
    for scope in (Scope("all"), Scope("project", "p"), Scope("note", "a")):
        edges = builder.build(scope)["edges"]
        pairs = [frozenset((e["source"], e["target"])) for e in edges]
        assert len(pairs) == len(set(pairs)), scope
    edges = builder.build(Scope("all"))["edges"]
    assert {(e["source"], e["target"]) for e in edges if "p" in (e["source"], e["target"])} == {
        ("p", "a"),
        ("p", "b"),
    }
    assert len(edges) == 3


def test_graph_threads_are_soft_bows() -> None:
    # Graph threads are one gentle curve each; only the landing keeps wild hyphae.
    graph = (STATIC / "js" / "graph.js").read_text(encoding="utf-8")
    assert "threadPath(" in graph
    assert "hyphaPath" not in graph
    draw = (STATIC / "js" / "draw.js").read_text(encoding="utf-8")
    assert "export function threadPath" in draw


def test_empty_vault(make_vault: VaultFactory) -> None:
    index = make_vault({})
    data = GraphBuilder(index.config, index).build(Scope("all"))
    assert data["nodes"] == []
    assert data["edges"] == []


# -- the API -----------------------------------------------------------------------------


def test_api_graph_default_scope(client: TestClient) -> None:
    response = client.get("/api/graph")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["scope"] == "all"


def test_api_graph_scopes(client: TestClient) -> None:
    project = client.get(f"/api/graph?scope=project:{BAYES}").json()
    assert project["scope"] == f"project:{BAYES}"
    note = client.get(f"/api/graph?scope=note:{PRIORS}").json()
    assert {n["id"] for n in note["nodes"]} >= {PRIORS, BAYES, FREE_WILL}


@pytest.mark.parametrize("scope", ["everything", "project:", "tag:x"])
def test_api_graph_bad_scope(client: TestClient, scope: str) -> None:
    response = client.get("/api/graph", params={"scope": scope})
    assert response.status_code == 400
    assert "scope" in response.json()["error"]


def test_api_graph_unknown_slug(client: TestClient) -> None:
    assert client.get("/api/graph?scope=note:nope").status_code == 404
    assert client.get(f"/api/graph?scope=project:{PRIORS}").status_code == 404


def test_api_graph_overlong_scope(client: TestClient) -> None:
    assert client.get("/api/graph", params={"scope": "note:" + "x" * 400}).status_code == 422


def test_api_graph_sees_new_notes(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "A.md").write_text("first", encoding="utf-8")
    client = client_for(root=root)
    assert [n["id"] for n in client.get("/api/graph").json()["nodes"]] == ["a"]
    (root / "notes" / "B.md").write_text("links [[A]]", encoding="utf-8")
    app_index: VaultIndex = client.app.state.vault  # type: ignore[attr-defined]
    app_index.refresh(force=True)
    data = client.get("/api/graph").json()
    assert {n["id"] for n in data["nodes"]} == {"a", "b"}
    assert [(e["source"], e["target"]) for e in data["edges"]] == [("b", "a")]


def test_api_graph_shows_visitors_public_notes_only(tmp_path: Path) -> None:
    config = Config.model_validate(
        {"vault": VaultConfig(root=EXAMPLE_VAULT), "data": {"dir": tmp_path}}
    )
    with TestClient(create_app(config, environ=AUTH_ENV)) as anonymous:
        response = anonymous.get("/api/graph", follow_redirects=False)
        assert response.status_code == 200
        nodes = response.json()["nodes"]
        assert nodes
        assert all(n["public"] and not n["ghost"] for n in nodes)
        explore = anonymous.get("/explore", follow_redirects=False)
        assert explore.status_code == 200
        # Browser strings are not private: the sign-in page may need them later.
        assert anonymous.get("/static/locales/en.json").status_code == 200


# -- browser strings ---------------------------------------------------------------------


def test_browser_strings_cover_the_graph_tables() -> None:
    strings = browser_strings("en")
    assert strings["graph.hint"].startswith("Click a mushroom")
    assert strings["type.ghost"] == "Missing note"
    assert strings["status.active"] == "Active"
    assert strings["category.science"] == "Science"
    assert not any(k.startswith(("login.", "health.")) for k in strings)


def test_browser_strings_per_language() -> None:
    for language in available_languages():
        strings = browser_strings(language)
        assert set(strings) == set(browser_strings("en"))
        own = load_strings(language)
        assert all(strings[k] == own[k] for k in strings if k in own)


def test_locale_json_route(client: TestClient) -> None:
    response = client.get("/static/locales/es.json")
    assert response.status_code == 200
    data = response.json()
    assert data["graph.matches"] == "{count} coincidencias"
    assert data == browser_strings("es")
    for bad in ("xx.json", "es", "es.toml", "en.json.json", "../en.json"):
        assert client.get(f"/static/locales/{bad}").status_code == 404, bad


def test_other_static_files_still_served(client: TestClient) -> None:
    assert client.get("/static/css/micelio.css").status_code == 200
    script = client.get("/static/js/graph.js")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]


# -- pages -------------------------------------------------------------------------------


def test_explore_page(client: TestClient, example_index: VaultIndex) -> None:
    html = client.get("/explore").text
    assert '<a href="/explore" aria-current="page">Explore</a>' in html
    assert 'data-graph="/api/graph?scope=all"' in html
    assert '<script type="module" src="/static/js/explore.js"></script>' in html
    assert '<script src="/static/vendor/d3-force/d3-force.bundle.min.js"></script>' in html
    assert 'href="/static/css/graph.css"' in html
    assert 'data-max="400"' in html
    # The page shows the underground of the painted background (§7c).
    assert 'class="full underground"' in html
    # Hidden by default: journal and source start unchecked.
    assert re.search(r'name="type" value="journal">', html)
    assert re.search(r'name="type" value="source">', html)
    assert re.search(r'name="type" value="note" checked>', html)
    assert 'name="type" value="ghost" checked' in html
    for key in ("science", "philosophy", "study", "free", "none"):
        assert f'name="category" value="{key}" checked' in html
    # The latest conversations, newest first.
    assert html.index("2026-11-09, voice call: planets") < html.index("2026-11-04")
    # Every note is also a text link.
    for note in example_index.notes.values():
        assert f'href="/{"projects" if note.type == "project" else "notes"}/{note.slug}"' in html
    assert f"All notes as a list ({len(example_index.notes)})" in html


def test_explore_without_ghosts_has_no_ghost_filter(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "A.md").write_text("alone", encoding="utf-8")
    html = client_for(root=root).get("/explore").text
    assert 'value="ghost"' not in html
    assert "No conversations yet." in html


def test_project_and_note_pages_embed_their_graphs(client: TestClient) -> None:
    project = client.get(f"/projects/{BAYES}").text
    assert f'data-graph="/api/graph?scope=project%3A{BAYES}"' in project
    assert 'data-mode="forest"' in project
    assert "Map of the project" in project
    assert '<script type="module" src="/static/js/graph-embed.js"></script>' in project
    note = client.get(f"/notes/{PRIORS}").text
    assert f'data-graph="/api/graph?scope=note%3A{PRIORS}"' in note
    assert "Neighborhood" in note
    assert 'data-mode="box"' in note
    # The graph's own address works.
    assert client.get(f"/api/graph?scope=project%3A{BAYES}").status_code == 200


def test_pages_without_graphs_load_no_graph_code(client: TestClient) -> None:
    for path in ("/projects", "/journal", "/health"):
        html = client.get(path).text
        assert "graph.js" not in html
        assert "d3-force" not in html
        assert "cytoscape" not in html


def _visible_text(html: str) -> str:
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.DOTALL)
    return re.sub(r"<[^>]+>", " ", html)


def test_spanish_graph_pages_have_no_english_interface() -> None:
    client = client_for("es")
    english = set(load_strings("en").values()) - set(load_strings("es").values())
    english = {s for s in english if "{" not in s and len(s) > 3}
    pages = ("/explore", f"/projects/{BAYES}", f"/notes/{PRIORS}")
    for path in pages:
        html = client.get(path).text
        text = _visible_text(html)
        attributes = " ".join(re.findall(r'(?:aria-label|placeholder|title)="([^"]*)"', html))
        for phrase in english:
            assert f">{phrase}<" not in html, (path, phrase)
            assert phrase not in attributes, (path, phrase)
        assert "Explorar" in text
    explore = client.get("/explore").text
    assert "Todas las notas en una lista" in explore
    assert "Sin categoría" in explore
    assert "Cargando el grafo…" in explore


def test_graphs_need_no_cytoscape() -> None:
    # The graphs are drawn as mycelium by the landing's d3-force (§7c).
    assert not (STATIC / "vendor" / "cytoscape").exists()
    for script in (STATIC / "js").glob("*.js"):
        assert "cytoscape" not in script.read_text(encoding="utf-8").lower(), script.name


def test_browser_code_uses_only_local_modules() -> None:
    for path in (STATIC / "js").glob("*.js"):
        # The SVG namespace is a name, not a request.
        source = path.read_text(encoding="utf-8").replace("http://www.w3.org/2000/svg", "")
        for target in re.findall(r'from\s+"([^"]+)"', source):
            assert target.startswith("./") or target.startswith("../vendor/"), (path, target)
        assert "http://" not in source
        assert "https://" not in source
        assert "innerHTML" not in source, f"{path.name}: build DOM with textContent"


def test_graph_json_is_plain(client: TestClient) -> None:
    """Renderer-agnostic: only JSON types, no HTML in titles."""
    data = client.get("/api/graph").json()
    json.dumps(data)
    keys = {
        "id", "title", "type", "category", "categories", "bridge", "status",
        "degree", "public", "href", "ghost", "faded", "focus", "look",
    }  # fmt: skip
    assert all(set(n) == keys for n in data["nodes"])
    assert all(set(e) == {"id", "source", "target", "faded"} for e in data["edges"])
