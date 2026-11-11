"""Diving from the landing into /explore (§7a, §7c): a knot's click sinks the view and
opens the graph centered on that note."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from .test_landing import client as client  # the fixture

STATIC = Path(__file__).resolve().parents[1] / "src" / "micelio" / "static"


def test_landing_dives_into_explore() -> None:
    script = (STATIC / "js" / "landing.js").read_text("utf-8")
    assert "function dive(" in script
    assert "/explore?focus=" in script
    assert "reduced()" in script  # reduced motion goes straight there
    css = (STATIC / "css" / "landing.css").read_text("utf-8")
    assert ".scene.diving .forest" in css


def test_explore_arrives_on_the_note() -> None:
    script = (STATIC / "js" / "explore.js").read_text("utf-8")
    assert 'get("focus")' in script
    assert "graph.highlight(" in script
    assert ".explore-stage.arriving" in (STATIC / "css" / "graph.css").read_text("utf-8")


def test_explore_with_a_focus_still_renders(client: TestClient) -> None:
    response = client.get("/explore?focus=bayes-theorem-in-one-line")
    assert response.status_code == 200
    assert "data-explore" in response.text
    # An unknown or hostile focus is only read by the script, never echoed.
    hostile = client.get('/explore?focus="><script>x</script>')
    assert hostile.status_code == 200
    assert "<script>x</script>" not in hostile.text
