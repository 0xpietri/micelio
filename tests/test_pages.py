from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from micelio.app import create_app
from micelio.config import Config, VaultConfig

from .conftest import EXAMPLE_VAULT


def client_for(language: str = "en", root: Path = EXAMPLE_VAULT) -> TestClient:
    config = Config.model_validate(
        {
            "site": {"language": language, "timezone": "America/Argentina/Buenos_Aires"},
            "vault": VaultConfig(root=root),
            "auth": {"mode": "none"},
        }
    )
    return TestClient(create_app(config, environ={}))


@pytest.fixture(scope="module")
def client() -> TestClient:
    return client_for()


def titles(html: str) -> list[str]:
    return re.findall(r'class="row-title" href="[^"]+">([^<]+)</a>', html)


def test_projects_grouped_by_category_in_config_order(client: TestClient) -> None:
    html = client.get("/projects").text
    keys = ("science", "philosophy", "study", "free")
    order = [html.index(f'class="group cat-{key}"') for key in keys]
    assert order == sorted(order)
    cards = re.findall(r'<strong class="row-title">([^<]+)</strong>', html)
    assert cards[-2:] == ["Cities as living organisms", "An abandoned idea"]
    # Each project is a card with its mushroom: species from the category, growth the status.
    assert 'data-species="chanterelle" data-status="closed"' in html
    assert "Last conversation Nov 9, 2026" in html
    assert 'class="group cat-science"' in html


def test_project_page(client: TestClient) -> None:
    html = client.get("/projects/learning-bayesian-statistics").text
    assert "<h1>Learning Bayesian statistics</h1>" in html
    assert "<h2>What I want to understand</h2>" in html
    assert "Bayes theorem in one line" in titles(html)
    assert "McElreath - Statistical Rethinking" in titles(html)
    assert html.count('class="badge bridge"') == 2
    assert "Created 10/1/2026" in html  # in the growth card, in numbers


def test_project_page_lists_its_conversations(client: TestClient) -> None:
    html = client.get("/projects/do-planets-at-birth-leave-a-trace").text
    assert "Conversations" in html
    assert "2026-11-09, voice call: planets" in html


def test_note_page(client: TestClient) -> None:
    html = client.get("/notes/priors-are-beliefs-you-can-update").text
    assert "Bridge between categories" in html
    assert "Free will in a determined world" in html
    assert "Learning Bayesian statistics" in html
    assert 'class="mushroom-icon cat-study"' in html


def test_note_page_shows_ghost_and_backlinks(client: TestClient) -> None:
    html = client.get("/notes/can-planetary-gravity-affect-a-newborn").text
    assert 'class="ghost"' in html
    assert "Linked from" in html
    assert "2026-11-09, voice call: planets" in html


def test_journal_newest_first(client: TestClient) -> None:
    html = client.get("/journal").text
    assert html.index("2026-11-09") < html.index("2026-11-04")
    assert 'datetime="2026-11-09"' in html


def test_health(client: TestClient) -> None:
    html = client.get("/health").text
    assert "Link to a missing note" in html
    assert "A stray thought with no home" in html
    assert "27 notes and 54 links." in html


def test_health_all_good(tmp_path: Path) -> None:
    (tmp_path / "A.md").write_text("[[B]]", encoding="utf-8")
    (tmp_path / "B.md").write_text("", encoding="utf-8")
    assert "Nothing to fix" in client_for(root=tmp_path).get("/health").text


def test_redirects_between_project_and_note_urls(client: TestClient) -> None:
    to_project = client.get("/notes/learning-bayesian-statistics", follow_redirects=False)
    assert to_project.status_code == 308
    assert to_project.headers["location"] == "/projects/learning-bayesian-statistics"
    to_note = client.get("/projects/bayes-theorem-in-one-line", follow_redirects=False)
    assert to_note.headers["location"] == "/notes/bayes-theorem-in-one-line"


def test_not_found(client: TestClient) -> None:
    for path in ("/notes/nope", "/projects/nope", "/nowhere"):
        response = client.get(path)
        assert response.status_code == 404
        assert "There is no note here" in response.text


def test_other_errors_keep_their_status(client: TestClient) -> None:
    assert client.post("/projects").status_code == 405


def test_theme_css(client: TestClient) -> None:
    response = client.get("/theme.css")
    assert response.headers["content-type"].startswith("text/css")
    assert ".cat-science { --cat: #ff2fa0; }" in response.text
    assert "--pal-sun: #ffd23f;" in response.text


def test_no_inline_scripts_or_styles(client: TestClient) -> None:
    paths = (
        "/",
        "/projects",
        "/projects/learning-bayesian-statistics",
        "/notes/priors-are-beliefs-you-can-update",
        "/explore",
        "/journal",
        "/health",
        "/appearance",
    )
    for path in paths:
        html = client.get(path).text
        scripts = re.findall(r"<script([^>]*)>(.*?)</script>", html, re.DOTALL)
        assert html.count("<script") == len(scripts)
        for attributes, body in scripts:
            assert re.search(r'src="/static/[^"]+\.js"', attributes), attributes
            assert body.strip() == ""
        assert "<style" not in html
        assert "style=" not in html


def test_spanish_interface(tmp_path: Path) -> None:
    client = client_for("es")
    html = client.get("/projects").text
    assert '<html lang="es">' in html
    assert "Proyectos" in html
    assert "Última conversación: 9 nov 2026" in html
    assert "Borrador" in html
    headings = [
        h.split("</span>")[-1].strip() for h in re.findall(r"<h2>(.*?)</h2>", html, re.DOTALL)
    ]
    assert headings == ["Ciencia", "Filosofía", "Estudio", "Libre"]
    note = client.get("/notes/priors-are-beliefs-you-can-update").text
    assert "Puente entre categorías" in note


def test_own_category_labels(tmp_path: Path) -> None:
    config = Config.model_validate(
        {
            "site": {"language": "es"},
            "vault": VaultConfig(root=EXAMPLE_VAULT),
            "auth": {"mode": "none"},
            "categories": [
                {
                    "key": "science",
                    "label": {"en": "Lab", "es": "Laboratorio"},
                    "color": "#ff2fa0",
                    "species": "morel",
                },
                {"key": "philosophy", "label": "Pensar", "color": "#22d3ee", "species": "coral"},
            ],
        }
    )
    html = TestClient(create_app(config, environ={})).get("/projects").text
    assert "Laboratorio" in html
    assert "Pensar" in html


def test_new_notes_show_up_on_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from micelio.vault import index as index_module

    monkeypatch.setattr(index_module, "REFRESH_INTERVAL_S", 0.0)
    (tmp_path / "notes").mkdir()
    client = client_for(root=tmp_path)
    assert client.get("/notes/fresh").status_code == 404
    (tmp_path / "notes" / "Fresh.md").write_text("# Fresh\nHello", encoding="utf-8")
    assert "Hello" in client.get("/notes/fresh").text
