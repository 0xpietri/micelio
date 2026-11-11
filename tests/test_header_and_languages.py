"""The header (§7c): two lines, the ⚙ menu, the language flag (§5a), signing out or in
as icons; and a visitor's own look, kept in their browser (§7b)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .test_graph import client_for
from .test_public import SiteFor
from .test_public import site_for as site_for  # the fixture


def fresh() -> TestClient:
    """Sign-in off, English, no cookies from other tests."""
    return client_for("en")


def test_header_has_two_lines_and_the_corner_tools() -> None:
    client = fresh()
    html = client.get("/projects").text
    row = html.index('class="top-row"')
    nav = html.index('<nav aria-label="Main">')
    assert row < html.index('class="brand"') < html.index('class="corner-tools"') < nav
    assert 'class="icon-button menu-toggle"' in html
    assert 'href="/appearance"' in html  # the owner's Appearance page, inside the ⚙ menu
    assert 'class="lang-menu"' in html
    assert 'href="/language/es?next=/projects"' in html
    assert "/static/js/menu.js" in html
    assert "look-early.js" not in html  # the owner sees the site's own look


def test_language_flag_switches_and_remembers() -> None:
    client = fresh()
    response = client.get("/language/es?next=/projects", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/projects"
    assert "micelio_lang=es" in response.headers["set-cookie"]
    html = client.get("/projects").text
    assert '<html lang="es"' in html
    assert ">Proyectos<" in html
    assert client.get("/api/graph").json()["categories"][0]["name"] == "Ciencia"
    client.get("/language/en")
    assert '<html lang="en"' in client.get("/projects").text


def test_language_route_refuses_unknown_and_offsite() -> None:
    client = fresh()
    assert client.get("/language/xx", follow_redirects=False).status_code == 404
    for bad in ("https://evil.example/", "//evil.example/", "/\\\\evil.example"):
        response = client.get(f"/language/es?next={bad}", follow_redirects=False)
        assert response.headers["location"] == "/", bad
    client.cookies.clear()
    client.cookies.set("micelio_lang", "xx")
    assert '<html lang="en"' in client.get("/projects").text


def test_visitors_get_the_flag_their_look_and_a_sign_in_icon(site_for: SiteFor) -> None:
    visitor = site_for().client
    html = visitor.get("/explore").text
    assert "data-visitor" in html
    assert "/static/js/look-early.js" in html
    assert 'class="look-panel"' in html
    assert 'href="/appearance"' not in html
    assert 'class="icon-button sign-in"' in html
    assert 'class="lang-menu"' in html
    assert visitor.get("/language/es?next=/explore", follow_redirects=False).status_code == 303
    assert '<html lang="es"' in visitor.get("/explore").text
    landing = visitor.get("/").text
    assert 'class="corner-tools"' in landing
    assert 'class="look-panel"' in landing


def test_a_visitor_palette_only_recolors_their_own_requests(site_for: SiteFor) -> None:
    visitor = site_for().client
    theme = visitor.get("/theme.css?palette=tokyo-night").text
    assert "--pal-sun: #7aa2f7;" in theme
    assert "--pal-sun: #7aa2f7;" not in visitor.get("/theme.css").text  # the site is unchanged
    graph = visitor.get("/api/graph?palette=tokyo-night").json()
    assert graph["categories"][0]["color"] == "#bb9af7"
    landing = visitor.get("/api/landing?palette=tokyo-night").json()
    assert landing["palette"]["key"] == "tokyo-night"
    # An unknown name is the site's own look.
    assert visitor.get("/theme.css?palette=neon").text == visitor.get("/theme.css").text
    assert visitor.get("/api/landing?palette=neon").json()["palette"]["key"] == "psychedelic"
