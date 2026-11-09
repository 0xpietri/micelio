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
