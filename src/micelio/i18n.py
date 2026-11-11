"""Interface strings, one flat TOML file per language in ``micelio/locales``.

Templates call ``t("login.title")``; nothing user-facing is written in a template.
A key missing from a language falls back to English, then to the key itself.
"""

from __future__ import annotations

import tomllib
from contextvars import ContextVar
from functools import cache
from importlib.resources import files
from typing import Protocol

DEFAULT_LANGUAGE = "en"

# The language a visitor chose with the flag in the header (a cookie, §5a). Set for each
# request by ``LanguageMiddleware``; without it, ``site.language`` from the config.
LANGUAGE_COOKIE = "micelio_lang"
_chosen: ContextVar[str | None] = ContextVar("micelio_language", default=None)


def active_language(default: str) -> str:
    """The language of the request being answered: the visitor's choice, else ``default``."""
    return _chosen.get() or default


class ActiveLanguage:
    """``{{ language }}`` in templates: renders as the request's language."""

    def __init__(self, default: str) -> None:
        self.default = default

    def __str__(self) -> str:
        return active_language(self.default)

    def __eq__(self, other: object) -> bool:
        return str(self) == other

    def __hash__(self) -> int:
        return hash(str(self))


def language_menu() -> list[dict[str, str]]:
    """Every interface language with its flag and its own name, for the header."""
    return [
        {
            "code": code,
            "flag": load_strings(code).get("site.flag", code.upper()),
            "name": load_strings(code).get("site.language_name", code),
        }
        for code in available_languages()
    ]


class LanguageMiddleware:
    """Reads the language cookie and makes it the request's language (pure ASGI, so the
    choice reaches every handler, thread or not)."""

    def __init__(self, app: object, languages: list[str]) -> None:
        self.app = app
        self.languages = frozenset(languages)

    async def __call__(self, scope: dict[str, object], receive: object, send: object) -> None:
        chosen = None
        if scope.get("type") == "http":
            for name, value in scope.get("headers", []):  # type: ignore[attr-defined]
                if name == b"cookie":
                    for part in value.decode("latin-1").split(";"):
                        key, _, raw = part.strip().partition("=")
                        if key == LANGUAGE_COOKIE and raw in self.languages:
                            chosen = raw
        token = _chosen.set(chosen)
        try:
            await self.app(scope, receive, send)  # type: ignore[operator]
        finally:
            _chosen.reset(token)


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
    folder = files("micelio") / "locales"
    return sorted(
        p.name.removesuffix(".toml") for p in folder.iterdir() if p.name.endswith(".toml")
    )


@cache
def load_strings(language: str) -> dict[str, str]:
    resource = files("micelio") / "locales" / f"{language}.toml"
    if not resource.is_file():
        return {}
    return _flatten(tomllib.loads(resource.read_text(encoding="utf-8")))


def translator(language: str) -> Translate:
    """``t()`` in the request's language (the visitor's choice), else ``language``."""
    fallback = load_strings(DEFAULT_LANGUAGE)

    def t(key: str, /, **values: object) -> str:
        strings = load_strings(active_language(language))
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
BROWSER_TABLES = (
    "graph",
    "type",
    "status",
    "category",
    "landing",
    "prompt",
    "species",
    "mineral",
    "said",
)


def browser_strings(language: str) -> dict[str, str]:
    """The strings served as ``/static/locales/<lang>.json``, English fallback included."""
    merged = {**load_strings(DEFAULT_LANGUAGE), **load_strings(language)}
    return {
        key: text for key, text in sorted(merged.items()) if key.split(".", 1)[0] in BROWSER_TABLES
    }
