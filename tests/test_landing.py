from __future__ import annotations

import re
import struct
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from micelio.app import create_app
from micelio.appearance import (
    MAX_UPLOAD_BYTES,
    PALETTES,
    Appearance,
    AppearanceStore,
    ImageError,
    category_colors,
    check_upload,
    image_info,
    palette_named,
)
from micelio.config import PALETTE_NAMES, Config, ConfigError, VaultConfig, load_config
from micelio.landing import LandingBuilder
from micelio.vault import VaultIndex

from .conftest import EXAMPLE_VAULT
from .test_auth_web import Site, SiteFactory
from .test_auth_web import make_site as make_site  # the fixture

STATIC = Path(__file__).resolve().parents[1] / "src" / "micelio" / "static"

PLANETS = "do-planets-at-birth-leave-a-trace"
BAYES = "learning-bayesian-statistics"
FREE_WILL = "free-will-in-a-determined-world"
PRIORS = "priors-are-beliefs-you-can-update"


def png(width: int = 1536, height: int = 1024) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + bytes(20)
    )


def jpeg(width: int = 1536, height: int = 1024) -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + bytes(9)
    sof = b"\xff\xc0" + struct.pack(">HBHH", 17, 8, height, width) + bytes(12)
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


def webp(kind: bytes, width: int = 1536, height: int = 1024) -> bytes:
    if kind == b"VP8X":
        body = bytes(4) + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    elif kind == b"VP8 ":
        body = bytes(3) + b"\x9d\x01\x2a" + struct.pack("<HH", width, height)
    else:
        bits = (width - 1) | ((height - 1) << 14)
        body = b"\x2f" + bits.to_bytes(4, "little")
    chunk = kind + struct.pack("<I", len(body)) + body
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk + bytes(8)


def make_config(tmp_path: Path, **site: object) -> Config:
    return Config.model_validate(
        {
            "site": {"owner": "Marcos Pietri", **site},
            "vault": VaultConfig(root=EXAMPLE_VAULT),
            "data": {"dir": tmp_path / "data"},
            "auth": {"mode": "none"},
        }
    )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(make_config(tmp_path), environ={})) as c:
        yield c


def form_token(client: TestClient) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', client.get("/appearance").text)
    assert match
    return match.group(1)


def save(client: TestClient, **fields: str) -> str:
    data = {"csrf": form_token(client), "palette": "psychedelic", "soil": "52", **fields}
    response = client.post("/appearance", data=data, follow_redirects=False)
    assert response.status_code == 303
    return response.headers["location"]


# -- config ---------------------------------------------------------------------------


def test_headline_and_tagline_per_language(tmp_path: Path) -> None:
    config = make_config(tmp_path, headline={"en": "My forest", "es": "Mi bosque"}, tagline="Hi")
    assert config.site.headline_for("es") == "Mi bosque"
    assert config.site.headline_for("fr") == "My forest"
    assert config.site.tagline_for("es") == "Hi"
    assert Config().site.headline_for("en") is None


def test_landing_config(tmp_path: Path) -> None:
    path = tmp_path / "micelio.toml"
    path.write_text('[landing]\npalette = "rose-pine"\nsoil = 40\n', encoding="utf-8")
    config = load_config(path)
    assert config.landing.palette == "rose-pine"
    assert config.landing.soil == 40
    for bad in ('palette = "neon"', "soil = 90"):
        path.write_text(f"[landing]\n{bad}\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(path)


def test_example_config_takes_colors_from_the_palette() -> None:
    config = load_config(Path(__file__).resolve().parents[1] / "micelio.example.toml")
    assert all(c.color is None for c in config.categories)
    assert config.landing.palette == "psychedelic"


# -- palettes and colors ----------------------------------------------------------------


def test_four_palettes_with_valid_colors() -> None:
    assert tuple(PALETTES) == PALETTE_NAMES
    hex_color = re.compile(r"^#[0-9a-f]{6}$")
    for palette in PALETTES.values():
        colors = [*palette.cats, *palette.spare, *palette.crystals, *palette.swatch]
        colors += [palette.ink, palette.stem, palette.thread, palette.spore, palette.sun]
        colors += [palette.accent, palette.button, palette.button_alt, *(palette.ramp or ())]
        assert all(hex_color.match(c) for c in colors), palette.key
    assert PALETTES["psychedelic"].ramp is None
    assert all(PALETTES[k].ramp for k in PALETTE_NAMES[1:])


def test_category_colors_follow_the_palette_unless_fixed(tmp_path: Path) -> None:
    config = Config.model_validate(
        {
            "categories": [
                {"key": "a", "species": "morel"},
                {"key": "b", "species": "coral", "color": "#123456"},
                *({"key": f"x{i}", "species": "parasol"} for i in range(8)),
            ]
        }
    )
    colors = category_colors(config, PALETTES["tokyo-night"])
    assert colors["a"] == "#bb9af7"
    assert colors["b"] == "#123456"
    assert colors["x7"] == PALETTES["tokyo-night"].slot(9) == PALETTES["tokyo-night"].cats[1]


def test_palette_named() -> None:
    assert palette_named("catppuccin", "psychedelic") == "catppuccin"
    assert palette_named("neon", "rose-pine") == "rose-pine"
    assert palette_named(None, "psychedelic") == "psychedelic"


# -- images ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (png(1600, 900), "png"),
        (jpeg(1600, 900), "jpeg"),
        (webp(b"VP8X", 1600, 900), "webp"),
        (webp(b"VP8 ", 1600, 900), "webp"),
        (webp(b"VP8L", 1600, 900), "webp"),
    ],
)
def test_image_info_reads_the_header(data: bytes, kind: str) -> None:
    assert image_info(data) == (kind, 1600, 900)


def test_jpeg_skips_markers_before_the_size() -> None:
    data = jpeg()
    dht = b"\xff\xc4" + struct.pack(">H", 4) + bytes(2)
    assert image_info(data[:2] + dht + data[2:])[1:] == (1536, 1024)


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"", "empty"),
        (b"GIF89a" + bytes(40), "type"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "type"),
        (b"\xff\xd8\xff\xd9" + bytes(20), "type"),
        (png(800, 600), "small"),
        (png() + bytes(MAX_UPLOAD_BYTES), "size"),
    ],
)
def test_check_upload_refuses(data: bytes, code: str) -> None:
    with pytest.raises(ImageError) as caught:
        check_upload(data)
    assert caught.value.code == code


# -- the store ------------------------------------------------------------------------


def test_store_defaults_without_writing(tmp_path: Path) -> None:
    store = AppearanceStore(make_config(tmp_path))
    assert store.current() == Appearance()
    assert not (tmp_path / "data").exists()


def test_store_round_trip_and_uploads(tmp_path: Path) -> None:
    store = AppearanceStore(make_config(tmp_path))
    store.save(Appearance(palette="rose-pine", soil=44, headline="Hola"))
    assert store.current().palette == "rose-pine"
    assert store.current().soil == 44

    first = store.store_background(png())
    assert first.uses_own
    assert first.own_type == "png"
    assert not first.recolors
    second = store.store_background(webp(b"VP8X"))
    assert second.own_type == "webp"
    assert second.own_version == first.own_version + 1
    assert sorted(p.name for p in (tmp_path / "data" / "backgrounds").iterdir()) == [
        "background.webp"
    ]
    assert store.current().headline == "Hola"

    removed = store.remove_background()
    assert not removed.uses_own
    assert removed.recolors
    assert not any((tmp_path / "data" / "backgrounds").iterdir())
    store.close()


def test_store_ignores_a_missing_file_and_bad_values(tmp_path: Path) -> None:
    store = AppearanceStore(make_config(tmp_path))
    store.save(Appearance(background="own", own_type="png", soil=10))
    now = store.current()
    assert now.background == "builtin"
    assert now.own_type is None
    assert now.soil == 52
    store.close()


# -- what the landing draws -----------------------------------------------------------


def test_landing_data(example_index: VaultIndex) -> None:
    data = LandingBuilder(example_index.config, example_index).build(Appearance())
    projects = {p["id"]: p for p in data["projects"]}
    assert set(projects) >= {PLANETS, BAYES, FREE_WILL}
    assert projects[PLANETS]["species"] == "fly-agaric"
    assert projects[PLANETS]["color"] == "#ff2fa0"
    assert projects["an-abandoned-idea"]["status"] == "closed"
    assert projects["cities-as-living-organisms"]["status"] == "draft"
    notes = {n["id"]: n for n in data["notes"]}
    assert notes[PRIORS]["projects"] == sorted([BAYES, FREE_WILL])
    assert all(n["href"].startswith("/notes/") for n in notes.values())
    assert all(a in notes and b in notes for a, b in data["links"])
    sources = {s["id"]: s for s in data["sources"]}
    assert BAYES in sources["mcelreath-statistical-rethinking"]["links"]
    journal = data["journal"]
    assert len(journal) == 2
    assert journal[0]["links"] == [PLANETS]
    assert data["hidden"] == 0
    assert data["background"] == {
        "url": "/static/img/psychedelic-dusk.webp",
        "recolor": False,
        "soil": 52,
    }


def test_landing_draws_only_the_most_connected_notes(tmp_path: Path) -> None:
    config = Config.model_validate(
        {"vault": VaultConfig(root=EXAMPLE_VAULT), "landing": {"max_notes": 10}}
    )
    index = VaultIndex(config)
    index.refresh(force=True)
    data = LandingBuilder(config, index).build(Appearance(palette="catppuccin"))
    assert len(data["notes"]) == 10
    assert data["hidden"] == sum(1 for n in index.notes.values() if n.type == "note") - 10
    assert data["palette"]["key"] == "catppuccin"
    assert data["background"]["recolor"] is True


# -- pages ----------------------------------------------------------------------------


def test_landing_page(client: TestClient) -> None:
    html = client.get("/").text
    assert '<h1 class="headline" id="headline">Marcos Pietri&#39;s Micelio</h1>' in html
    assert "A living notebook of ideas" in html
    assert 'href="/explore"' in html
    assert 'href="/projects"' in html
    assert "/static/vendor/d3-force/d3-force.bundle.min.js" in html
    assert f'href="/projects/{PLANETS}" tabindex="-1">Project: Do planets' in html
    data = client.get("/api/landing")
    assert data.headers["cache-control"] == "no-store"
    assert {p["id"] for p in data.json()["projects"]} >= {PLANETS, BAYES}


def test_landing_in_spanish_has_no_english(tmp_path: Path) -> None:
    config = make_config(tmp_path, language="es")
    with TestClient(create_app(config, environ={})) as client:
        html = client.get("/").text
        for text in (
            "El micelio de Marcos Pietri",
            "Un cuaderno vivo de ideas",
            "Explorar el grafo",
        ):
            assert text in html
        for english in ("micelio</h1>", "A living notebook", "Explore the graph", "Project:"):
            assert english not in html
        page = client.get("/appearance").text
        for text in ("Paleta de colores", "Creá tu propio fondo", "Copiar prompt", "ESTILO"):
            assert text in page
        for english in ("Color palette", "Copy prompt", "STYLE\n", "Upload an image"):
            assert english not in page


def test_saved_texts_replace_the_defaults_and_are_escaped(client: TestClient) -> None:
    save(client, headline="  <b>Mi\tbosque</b>  ", tagline="Ideas que crecen")
    html = client.get("/").text
    assert "&lt;b&gt;Mi bosque&lt;/b&gt;</h1>" in html
    assert "Ideas que crecen" in html


def test_palette_changes_every_page(client: TestClient) -> None:
    assert save(client, palette="tokyo-night") == "/appearance?done=saved"
    assert ".cat-science { --cat: #bb9af7; }" in client.get("/theme.css").text
    assert "--pal-sun: #7aa2f7;" in client.get("/theme.css").text
    categories = client.get("/api/graph").json()["categories"]
    assert categories[0]["color"] == "#bb9af7"
    landing = client.get("/api/landing").json()
    assert landing["palette"]["key"] == "tokyo-night"
    assert landing["background"]["recolor"] is False  # the box was left unticked
    save(client, palette="tokyo-night", recolor="on")
    assert client.get("/api/landing").json()["background"]["recolor"] is True


def test_bad_values_are_ignored(client: TestClient) -> None:
    save(client, palette="neon", soil="99", background="own")
    landing = client.get("/api/landing").json()
    assert landing["palette"]["key"] == "psychedelic"
    assert landing["background"]["soil"] == 52
    assert landing["background"]["url"].startswith("/static/")


def test_forms_need_the_token(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/appearance", data={"palette": "rose-pine"}, follow_redirects=False)
    assert response.headers["location"] == "/appearance?error=form"
    files = {"image": ("x.png", png(), "image/png")}
    response = client.post(
        "/appearance/background", files=files, data={"csrf": "x"}, follow_redirects=False
    )
    assert response.headers["location"] == "/appearance?error=form"
    response = client.post("/appearance/background/remove", follow_redirects=False)
    assert response.headers["location"] == "/appearance?error=form"
    assert client.get("/api/landing").json()["palette"]["key"] == "psychedelic"
    assert not (tmp_path / "data" / "backgrounds").exists()
    assert "The form expired" in client.get("/appearance?error=form").text


def test_upload_serve_and_remove_a_background(client: TestClient) -> None:
    token = form_token(client)
    files = {"image": ("evil.png.exe", webp(b"VP8L"), "application/octet-stream")}
    response = client.post(
        "/appearance/background", files=files, data={"csrf": token}, follow_redirects=False
    )
    assert response.headers["location"] == "/appearance?done=uploaded"
    background = client.get("/api/landing").json()["background"]
    assert background == {"url": "/appearance/background?v=1", "recolor": False, "soil": 52}
    image = client.get(background["url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/webp"
    assert "Background uploaded." in client.get("/appearance?done=uploaded").text

    response = client.post(
        "/appearance/background/remove", data={"csrf": token}, follow_redirects=False
    )
    assert response.headers["location"] == "/appearance?done=removed"
    assert client.get("/appearance/background").status_code == 404
    assert client.get("/api/landing").json()["background"]["url"].startswith("/static/")


@pytest.mark.parametrize(
    ("data", "code"),
    [(b"", "empty"), (b"GIF89a" + bytes(40), "type"), (png(640, 480), "small")],
)
def test_rejected_uploads_say_why(client: TestClient, data: bytes, code: str) -> None:
    files = {"image": ("bg.png", data, "image/png")}
    token = form_token(client)
    response = client.post(
        "/appearance/background", files=files, data={"csrf": token}, follow_redirects=False
    )
    assert response.headers["location"] == f"/appearance?error={code}"
    assert client.get("/appearance/background").status_code == 404


def test_appearance_needs_sign_in(make_site: SiteFactory) -> None:
    site: Site = make_site()
    response = site.client.get("/appearance", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")
    # The landing and its background are public; without an upload there is none.
    assert site.client.get("/appearance/background").status_code == 404
    response = site.client.post(
        "/appearance", data={"palette": "rose-pine"}, follow_redirects=False
    )
    assert response.status_code == 401
    site.sign_in()
    page = site.client.get("/appearance")
    assert page.status_code == 200
    token = re.search(r'action="/appearance".*?name="csrf" value="([^"]+)"', page.text, re.DOTALL)
    assert token
    response = site.client.post(
        "/appearance",
        data={"csrf": token.group(1), "palette": "rose-pine", "soil": "50"},
        follow_redirects=False,
    )
    assert response.headers["location"] == "/appearance?done=saved"
    assert "--pal-sun: #ebbcba;" in site.client.get("/theme.css").text


def test_prompt_guide_has_fixed_rules_and_defaults(client: TestClient) -> None:
    html = client.get("/appearance").text
    assert "1536 x 1024 pixels (3:2)" in html
    assert "exactly 52% of the height" in html
    assert "No mushrooms or fungi" in html
    assert "#12051f, #9b5cff" in html
    strings = client.get("/static/locales/es.json").json()
    assert "{soil}" in strings["prompt.template"]
    assert "{style}" in strings["prompt.template"]


# -- vendored files -------------------------------------------------------------------


def test_vendored_d3_force_and_font() -> None:
    bundle = (STATIC / "vendor" / "d3-force" / "d3-force.bundle.min.js").read_text(encoding="utf-8")
    for header in (
        "d3-dispatch/ v3.0.1",
        "d3-quadtree/ v3.0.1",
        "d3-timer/ v3.0.1",
        "d3-force/ v3.0.0",
    ):
        assert header in bundle
    assert (STATIC / "vendor" / "d3-force" / "LICENSE").is_file()
    fonts = STATIC / "vendor" / "fonts" / "shrikhand"
    assert (fonts / "shrikhand-latin.woff2").read_bytes()[:4] == b"wOF2"
    assert "SIL Open Font License" in (fonts / "OFL.txt").read_text(encoding="utf-8")
    assert (STATIC / "img" / "psychedelic-dusk.webp").read_bytes()[8:12] == b"WEBP"
    readme = (STATIC / "vendor" / "README.md").read_text(encoding="utf-8")
    assert "d3-force" in readme
    assert "Shrikhand" in readme
