"""How the owner dressed each project and source (§7c): a mushroom's species, color and
size; a source's mineral and color.

Chosen by clicking the node on its own page, kept in the data folder
(``site.sqlite3``, key ``node_looks``), never in the vault. Without a choice a project
is its category's species in its own shade, and a source is a diamond.
"""

from __future__ import annotations

import json
import re
from typing import TypedDict

from micelio.appearance import AppearanceStore
from micelio.config import SPECIES

MINERALS: tuple[str, ...] = ("diamond", "emerald", "amber", "quartz", "amethyst")
SIZE_MIN, SIZE_MAX = 0.6, 1.6
_KEY = "node_looks"
_COLOR = re.compile(r"#[0-9a-f]{6}")


class Look(TypedDict, total=False):
    color: str
    size: float
    species: str
    mineral: str


def clean_look(raw: object, kind: str) -> Look:
    """Only what ``kind`` (``project`` or ``source``) can have, each value checked."""
    look: Look = {}
    if not isinstance(raw, dict):
        return look
    color = raw.get("color")
    if isinstance(color, str) and _COLOR.fullmatch(color.lower()):
        look["color"] = color.lower()
    if kind == "project":
        species = raw.get("species")
        if isinstance(species, str) and species in SPECIES:
            look["species"] = species
        size = raw.get("size")
        if isinstance(size, int | float) and not isinstance(size, bool):
            look["size"] = round(min(SIZE_MAX, max(SIZE_MIN, float(size))), 2)
    elif kind == "source":
        mineral = raw.get("mineral")
        if isinstance(mineral, str) and mineral in MINERALS:
            look["mineral"] = mineral
    return look


class NodeLooks:
    """The looks, by note slug, next to the Appearance page's choices."""

    def __init__(self, store: AppearanceStore) -> None:
        self.store = store

    def all(self) -> dict[str, Look]:
        raw = self.store.read_setting(_KEY)
        if not isinstance(raw, dict):
            return {}
        return {
            slug: look
            for slug, value in raw.items()
            if isinstance(slug, str) and isinstance(value, dict)
            for look in [clean_look(value, "source" if "mineral" in value else "project")]
            if look
        }

    def get(self, slug: str) -> Look | None:
        return self.all().get(slug)

    def save(self, slug: str, look: Look) -> None:
        """Keep ``look`` for ``slug``; an empty one goes back to the defaults."""
        looks = dict(self.all())
        if look:
            looks[slug] = look
        else:
            looks.pop(slug, None)
        self.store.write_setting(_KEY, json.loads(json.dumps(looks)))
