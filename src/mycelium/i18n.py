"""Interface strings, one flat TOML file per language in ``mycelium/locales``.

Templates call ``t("login.title")``; nothing user-facing is written in a template.
A key missing from a language falls back to English, then to the key itself.
"""

from __future__ import annotations

import tomllib
from functools import cache
from importlib.resources import files
from typing import Protocol

DEFAULT_LANGUAGE = "en"


class Translate(Protocol):
    def __call__(self, key: str, /, **values: object) -> str: ...


def _flatten(table: dict[str, object], prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in table.items():
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{full}."))
        else:
            flat[full] = str(value)
    return flat


def available_languages() -> list[str]:
    folder = files("mycelium") / "locales"
    return sorted(
        p.name.removesuffix(".toml") for p in folder.iterdir() if p.name.endswith(".toml")
    )


@cache
def load_strings(language: str) -> dict[str, str]:
    resource = files("mycelium") / "locales" / f"{language}.toml"
    if not resource.is_file():
        return {}
    return _flatten(tomllib.loads(resource.read_text(encoding="utf-8")))


def translator(language: str) -> Translate:
    strings = load_strings(language)
    fallback = load_strings(DEFAULT_LANGUAGE)

    def t(key: str, /, **values: object) -> str:
        text = strings.get(key) or fallback.get(key) or key
        return text.format(**values) if values else text

    return t


def category_names(language: str) -> dict[str, str]:
    """Translated names of the default categories (``category.<key>``), English fallback."""
    names = {
        key.removeprefix("category."): text
        for key, text in load_strings(DEFAULT_LANGUAGE).items()
        if key.startswith("category.")
    }
    names.update(
        (key.removeprefix("category."), text)
        for key, text in load_strings(language).items()
        if key.startswith("category.")
    )
    return names


# Locale tables the browser needs (graph tooltips, legends, search feedback).
BROWSER_TABLES = ("graph", "type", "status", "category")


def browser_strings(language: str) -> dict[str, str]:
    """The strings served as ``/static/locales/<lang>.json``, English fallback included."""
    merged = {**load_strings(DEFAULT_LANGUAGE), **load_strings(language)}
    return {
        key: text for key, text in sorted(merged.items()) if key.split(".", 1)[0] in BROWSER_TABLES
    }
