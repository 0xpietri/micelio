"""Load and validate ``micelio.toml``.

Everything personal (names, categories, colors, folders) lives in the config file,
never in code. Secrets never live here: they come from environment variables.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from babel import Locale, UnknownLocaleError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONFIG_ENV = "MICELIO_CONFIG"
VAULT_ENV = "MICELIO_VAULT"
DATA_ENV = "MICELIO_DATA"

SPECIES: frozenset[str] = frozenset(
    {
        "fly-agaric",
        "shaggy-inkcap",
        "morel",
        "chanterelle",
        "liberty-caps",
        "coral",
        "parasol",
        "glowing-bonnets",
    }
)

NoteType = Literal["project", "note", "journal", "source"]
NOTE_TYPES: tuple[NoteType, ...] = ("project", "note", "journal", "source")
STATUSES: tuple[str, ...] = ("draft", "active", "paused", "closed")

PaletteName = Literal["psychedelic", "tokyo-night", "catppuccin", "rose-pine"]
PALETTE_NAMES: tuple[PaletteName, ...] = ("psychedelic", "tokyo-night", "catppuccin", "rose-pine")
SOIL_MIN, SOIL_MAX = 30, 70

TitleFont = Literal["shrikhand", "righteous", "bagel-fat-one", "fraunces"]
TITLE_FONTS: tuple[TitleFont, ...] = ("shrikhand", "righteous", "bagel-fat-one", "fraunces")
TextFont = Literal["system", "atkinson-hyperlegible", "literata", "space-grotesk"]
TEXT_FONTS: tuple[TextFont, ...] = ("system", "atkinson-hyperlegible", "literata", "space-grotesk")
TitleEffect = Literal["poster", "plain"]
TITLE_EFFECTS: tuple[TitleEffect, ...] = ("poster", "plain")
TITLE_SIZE_MIN, TITLE_SIZE_MAX = 70, 140  # percent
TEXT_SIZE_MIN, TEXT_SIZE_MAX = 14, 20  # px
LABEL_SIZE_MIN, LABEL_SIZE_MAX = 80, 150  # percent

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_KEY = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


class ConfigError(ValueError):
    """The configuration file is missing or invalid."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _pick(text: str | dict[str, str] | None, language: str) -> str | None:
    """One text for every language, or a table such as ``{ en = "...", es = "..." }``."""
    if isinstance(text, str):
        return text
    if text:
        return text.get(language) or text.get("en")
    return None


class SiteConfig(_Strict):
    title: str = "Micelio"
    owner: str = ""
    headline: str | dict[str, str] | None = None
    tagline: str | dict[str, str] | None = None

    def headline_for(self, language: str) -> str | None:
        """The landing's title from the config, if one is set."""
        return _pick(self.headline, language)

    def tagline_for(self, language: str) -> str | None:
        """The landing's tagline from the config; ``None`` uses the translated default."""
        return _pick(self.tagline, language)

    language: str = "en"
    timezone: str = "UTC"

    @field_validator("language")
    @classmethod
    def _known_language(cls, value: str) -> str:
        try:
            Locale.parse(value.replace("-", "_"))
        except (ValueError, UnknownLocaleError) as exc:
            raise ValueError(f"unknown language code {value!r}") from exc
        return value

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown time zone {value!r}, use a name like Europe/Madrid") from exc
        return value


class VaultConfig(_Strict):
    root: Path = Path("vault")
    projects: str = "projects"
    notes: str = "notes"
    journal: str = "journal"
    sources: str = "sources"

    def folder_for(self, note_type: NoteType) -> str:
        folders: dict[NoteType, str] = {
            "project": self.projects,
            "note": self.notes,
            "journal": self.journal,
            "source": self.sources,
        }
        return folders[note_type]


class Category(_Strict):
    """A project category.

    ``label`` is optional: without it the name comes from the interface language
    (``category.<key>`` in the locale files) or, failing that, from the key. It can be
    one name for every language or a table such as ``{ en = "Art", es = "Arte" }``.
    """

    key: str
    label: str | dict[str, str] | None = None
    color: str | None = None  # None: the palette's color for this position
    species: str

    def name(self, language: str, translated: str | None = None) -> str:
        """The name to show for ``language``; ``translated`` is the locale's name, if any."""
        return _pick(self.label, language) or translated or self.key.replace("-", " ").capitalize()

    @field_validator("key")
    @classmethod
    def _key_format(cls, value: str) -> str:
        if not _KEY.match(value):
            raise ValueError("must be lowercase letters, digits or '-', starting with a letter")
        return value

    @field_validator("color")
    @classmethod
    def _hex_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _HEX_COLOR.match(value):
            raise ValueError("must be a hex color like #ff2fa0")
        return value.lower()

    @field_validator("species")
    @classmethod
    def _known_species(cls, value: str) -> str:
        if value not in SPECIES:
            raise ValueError(f"unknown species; choose one of {', '.join(sorted(SPECIES))}")
        return value


def _default_categories() -> list[Category]:
    return [
        Category(key="science", species="fly-agaric"),
        Category(key="philosophy", species="shaggy-inkcap"),
        Category(key="study", species="morel"),
        Category(key="free", species="chanterelle"),
    ]


def _default_hidden() -> list[NoteType]:
    return ["journal", "source"]


class GraphConfig(_Strict):
    hide_by_default: list[NoteType] = Field(default_factory=_default_hidden)
    max_nodes: int = Field(default=400, ge=20, le=5000)


class TypographyConfig(_Strict):
    """Defaults for titles and text on every page (§7b). The Appearance page can
    override them."""

    title_font: TitleFont = "shrikhand"
    text_font: TextFont = "system"
    title_size: int = Field(default=100, ge=TITLE_SIZE_MIN, le=TITLE_SIZE_MAX)
    text_size: int = Field(default=16, ge=TEXT_SIZE_MIN, le=TEXT_SIZE_MAX)
    graph_labels: int = Field(default=100, ge=LABEL_SIZE_MIN, le=LABEL_SIZE_MAX)
    title_effect: TitleEffect = "poster"


class LandingConfig(_Strict):
    """Defaults for the landing (§7a, §7b). The Appearance page can override them."""

    palette: PaletteName = "psychedelic"
    soil: int = Field(default=52, ge=SOIL_MIN, le=SOIL_MAX)
    max_notes: int = Field(default=300, ge=10, le=5000)


class AuthConfig(_Strict):
    mode: Literal["local", "none"] = "local"
    session_hours: int = Field(default=12, ge=1, le=24 * 30)
    max_failures: int = Field(default=5, ge=1, le=100)
    lockout_minutes: int = Field(default=15, ge=1, le=24 * 60)


class DataConfig(_Strict):
    """Micelio's own small state: sign-in sessions and the Appearance page's choices
    (§7b). Never the vault. Safe to delete."""

    dir: Path = Path("data")


class Config(_Strict):
    site: SiteConfig = Field(default_factory=SiteConfig)
    vault: VaultConfig = Field(default_factory=VaultConfig)
    categories: list[Category] = Field(default_factory=_default_categories)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    landing: LandingConfig = Field(default_factory=LandingConfig)
    typography: TypographyConfig = Field(default_factory=TypographyConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    data: DataConfig = Field(default_factory=DataConfig)

    @model_validator(mode="after")
    def _unique_categories(self) -> Config:
        keys = [c.key for c in self.categories]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        if duplicates:
            raise ValueError(f"duplicate category keys: {', '.join(duplicates)}")
        if not self.categories:
            raise ValueError("at least one category is required")
        return self

    def category(self, key: str | None) -> Category | None:
        return next((c for c in self.categories if c.key == key), None)


def load_config(path: Path | None = None, *, vault_override: Path | None = None) -> Config:
    """Read the config file, resolve the vault root and validate everything.

    ``path`` falls back to ``$MICELIO_CONFIG``; with neither, defaults are used.
    A relative ``vault.root`` is resolved against the config file's folder.
    ``vault_override`` (or ``$MICELIO_VAULT``) replaces ``vault.root``.
    """
    env_path = os.environ.get(CONFIG_ENV)
    config_path = path or (Path(env_path) if env_path else None)
    raw: dict[str, object] = {}
    base = Path.cwd()
    if config_path is not None:
        try:
            raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"config file not found: {config_path}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{config_path}: invalid TOML: {exc}") from exc
        base = config_path.resolve().parent
    try:
        config = Config.model_validate(raw)
    except ValueError as exc:
        raise ConfigError(f"invalid configuration: {exc}") from exc

    env_vault = os.environ.get(VAULT_ENV)
    root = vault_override or (Path(env_vault) if env_vault else config.vault.root)
    vault = config.vault.model_copy(update={"root": _absolute(root, base)})
    env_data = os.environ.get(DATA_ENV)
    data_dir = Path(env_data) if env_data else config.data.dir
    data = config.data.model_copy(update={"dir": _absolute(data_dir, base)})
    return config.model_copy(update={"vault": vault, "data": data})


def _absolute(path: Path, base: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()
