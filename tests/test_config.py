from __future__ import annotations

from pathlib import Path

import pytest

from mycelium.config import ConfigError, load_config


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_without_a_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config.site.title == "Mycelium"
    assert [c.key for c in config.categories] == ["science", "philosophy", "study", "free"]
    assert config.vault.root == (tmp_path / "vault").resolve()
    assert config.auth.mode == "local"


def test_relative_root_resolves_against_the_config_folder(tmp_path: Path) -> None:
    cfg = write(tmp_path / "mycelium.toml", '[vault]\nroot = "notes"\n')
    assert load_config(cfg).vault.root == (tmp_path / "notes").resolve()


def test_vault_override_and_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = write(tmp_path / "mycelium.toml", '[vault]\nroot = "notes"\n')
    monkeypatch.setenv("MYCELIUM_VAULT", str(tmp_path / "from-env"))
    assert load_config(cfg).vault.root == (tmp_path / "from-env").resolve()
    other = tmp_path / "flag"
    assert load_config(cfg, vault_override=other).vault.root == other.resolve()


def test_config_path_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = write(tmp_path / "m.toml", '[site]\nowner = "Ada"\n')
    monkeypatch.setenv("MYCELIUM_CONFIG", str(cfg))
    assert load_config().site.owner == "Ada"


def test_custom_categories_and_lowercased_color(tmp_path: Path) -> None:
    cfg = write(
        tmp_path / "m.toml",
        '[[categories]]\nkey = "art"\nlabel = "Art"\ncolor = "#AABBCC"\nspecies = "coral"\n',
    )
    config = load_config(cfg)
    assert [c.key for c in config.categories] == ["art"]
    art = config.category("art")
    assert art is not None
    assert art.color == "#aabbcc"
    assert config.category("science") is None
    assert config.category(None) is None
    assert art.name("es") == "Art"


def test_category_names() -> None:
    from mycelium.config import Category

    plain = Category(key="deep-sea", color="#000000", species="morel")
    assert plain.name("es") == "Deep sea"
    assert plain.name("es", "Mar profundo") == "Mar profundo"
    both = Category(key="art", label={"en": "Art", "es": "Arte"}, color="#000000", species="morel")
    assert both.name("es") == "Arte"
    assert both.name("fr") == "Art"
    only_es = Category(key="art", label={"es": "Arte"}, color="#000000", species="morel")
    assert only_es.name("fr", "Artes") == "Artes"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[site\n", "invalid TOML"),
        ("[site]\nnope = 1\n", "nope"),
        (
            '[[categories]]\nkey = "Bad Key"\nlabel = "x"\ncolor = "#000000"\nspecies = "morel"\n',
            "lowercase",
        ),
        (
            '[[categories]]\nkey = "a"\nlabel = "x"\ncolor = "red"\nspecies = "morel"\n',
            "hex color",
        ),
        (
            '[[categories]]\nkey = "a"\nlabel = "x"\ncolor = "#000000"\nspecies = "truffle"\n',
            "unknown species",
        ),
        (
            '[[categories]]\nkey = "a"\nlabel = "x"\ncolor = "#000000"\nspecies = "morel"\n'
            '[[categories]]\nkey = "a"\nlabel = "y"\ncolor = "#111111"\nspecies = "coral"\n',
            "duplicate category keys: a",
        ),
        ("categories = []\n", "at least one category"),
        ('[auth]\nmode = "oauth"\n', "mode"),
        ('[graph]\nhide_by_default = ["diary"]\n', "hide_by_default"),
        ('[site]\ntimezone = "Mars/Olympus"\n', "unknown time zone"),
        ('[site]\nlanguage = "zz-not"\n', "unknown language"),
    ],
)
def test_invalid_configs_raise_config_error(tmp_path: Path, text: str, message: str) -> None:
    cfg = write(tmp_path / "m.toml", text)
    with pytest.raises(ConfigError, match=message):
        load_config(cfg)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.toml")


def test_example_config_is_valid() -> None:
    example = Path(__file__).resolve().parents[1] / "mycelium.example.toml"
    config = load_config(example)
    assert config.site.owner
    assert len(config.categories) == 4
