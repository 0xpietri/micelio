"""The viewer's graph settings panel: spacing, name size, short names, zoom (§7)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from micelio.i18n import available_languages, browser_strings

from .test_graph import client as client  # the fixture
from .test_public import SiteFor
from .test_public import site_for as site_for  # the fixture

STATIC = Path(__file__).resolve().parents[1] / "src" / "micelio" / "static"
SETTINGS_JS = STATIC / "js" / "graph-settings.js"
NODE = shutil.which("node")


def run_module(body: str) -> Any:
    """Run ``body`` with the settings module imported as ``m``; return what it prints."""
    assert NODE
    script = f'import * as m from "{SETTINGS_JS.as_uri()}";\n{body}'
    # Our own module and script, run by the Node.js found on PATH.
    done = subprocess.run(  # noqa: S603
        [NODE, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    return json.loads(done.stdout)


needs_node = pytest.mark.skipif(NODE is None, reason="needs Node.js to run the browser module")

FAKE_STORAGE = """
const store = new Map();
const storage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
};
const deny = () => { throw new Error("denied"); };
const blocked = { getItem: deny, setItem: deny };
"""


@needs_node
def test_defaults_and_cleaning() -> None:
    out = run_module(
        "console.log(JSON.stringify([m.defaults(), m.clean(null), m.clean([1]),"
        " m.clean({spacing: 999, labels: 'x', length: 13, shorten: 'no', extra: 1,"
        " zoom: {free: 100, box: -1, forest: '2'}})]));"
    )
    defaults, from_null, from_list, cleaned = out
    assert defaults == {
        "spacing": 100,
        "labels": 100,
        "shorten": True,
        "length": 28,
        "every": False,
        "zoom": {"free": 1, "box": 1, "forest": 1},
    }
    assert from_null == defaults
    assert from_list == defaults
    assert cleaned["spacing"] == 200  # clamped to the top
    assert cleaned["labels"] == 100  # not a number: the default
    assert cleaned["length"] in (12, 14)  # snapped to the slider's step
    assert cleaned["shorten"] is True  # not a boolean: the default
    assert cleaned["every"] is False
    assert "extra" not in cleaned
    assert cleaned["zoom"] == {"free": 8, "box": 1, "forest": 2}


@needs_node
def test_settings_are_saved_and_loaded() -> None:
    out = run_module(
        FAKE_STORAGE
        + """
const s = m.load(storage);
s.spacing = 160; s.labels = 130; s.shorten = false; s.length = 40; s.zoom.free = 1.69;
const saved = m.save(s, storage);
console.log(JSON.stringify({saved, again: m.load(storage), key: [...store.keys()]}));
"""
    )
    assert out["saved"] is True
    assert out["key"] == ["micelio.graph.v1"]
    again = out["again"]
    assert (again["spacing"], again["labels"], again["shorten"], again["length"]) == (
        160,
        130,
        False,
        40,
    )
    assert again["zoom"]["free"] == pytest.approx(1.69)


@needs_node
def test_blocked_or_broken_storage_falls_back_to_defaults() -> None:
    out = run_module(
        FAKE_STORAGE
        + """
storage.setItem(m.STORAGE_KEY, "{not json");
console.log(JSON.stringify({
  broken: m.load(storage), blocked: m.load(blocked), saved: m.save(m.defaults(), blocked),
  none: m.load(null),
}));
"""
    )
    assert out["broken"] == out["blocked"] == out["none"]
    assert out["broken"]["spacing"] == 100
    assert out["saved"] is False


@needs_node
def test_long_names_are_shortened_at_a_word() -> None:
    out = run_module(
        """
const s = m.defaults();
console.log(JSON.stringify([
  m.shorten("Short title", 28),
  m.shorten("A planet's tidal pull is smaller than a nearby wall's", 28),
  m.shorten("Supercalifragilisticexpialidocious", 12),
  m.shorten("Árboles, hongos y micelio en la ciudad", 20),
  m.labelText("A planet's tidal pull is smaller than a nearby wall's", {...s, shorten: false}),
  [...m.shorten("x".repeat(80), 28)].length,
]));
"""
    )
    short, worded, one_word, accented, whole, length = out
    assert short == "Short title"
    assert worded == "A planet's tidal pull is…"
    assert one_word == "Supercalifr…"
    assert accented == "Árboles, hongos y…"
    assert whole == "A planet's tidal pull is smaller than a nearby wall's"
    assert length == 28


# -- the panel on the pages --------------------------------------------------------------


def test_settings_strings_exist_in_every_language() -> None:
    keys = ("settings", "spacing", "labels", "shorten", "length", "chars", "every")
    for language in available_languages():
        strings = browser_strings(language)
        for key in (*keys, "reset", "zoom_in", "zoom_out", "fit"):
            assert strings.get(f"graph.{key}"), (language, key)
        assert "{count}" in strings["graph.chars"]
    assert browser_strings("es")["graph.settings"] == "Ajustes del grafo"


def test_every_graph_has_its_own_settings_gear() -> None:
    graph = (STATIC / "js" / "graph.js").read_text("utf-8")
    assert 'from "./graph-settings.js"' in graph
    assert 'from "./graph-panel.js"' in graph
    # Zoom, Fit and the ⚙ in every graph's top right corner.
    assert graph.count("function zoomButtons(") == 1
    assert graph.count("  zoomButtons(host, strings, {") == 1
    assert 'class: "graph-gear"' in graph
    assert "graphSection(panel, strings, { every })" in graph
    assert 'addEventListener("micelio:graph-settings"' in graph
    panel = (STATIC / "js" / "graph-panel.js").read_text("utf-8")
    assert 'from "./graph-settings.js"' in panel
    assert 'new CustomEvent("micelio:graph-settings"' in panel
    menu = (STATIC / "js" / "menu.js").read_text("utf-8")
    assert "graph-settings" not in menu
    explore = (STATIC / "js" / "explore.js").read_text("utf-8")
    assert "graph-zoom" not in explore


def test_settings_stay_in_the_browser() -> None:
    # Viewer settings are kept in localStorage only: no request to the server.
    source = SETTINGS_JS.read_text("utf-8")
    assert "localStorage" in source
    assert "fetch(" not in source
    assert "document" not in source  # no DOM: testable on its own
    graph = (STATIC / "js" / "graph.js").read_text("utf-8")
    assert "localStorage" not in graph
    assert not re.search(r"method:\s*\"(POST|PUT|PATCH|DELETE)\"", graph)


def test_explore_has_no_server_drawn_zoom_left(client: TestClient) -> None:
    html = client.get("/explore").text
    assert "graph-zoom" not in html
    assert "data-zoom" not in html


def test_visitors_get_the_same_graph_code(site_for: SiteFor) -> None:
    visitor = site_for().client  # not signed in
    for path in ("/explore", "/static/js/graph.js", "/static/js/graph-settings.js"):
        assert visitor.get(path).status_code == 200, path
    strings = visitor.get("/static/locales/en.json").json()
    assert strings["graph.settings"] == "Graph settings"


@needs_node
def test_a_project_always_opens_closed() -> None:
    # Digging is not remembered: a reload or another project starts with the underground
    # hidden, and the same button folds it back up.
    settings = (STATIC / "js" / "graph-settings.js").read_text(encoding="utf-8")
    graph = (STATIC / "js" / "graph.js").read_text(encoding="utf-8")
    assert "micelio.dug" not in settings + graph
    assert "sessionStorage" not in settings + graph
    assert "const state = { deep: false" in graph
    assert "go(!state.deep)" in graph
    out = run_module("console.log(JSON.stringify(m.clean({every: true}).every));")
    assert out is True


def test_notes_are_palette_dots_and_the_neighborhood_reads_like_words() -> None:
    graph = (STATIC / "js" / "graph.js").read_text(encoding="utf-8")
    # Notes and drafts are dots in their category's color, never pictures.
    assert 'picture("note"' not in graph
    assert 'nodePicture("draft")' not in graph
    # The Neighborhood draws each node as a small mark with its name on the same line.
    assert "function token(" in graph
    assert 'inline: mode === "box"' in graph
    assert 'text.setAttribute("text-anchor", "start")' in graph


def test_every_connection_lives_in_the_settings_panel() -> None:
    panel = (STATIC / "js" / "graph-panel.js").read_text("utf-8")
    graph = (STATIC / "js" / "graph.js").read_text("utf-8")
    assert 'name: "graph-every"' in panel
    assert "settings_note" not in panel
    # One way back up: the dig button; no bar at the bottom.
    assert "forest-bar" not in graph
    assert 'every: mode === "forest"' in graph
