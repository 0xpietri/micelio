"""The included scenes and the illustrated mushrooms (§7b): each scene brings its soil
line, its recolor default and its mushroom style; a choice saved before scenes existed
starts on the default scene with that scene's own values."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from micelio.appearance import Appearance, AppearanceStore
from micelio.config import SPECIES, Config, VaultConfig
from micelio.i18n import load_strings
from micelio.looks import clean_look
from micelio.scenes import DEFAULT_SCENE, MUSHROOM_STYLES, SCENES

from .conftest import EXAMPLE_VAULT
from .test_landing import client as client  # the fixture
from .test_landing import form_token, make_config, png

STATIC = Path(__file__).resolve().parents[1] / "src" / "micelio" / "static"
JSON = {"Accept": "application/json"}


def _draw_js_species() -> list[str]:
    source = (STATIC / "js" / "draw.js").read_text("utf-8")
    block = re.search(r"export const SPECIES = \[(.*?)\];", source, re.S)
    assert block is not None
    return re.findall(r'"([a-z-]+)"', block.group(1))


def test_every_scene_ships_a_painting_and_a_thumbnail() -> None:
    assert DEFAULT_SCENE in SCENES
    for scene in SCENES.values():
        for url in (scene.url, scene.thumb):
            path = STATIC / url.removeprefix("/static/")
            assert path.read_bytes()[8:12] == b"WEBP", url
        assert 30 <= scene.soil <= 70
        assert scene.mushrooms in MUSHROOM_STYLES
    # Only the first painting is recolored by default: the others keep their colors.
    assert [k for k, s in SCENES.items() if s.recolor] == ["dusk"]


def test_every_illustrated_style_has_every_species() -> None:
    species = _draw_js_species()
    assert sorted(species) == sorted(SPECIES)
    for style in MUSHROOM_STYLES:
        if style == "drawn":
            continue
        for kind in species:
            path = STATIC / "img" / "mushrooms" / style / f"{kind}.webp"
            assert path.read_bytes()[8:12] == b"WEBP", path


def test_every_scene_and_species_has_a_name() -> None:
    for language in ("en", "es"):
        strings = load_strings(language)
        for key in SCENES:
            assert strings.get(f"scene.{key}"), (language, key)
        for kind in SPECIES:
            assert strings.get(f"species.{kind}"), (language, kind)
        for style in MUSHROOM_STYLES:
            assert strings.get(f"appearance.mushrooms_{style}"), (language, style)


def test_a_scene_sets_soil_recolor_and_mushrooms() -> None:
    neon = Appearance(scene="neon-sun")
    assert neon.painting.url == "/static/img/scenes/neon-sun.webp"
    assert not neon.recolors
    assert neon.mushroom_style == "neon"
    assert Appearance(scene="dusk").recolors
    assert Appearance(scene="dusk").mushroom_style == "drawn"
    assert Appearance(scene="dusk", mushrooms="brush").mushroom_style == "brush"
    # An uploaded image is never recolored by default, and its mushrooms are drawn.
    own = Appearance(scene="neon-sun", background="own", own_type="png")
    assert not own.recolors
    assert own.mushroom_style == "drawn"


def test_a_choice_saved_before_scenes_starts_on_the_default_scene(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = AppearanceStore(config)
    store.write_setting("appearance", {"palette": "tokyo-night", "recolor": True, "soil": 40})
    now = store.current()
    assert now.palette == "tokyo-night"
    assert now.scene == DEFAULT_SCENE
    assert not now.recolors  # the old box was about the first painting
    assert now.soil == SCENES[DEFAULT_SCENE].soil
    store.save(now)
    assert store.current().soil == SCENES[DEFAULT_SCENE].soil


def test_a_legacy_upload_keeps_its_soil(tmp_path: Path) -> None:
    store = AppearanceStore(make_config(tmp_path))
    store.store_background(png())
    with closing(sqlite3.connect(tmp_path / "data" / "site.sqlite3")) as db:
        raw = json.loads(
            db.execute("SELECT value FROM settings WHERE key = 'appearance'").fetchone()[0]
        )
    raw.pop("scene")
    raw["soil"] = 41
    store.write_setting("appearance", raw)
    assert store.current().uses_own
    assert store.current().soil == 41


def test_picking_a_scene_brings_its_values(client: TestClient) -> None:
    token = form_token(client)

    def post(**fields: str) -> dict[str, object]:
        data = {"csrf": token, "palette": "tokyo-night", "soil": "52", **fields}
        response = client.post("/appearance", data=data, headers=JSON)
        assert response.status_code == 200
        backdrop = response.json()["backdrop"]
        assert isinstance(backdrop, dict)
        return backdrop

    neon = post(background="neon-sun", recolor="on")
    assert neon == {
        "url": "/static/img/scenes/neon-sun.webp",
        "soil": SCENES["neon-sun"].soil,
        "ramp": "",
        "recolor": False,  # a new scene starts with its own default, not the old box
        "mushrooms": "neon",
    }
    # On the same scene the box and the slider count.
    again = post(background="neon-sun", recolor="on", soil="47")
    assert again["recolor"] is True
    assert again["soil"] == 47
    dusk = post(background="dusk")
    assert dusk["recolor"] is True
    assert dusk["mushrooms"] == "drawn"
    assert post(background="no-such-scene")["url"] == "/static/img/psychedelic-dusk.webp"
    landing = client.get("/api/landing").json()
    assert landing["background"]["url"] == "/static/img/psychedelic-dusk.webp"
    chosen = post(background="dusk", recolor="on", mushrooms="blacklight")
    assert chosen["mushrooms"] == "blacklight"
    assert '<meta name="micelio-mushrooms" content="blacklight">' in client.get("/journal").text


def test_the_appearance_page_lists_every_scene(client: TestClient) -> None:
    page = client.get("/appearance").text
    for key, scene in SCENES.items():
        assert f'value="{key}" data-soil="{scene.soil}"' in page
        assert f'src="{scene.thumb}"' in page
    assert re.search(rf'value="{DEFAULT_SCENE}"[^>]* checked', page)
    assert '<select name="mushrooms"' in page


def test_the_config_names_a_scene(tmp_path: Path) -> None:
    vault = VaultConfig(root=EXAMPLE_VAULT)
    config = Config.model_validate({"vault": vault, "landing": {"scene": "brush-night"}})
    assert config.landing.scene == "brush-night"
    with pytest.raises(ValueError, match="unknown scene"):
        Config.model_validate({"vault": vault, "landing": {"scene": "nope"}})


def test_the_new_species_can_be_chosen() -> None:
    for kind in ("spiral", "oyster", "turkey-tail"):
        assert clean_look({"species": kind}, "project") == {"species": kind}
