"""The scenes that ship with Micelio (§7b): painted backgrounds, each with its soil line
and the mushrooms drawn on it.

A scene is a template: choosing it on the Appearance page sets the background, where
the ground starts and, unless the owner picks otherwise, the style of every mushroom.
The paintings and the mushroom sheets were made once with an image model and ship as
static files under ``static/img``; nothing is generated at run time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# How mushrooms look: ``drawn`` is the procedural SVG of draw.js (recolored by the
# palette); the others are illustrated sheets, one picture per species, under
# ``static/img/mushrooms/<style>/<species>.webp``.
MushroomStyle = Literal["drawn", "neon", "brush", "blacklight"]
MUSHROOM_STYLES: tuple[MushroomStyle, ...] = ("drawn", "neon", "brush", "blacklight")


@dataclass(frozen=True, slots=True)
class Scene:
    key: str
    file: str  # under /static
    soil: int  # percent of the image's height where the ground starts
    mushrooms: MushroomStyle
    recolor: bool  # whether the palette recolors it unless the owner says otherwise

    @property
    def url(self) -> str:
        return f"/static/{self.file}"

    @property
    def thumb(self) -> str:
        if self.key == "dusk":
            return "/static/img/scenes/dusk-thumb.webp"
        return f"/static/img/scenes/{self.key}-thumb.webp"


def _painted(key: str, soil: int, mushrooms: MushroomStyle) -> Scene:
    return Scene(key, f"img/scenes/{key}.webp", soil, mushrooms, recolor=False)


SCENES: dict[str, Scene] = {
    s.key: s
    for s in (
        _painted("blacklight-planet", 52, "blacklight"),
        _painted("blacklight-moons", 52, "blacklight"),
        _painted("blacklight-nebula", 50, "blacklight"),
        _painted("blacklight-blue", 51, "blacklight"),
        _painted("neon-moon", 53, "neon"),
        _painted("neon-sun", 53, "neon"),
        _painted("neon-dusk", 53, "neon"),
        _painted("brush-night", 53, "brush"),
        _painted("brush-hills", 52, "brush"),
        # The first painting (§7a): drawn mushrooms, recolored by the palette.
        Scene("dusk", "img/psychedelic-dusk.webp", 52, "drawn", recolor=True),
    )
}
SCENE_NAMES: tuple[str, ...] = tuple(SCENES)
DEFAULT_SCENE = "blacklight-planet"


def scene_named(value: object, fallback: str) -> str:
    """``value`` if it names a scene, else ``fallback``."""
    return value if isinstance(value, str) and value in SCENES else fallback


def mushroom_style_named(value: object) -> MushroomStyle | None:
    """``value`` if it names a mushroom style, else ``None`` (follow the scene)."""
    return next((k for k in MUSHROOM_STYLES if k == value), None)
