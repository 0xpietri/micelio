"""Load and validate ``mycelium.toml``.

Everything personal (names, categories, colors, folders) lives in the config file,
never in code. Secrets never live here: they come from environment variables.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONFIG_ENV = "MYCELIUM_CONFIG"
VAULT_ENV = "MYCELIUM_VAULT"

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

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_KEY = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


class ConfigError(ValueError):
    """The configuration file is missing or invalid."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SiteConfig(_Strict):
    title: str = "Mycelium"
    owner: str = ""
    tagline: str = "A living notebook of ideas"
    language: str = "en"
    timezone: str = "UTC"


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
    key: str
    label: str
    color: str
    species: str

    @field_validator("key")
    @classmethod
    def _key_format(cls, value: str) -> str:
        if not _KEY.match(value):
            raise ValueError("must be lowercase letters, digits or '-', starting with a letter")
        return value

    @field_validator("color")
    @classmethod
    def _hex_color(cls, value: str) -> str:
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
        Category(key="science", label="Science", color="#ff2fa0", species="fly-agaric"),
        Category(key="philosophy", label="Philosophy", color="#22d3ee", species="shaggy-inkcap"),
        Category(key="study", label="Study", color="#ff8a1f", species="morel"),
        Category(key="free", label="Free", color="#ffd23f", species="chanterelle"),
    ]


def _default_hidden() -> list[NoteType]:
    return ["journal", "source"]


class GraphConfig(_Strict):
    hide_by_default: list[NoteType] = Field(default_factory=_default_hidden)


class AuthConfig(_Strict):
    mode: Literal["local", "none"] = "local"


class Config(_Strict):
    site: SiteConfig = Field(default_factory=SiteConfig)
    vault: VaultConfig = Field(default_factory=VaultConfig)
    categories: list[Category] = Field(default_factory=_default_categories)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)

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

    ``path`` falls back to ``$MYCELIUM_CONFIG``; with neither, defaults are used.
    A relative ``vault.root`` is resolved against the config file's folder.
    ``vault_override`` (or ``$MYCELIUM_VAULT``) replaces ``vault.root``.
    """
    env_path = os.environ.get(CONFIG_ENV)
    config_path = path or (Path(env_path) if env_path else None)
    data: dict[str, object] = {}
    base = Path.cwd()
    if config_path is not None:
        try:
            data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"config file not found: {config_path}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{config_path}: invalid TOML: {exc}") from exc
        base = config_path.resolve().parent
    try:
        config = Config.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"invalid configuration: {exc}") from exc

    env_vault = os.environ.get(VAULT_ENV)
    root = vault_override or (Path(env_vault) if env_vault else config.vault.root)
    root = root.expanduser()
    if not root.is_absolute():
        root = base / root
    vault = config.vault.model_copy(update={"root": root.resolve()})
    return config.model_copy(update={"vault": vault})
