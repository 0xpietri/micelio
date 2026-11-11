"""The Appearance page saves itself (§7b): no Save button, a folded prompt guide, an
empty tagline that stays empty, and a click outside that goes back."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from .test_landing import client as client  # the fixture
from .test_landing import form_token, save

STATIC = Path(__file__).resolve().parents[1] / "src" / "micelio" / "static"
JSON = {"Accept": "application/json"}


def test_autosave_answers_json_and_repaints(client: TestClient) -> None:
    data = {"csrf": form_token(client), "palette": "tokyo-night", "soil": "44", "recolor": "on"}
    response = client.post("/appearance", data=data, headers=JSON, follow_redirects=False)
    assert response.status_code == 200
    answer = response.json()
    assert answer["ok"] is True
    backdrop = answer["backdrop"]
    assert backdrop["soil"] == 44
    assert backdrop["url"].startswith("/static/")
    assert backdrop["ramp"].count("#") >= 3  # recolored: the palette's ramp
    assert client.get("/api/landing").json()["palette"]["key"] == "tokyo-night"


def test_autosave_without_the_token_is_refused(client: TestClient) -> None:
    data = {"palette": "rose-pine"}
    response = client.post("/appearance", data=data, headers=JSON, follow_redirects=False)
    assert response.status_code == 403
    assert response.json() == {"ok": False, "error": "form"}
    assert client.get("/api/landing").json()["palette"]["key"] == "psychedelic"


def test_plain_form_posts_still_redirect(client: TestClient) -> None:
    assert save(client, palette="rose-pine") == "/appearance?done=saved"


def test_page_is_built_for_autosave(client: TestClient) -> None:
    html = client.get("/appearance").text
    assert "data-autosave" in html
    assert 'id="autosave-status"' in html
    # The Save buttons stay for browsers without JavaScript; the script hides them.
    assert html.count('class="save-fallback"') == 2
    assert '<details class="prompt" id="prompt"' in html
    assert "<summary><h2>Make your own background</h2></summary>" in html
    script = (STATIC / "js" / "appearance.js").read_text("utf-8")
    assert "form[data-autosave]" in script
    assert "clickOutsideLeaves" in script


def test_empty_tagline_shows_nothing(client: TestClient) -> None:
    assert "A living notebook of ideas" in client.get("/").text  # never saved: the default
    page = client.get("/appearance").text
    assert 'name="tagline" maxlength="120" value="A living notebook of ideas"' in page
    save(client, tagline="")
    landing = client.get("/").text
    assert "A living notebook of ideas" not in landing
    assert '<p class="tagline">' not in landing
    assert 'name="tagline" maxlength="120" value=""' in client.get("/appearance").text
    save(client, tagline="Ideas que crecen")
    assert '<p class="tagline">Ideas que crecen</p>' in client.get("/").text
