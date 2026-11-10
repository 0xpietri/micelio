"""The landing's look on every page (§7c) and the type settings of the Appearance page (§7b)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from micelio.app import create_app
from micelio.appearance import Appearance, AppearanceStore
from micelio.config import TEXT_FONTS, TITLE_FONTS, Config, TypographyConfig, VaultConfig
from micelio.pages import theme_css

from .conftest import EXAMPLE_VAULT
from .test_auth_web import Site, SiteFactory
from .test_auth_web import make_site as make_site  # the fixture
from .test_landing import png, save

STATIC = Path(__file__).resolve().parents[1] / "src" / "micelio" / "static"
PAGES = (
    "/projects",
    "/projects/learning-bayesian-statistics",
    "/notes/priors-are-beliefs-you-can-update",
    "/explore",
    "/journal",
    "/health",
    "/appearance",
)


def make_config(tmp_path: Path, **sections: object) -> Config:
    return Config.model_validate(
        {
            "vault": VaultConfig(root=EXAMPLE_VAULT),
            "data": {"dir": tmp_path / "data"},
            "auth": {"mode": "none"},
            **sections,
        }
    )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(make_config(tmp_path), environ={})) as c:
        yield c


def backdrop(html: str) -> re.Match[str]:
    match = re.search(
        r'<svg class="backdrop" id="backdrop" viewBox="0 (\d+) 1536 (\d+)" '
        r'preserveAspectRatio="(\w+) slice" data-soil="(\d+)" data-ramp="([^"]*)"',
        html,
    )
    assert match, "no backdrop"
    return match


# -- config -----------------------------------------------------------------------------


def test_typography_defaults_and_limits(tmp_path: Path) -> None:
    typography = make_config(tmp_path).typography
    assert typography == TypographyConfig()
    assert (typography.title_font, typography.text_font) == ("shrikhand", "system")
    assert (typography.title_size, typography.text_size, typography.graph_labels) == (100, 16, 100)
    assert typography.title_effect == "poster"
    for bad in (
        {"title_font": "comic-sans"},
        {"text_font": "papyrus"},
        {"title_size": 200},
        {"text_size": 9},
        {"graph_labels": 10},
        {"title_effect": "neon"},
        {"colour": "red"},
    ):
        with pytest.raises(ValidationError):
            TypographyConfig.model_validate(bad)


def test_example_config_documents_typography() -> None:
    text = (Path(__file__).resolve().parents[1] / "micelio.example.toml").read_text("utf-8")
    assert "[typography]" in text
    for key in ("title_font", "text_font", "title_size", "text_size", "graph_labels"):
        assert f"\n{key} = " in text
    assert "max_nodes = 400" in text


# -- the store --------------------------------------------------------------------------


def test_config_typography_is_the_default_and_saved_values_win(tmp_path: Path) -> None:
    config = make_config(
        tmp_path, typography={"title_font": "fraunces", "text_size": 18, "title_effect": "plain"}
    )
    store = AppearanceStore(config)
    look = store.current()
    assert (look.title_font, look.text_size, look.title_effect) == ("fraunces", 18, "plain")
    store.save(Appearance(title_font="righteous", text_font="literata", graph_labels=130))
    look = store.current()
    assert (look.title_font, look.text_font, look.graph_labels) == ("righteous", "literata", 130)
    store.close()


def test_store_ignores_bad_type_values(tmp_path: Path) -> None:
    store = AppearanceStore(make_config(tmp_path))
    store.save(Appearance())
    store._conn().execute(
        "UPDATE settings SET value = ?",
        (
            '{"title_font": "x", "text_font": 3, "title_size": 999, "text_size": true,'
            ' "graph_labels": "120", "title_effect": "", "site_name": "  A\\tname  "}',
        ),
    )
    look = store.current()
    assert (look.title_font, look.text_font) == ("shrikhand", "system")
    assert (look.title_size, look.text_size, look.graph_labels) == (100, 16, 100)
    assert look.title_effect == "poster"
    assert look.site_name == "A name"
    store.close()


# -- theme.css --------------------------------------------------------------------------


def test_theme_css_carries_palette_and_type() -> None:
    css = theme_css(
        {"science": "#ff2fa0"},
        Appearance(
            palette="rose-pine",
            title_font="bagel-fat-one",
            text_font="atkinson-hyperlegible",
            title_size=120,
            text_size=18,
            graph_labels=90,
            title_effect="plain",
        ),
    )
    for rule in (
        "--pal-ink: #191724;",
        "--pal-stem: #e0def4;",
        "--pal-spore: #f6c177;",
        "--pal-crystal: #9ccfd8;",
        "--title-font: var(--font-bagel-fat-one);",
        "--text-font: var(--font-atkinson-hyperlegible);",
        "--title-scale: 1.2;",
        "--text-size: 18px;",
        "--label-scale: 0.9;",
        "--title-stroke: 0;",
        "--title-shadow: none;",
        ".cat-science { --cat: #ff2fa0; }",
    ):
        assert rule in css, rule
    poster = theme_css({}, Appearance())
    assert "--title-stroke: 0.08em;" in poster
    assert "--title-shadow: 0.05em 0.06em 0 var(--pal-accent);" in poster


def test_every_font_has_a_face_a_stack_a_file_and_a_license() -> None:
    css = (STATIC / "css" / "fonts.css").read_text("utf-8")
    for font in (*TITLE_FONTS, *TEXT_FONTS):
        assert f"--font-{font}:" in css, font
        assert f".font-{font} " in css, font
    for url in re.findall(r'url\("\.\./([^"]+)"\)', css):
        path = STATIC / url
        assert path.read_bytes()[:4] == b"wOF2", url
        assert "SIL Open Font License" in (path.parent / "OFL.txt").read_text("utf-8")
    readme = (STATIC / "vendor" / "README.md").read_text("utf-8")
    for name in ("Righteous", "Bagel Fat One", "Fraunces", "Atkinson Hyperlegible", "Literata"):
        assert name in readme


# -- the painted background on every page -----------------------------------------------


def test_every_page_has_the_painted_background(client: TestClient) -> None:
    for path in PAGES:
        html = client.get(path).text
        top, height, _align, soil, ramp = backdrop(html).groups()
        assert int(top) + int(height) == 1024, path
        assert soil == "52"
        assert ramp == ""  # the psychedelic palette keeps the painting as it is
        assert 'href="/static/img/psychedelic-dusk.webp"' in html
        assert '/static/css/fonts.css"' in html
        assert '<meta name="color-scheme" content="dark">' in html
        assert "backdrop.js" not in html
    # Explore lies underground; reading pages show the horizon at the top.
    assert backdrop(client.get("/explore").text).group(1) == str(round(1024 * 0.52) + 20)
    assert backdrop(client.get("/journal").text).group(1) == str(round(1024 * 0.52) - 330)
    # The landing draws its own scene.
    assert 'id="backdrop"' not in client.get("/").text


def test_recolored_and_uploaded_backgrounds_reach_every_page(client: TestClient) -> None:
    save(client, palette="tokyo-night", recolor="on", soil="40")
    html = client.get("/journal").text
    _, _, _, soil, ramp = backdrop(html).groups()
    assert soil == "40"
    assert ramp.split(" ")[0] == "#16161e"
    assert '<script type="module" src="/static/js/backdrop.js"></script>' in html
    token = re.search(r'name="csrf" value="([^"]+)"', client.get("/appearance").text)
    assert token
    client.post(
        "/appearance/background",
        files={"image": ("bg.png", png(), "image/png")},
        data={"csrf": token.group(1)},
    )
    html = client.get("/projects").text
    assert 'href="/appearance/background?v=1"' in html
    assert backdrop(html).group(5) == ""  # an upload is not recolored unless asked


def test_no_light_theme_is_left() -> None:
    for name in ("micelio.css", "graph.css", "appearance.css", "landing.css"):
        css = (STATIC / "css" / name).read_text("utf-8")
        assert "prefers-color-scheme" not in css, name


# -- the Appearance page's type settings -------------------------------------------------


def test_appearance_page_offers_fonts_and_sizes(client: TestClient) -> None:
    html = client.get("/appearance").text
    for font in TITLE_FONTS:
        assert f'name="title_font" value="{font}"' in html
        assert f'class="sample title-sample font-{font}"' in html
    for font in TEXT_FONTS:
        assert f'name="text_font" value="{font}"' in html
    assert 'name="title_font" value="shrikhand" checked' in html
    assert 'name="title_effect" value="poster" checked' in html
    sizes = (("title_size", 70, 140), ("text_size", 14, 20), ("graph_labels", 80, 150))
    for name, low, high in sizes:
        assert f'name="{name}" id="{name}" min="{low}" max="{high}"' in html
    assert 'title_font = "shrikhand"' in html  # the same choices as micelio.toml lines


def test_saving_type_settings_changes_every_page(client: TestClient) -> None:
    location = save(
        client,
        title_font="fraunces",
        text_font="space-grotesk",
        title_size="130",
        text_size="18",
        graph_labels="140",
        title_effect="plain",
        site_name="  Bosque <de> ideas ",
    )
    assert location == "/appearance?done=saved"
    css = client.get("/theme.css").text
    assert "--title-font: var(--font-fraunces);" in css
    assert "--text-font: var(--font-space-grotesk);" in css
    assert "--title-scale: 1.3;" in css
    assert "--label-scale: 1.4;" in css
    assert "--title-shadow: none;" in css
    html = client.get("/projects").text
    assert '<a class="brand" href="/">Bosque &lt;de&gt; ideas</a>' in html
    assert "<title>Projects · Bosque &lt;de&gt; ideas</title>" in html
    assert "Bosque &lt;de&gt; ideas</h1>" in client.get("/").text  # the landing's default title
    # Bad values keep what was saved before.
    save(client, title_font="wingdings", text_size="40", graph_labels="-1", title_effect="neon")
    look = client.get("/theme.css").text
    assert "--title-font: var(--font-fraunces);" in look
    assert "--text-size: 18px;" in look
    assert "--label-scale: 1.4;" in look
    assert "--title-shadow: none;" in look
    # An empty name brings the config's title back.
    save(client, site_name="")
    assert '<a class="brand" href="/">Micelio</a>' in client.get("/projects").text


def test_visitors_see_the_look_but_cannot_change_it(make_site: SiteFactory) -> None:
    site: Site = make_site()
    html = site.client.get("/projects").text
    assert 'id="backdrop"' in html
    assert "/theme.css" in html
    response = site.client.post(
        "/appearance", data={"title_font": "righteous"}, follow_redirects=False
    )
    assert response.status_code == 401
    assert "--title-font: var(--font-shrikhand);" in site.client.get("/theme.css").text


def test_spanish_appearance_has_no_english_type_settings(tmp_path: Path) -> None:
    config = make_config(tmp_path, site={"language": "es"})
    with TestClient(create_app(config, environ={})) as client:
        html = client.get("/appearance").text
        for text in ("Nombre y letras", "Fuente de los títulos", "Nombres en los grafos", "Póster"):
            assert text in html
        for english in ("Names and lettering", "Title font", "Names on the graphs", "Poster<"):
            assert english not in html
        explore = client.get("/explore").text
        assert "Cómo leerlo" in explore
        assert "Ver todo" in explore
        assert "How to read it" not in explore


# -- the graph's code -------------------------------------------------------------------


def test_graph_pages_load_the_micelio_drawing() -> None:
    graph = (STATIC / "js" / "graph.js").read_text("utf-8")
    assert 'from "./draw.js"' in graph
    landing = (STATIC / "js" / "landing.js").read_text("utf-8")
    assert 'from "./draw.js"' in landing
    draw = (STATIC / "js" / "draw.js").read_text("utf-8")
    for name in ("painter", "hyphaPath", "cloud", "rampFilter", "seededRandom"):
        assert f"export function {name}(" in draw, name
