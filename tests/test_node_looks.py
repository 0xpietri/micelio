"""The owner dresses a project's mushroom or a source's mineral (§7c): saved in the data
folder through ``POST /api/looks/<slug>``, shown by every graph and the landing."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from micelio.appearance import AppearanceStore
from micelio.looks import NodeLooks, clean_look

from .conftest import EXAMPLE_VAULT
from .test_landing import client as client  # the fixture
from .test_landing import form_token, make_config
from .test_public import VAULT, SiteFor
from .test_public import site_for as site_for  # the fixture

STATIC = Path(__file__).resolve().parents[1] / "src" / "micelio" / "static"
PROJECT = "cities-as-living-organisms"
SOURCE = "mcelreath-statistical-rethinking"
NOTE = "streets-behave-like-veins"


def key(client: TestClient, path: str = f"/projects/{PROJECT}") -> str:
    match = re.search(r'<meta name="micelio-looks" content="([^"]+)"', client.get(path).text)
    assert match, "the owner's page carries the looks key"
    return match.group(1)


def dress(client: TestClient, slug: str, look: object, token: str | None = None) -> object:
    token = key(client) if token is None else token
    return client.post(f"/api/looks/{slug}", json=look, headers={"X-Micelio-Form": token})


def graph_node(client: TestClient, slug: str, scope: str = "all") -> dict[str, object]:
    nodes = client.get(f"/api/graph?scope={scope}").json()["nodes"]
    return next(n for n in nodes if n["id"] == slug)


def test_clean_look_keeps_only_what_the_kind_has() -> None:
    raw = {"color": "#AABBCC", "size": 9, "species": "morel", "mineral": "amber", "x": 1}
    assert clean_look(raw, "project") == {"color": "#aabbcc", "size": 1.6, "species": "morel"}
    assert clean_look(raw, "source") == {"color": "#aabbcc", "mineral": "amber"}
    bad = {"color": "red; x", "size": True, "species": "toadstool", "mineral": "ruby"}
    assert clean_look(bad, "project") == {}
    assert clean_look(bad, "source") == {}
    assert clean_look([1, 2], "project") == {}
    assert clean_look({"size": 0.1}, "project") == {"size": 0.6}


def test_node_looks_save_and_reset(tmp_path: Path) -> None:
    looks = NodeLooks(AppearanceStore(make_config(tmp_path)))
    assert looks.all() == {}
    looks.save("a", {"species": "coral", "size": 1.2})
    looks.save("b", {"mineral": "emerald"})
    assert looks.get("a") == {"species": "coral", "size": 1.2}
    assert looks.get("b") == {"mineral": "emerald"}
    looks.save("a", {})
    assert looks.get("a") is None
    assert set(looks.all()) == {"b"}


def test_owner_dresses_a_project(client: TestClient) -> None:
    assert graph_node(client, PROJECT)["look"] is None
    answer = dress(client, PROJECT, {"species": "coral", "color": "#ff00aa", "size": 1.3})
    assert answer.status_code == 200
    assert answer.json() == {
        "ok": True,
        "look": {"color": "#ff00aa", "species": "coral", "size": 1.3},
    }
    assert graph_node(client, PROJECT)["look"] == {
        "color": "#ff00aa",
        "species": "coral",
        "size": 1.3,
    }
    assert graph_node(client, PROJECT, f"project:{PROJECT}")["look"]["species"] == "coral"
    landing = client.get("/api/landing").json()
    project = next(p for p in landing["projects"] if p["id"] == PROJECT)
    assert project["species"] == "coral"
    assert project["color"] == "#ff00aa"
    assert project["scale"] == 1.3
    assert project["shade"] is False
    # The project list draws the same mushroom.
    assert 'data-species="coral"' in client.get("/projects").text
    # Back to the default.
    assert dress(client, PROJECT, {}).json()["look"] == {}
    assert graph_node(client, PROJECT)["look"] is None


def test_owner_dresses_a_source(client: TestClient) -> None:
    look = {"mineral": "amethyst", "color": "#123456", "species": "morel"}
    answer = dress(client, SOURCE, look, key(client, f"/notes/{SOURCE}"))
    assert answer.json()["look"] == {"color": "#123456", "mineral": "amethyst"}
    assert graph_node(client, SOURCE, f"note:{SOURCE}")["look"]["mineral"] == "amethyst"


def test_only_projects_and_sources_are_dressed(client: TestClient) -> None:
    assert dress(client, NOTE, {"color": "#ffffff"}).status_code == 404
    assert dress(client, "no-such-note", {"color": "#ffffff"}).status_code == 404


def test_a_dress_without_the_key_is_refused(client: TestClient) -> None:
    answer = dress(client, PROJECT, {"species": "coral"}, token="forged")
    assert answer.status_code == 403
    assert answer.json() == {"ok": False, "error": "form"}
    answer = client.post(f"/api/looks/{PROJECT}", json={"species": "coral"})
    assert answer.status_code == 403
    assert graph_node(client, PROJECT)["look"] is None


def test_looks_never_touch_the_vault(client: TestClient) -> None:
    before = {p: p.stat().st_mtime_ns for p in EXAMPLE_VAULT.rglob("*") if p.is_file()}
    dress(client, PROJECT, {"species": "parasol"})
    after = {p: p.stat().st_mtime_ns for p in EXAMPLE_VAULT.rglob("*") if p.is_file()}
    assert before == after


def test_visitors_cannot_dress_and_get_no_key(site_for: SiteFor) -> None:
    site = site_for(VAULT)
    page = site.client.get("/projects/open-garden").text
    assert 'name="micelio-looks"' not in page
    assert "Click it to choose its look" not in page
    answer = site.client.post(
        "/api/looks/open-garden", json={"species": "coral"}, headers={"X-Micelio-Form": "x"}
    )
    assert answer.status_code in (401, 404)
    # A private project gives nothing away either.
    answer = site.client.post("/api/looks/vault-xq-plan", json={}, headers={"X-Micelio-Form": "x"})
    assert answer.status_code in (401, 404)
    assert "xq" not in answer.text.lower()


def test_signed_in_owner_gets_the_key_and_hint(site_for: SiteFor) -> None:
    site = site_for(VAULT)
    site.sign_in()
    page = site.client.get("/projects/open-garden").text
    assert 'name="micelio-looks"' in page
    assert "Click it to choose its look" in page
    token = key(site.client, "/projects/open-garden")
    answer = site.client.post(
        "/api/looks/open-garden", json={"species": "coral"}, headers={"X-Micelio-Form": token}
    )
    assert answer.status_code == 200


def test_graph_opens_the_editor_on_the_focus_node() -> None:
    script = (STATIC / "js" / "graph.js").read_text("utf-8")
    assert 'from "./node-look.js"' in script
    assert "openLookPanel(" in script
    editor = (STATIC / "js" / "node-look.js").read_text("utf-8")
    assert "/api/looks/" in editor
    assert "X-Micelio-Form" in editor


def test_browser_strings_name_species_and_minerals(client: TestClient) -> None:
    strings = client.get("/static/locales/es.json").json()
    assert strings["species.morel"]
    assert strings["mineral.amethyst"]
    assert strings["graph.dress_project"]


def test_theme_address_changes_with_the_palette(client: TestClient) -> None:
    def link() -> str:
        match = re.search(r'href="(/theme\.css\?v=[0-9a-f]{10})"', client.get("/projects").text)
        assert match
        return match.group(1)

    before = link()
    response = client.get(before)
    assert response.headers["cache-control"] == "private, no-cache"
    assert response.headers["cdn-cache-control"] == "no-store"
    data = {"csrf": form_token(client), "palette": "rose-pine", "soil": "52"}
    client.post("/appearance", data=data, follow_redirects=False)
    after = link()
    assert after != before
    assert "#ebbcba" in client.get(after).text  # rosé pine's sun: the logo and titles
