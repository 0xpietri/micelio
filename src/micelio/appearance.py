"""The landing's look (§7b): palettes, the background image and the saved choices.

The choices made on ``/appearance`` live in the data folder (``site.sqlite3`` and
``backgrounds/``), never in the vault. Without them the defaults of ``micelio.toml``
apply, so deleting the data folder only brings the defaults back.
"""

from __future__ import annotations

import json
import sqlite3
import struct
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

from micelio.config import (
    LABEL_SIZE_MAX,
    LABEL_SIZE_MIN,
    PALETTE_NAMES,
    SOIL_MAX,
    SOIL_MIN,
    TEXT_FONTS,
    TEXT_SIZE_MAX,
    TEXT_SIZE_MIN,
    TITLE_EFFECTS,
    TITLE_FONTS,
    TITLE_SIZE_MAX,
    TITLE_SIZE_MIN,
    Config,
    PaletteName,
    TextFont,
    TitleEffect,
    TitleFont,
)

# The chalkboard that closes a concept (`> [!takeaway]`): its color and the hand it is
# written in. The chalk's color is not a choice: it follows the palette (micelio.css).
BoardColor = Literal["black", "green", "white"]
BOARD_COLORS: tuple[BoardColor, ...] = ("black", "green", "white")
BoardFont = Literal["caveat", "patrick-hand", "gochi-hand"]
BOARD_FONTS: tuple[BoardFont, ...] = ("caveat", "patrick-hand", "gochi-hand")

SITE_DB = "site.sqlite3"
BACKGROUNDS = "backgrounds"
BUILTIN_BACKGROUND = "img/psychedelic-dusk.webp"  # under /static
BUILTIN_SOIL = 52

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MIN_WIDTH, MIN_HEIGHT = 1200, 800
MAX_AVATAR_BYTES = 2 * 1024 * 1024
MIN_AVATAR_SIDE = 64
AVATARS = "avatar"
MAX_TEXT = 120
MAX_NAME = 40

ImageType = Literal["png", "jpeg", "webp"]
MEDIA_TYPES: dict[ImageType, str] = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}


@dataclass(frozen=True, slots=True)
class Palette:
    """Colors of one template. ``cats`` and ``spare`` colour categories by position;
    ``ramp`` (dark to light) recolors the background, ``None`` keeps it as painted."""

    key: PaletteName
    name: str
    cats: tuple[str, str, str, str]
    spare: tuple[str, str, str, str]
    ink: str
    stem: str
    thread: str
    spore: str
    crystals: tuple[str, str]
    sun: str
    accent: str
    button: str
    button_alt: str
    ramp: tuple[str, ...] | None
    swatch: tuple[str, ...]

    def slot(self, position: int) -> str:
        slots = (*self.cats, *self.spare)
        return slots[position % len(slots)]

    def to_json(self) -> dict[str, object]:
        data = asdict(self)
        data["ramp"] = list(self.ramp) if self.ramp else None
        return data


PALETTES: dict[PaletteName, Palette] = {
    "psychedelic": Palette(
        key="psychedelic",
        name="Psychedelic",
        cats=("#ff2fa0", "#22d3ee", "#ff8a1f", "#ffd23f"),
        spare=("#9b5cff", "#39ff6a", "#3b5bff", "#c6ff3a"),
        ink="#12051f",
        stem="#fff1d0",
        thread="#ffffff",
        spore="#ffd23f",
        crystals=("#22d3ee", "#ffd23f"),
        sun="#ffd23f",
        accent="#ff2fa0",
        button="#c6ff3a",
        button_alt="#22d3ee",
        ramp=None,
        swatch=("#12051f", "#9b5cff", "#ff2fa0", "#ff8a1f", "#ffd23f", "#22d3ee"),
    ),
    # https://github.com/folke/tokyonight.nvim (MIT)
    "tokyo-night": Palette(
        key="tokyo-night",
        name="Tokyo Night",
        cats=("#bb9af7", "#7dcfff", "#ff9e64", "#9ece6a"),
        spare=("#f7768e", "#73daca", "#e0af68", "#2ac3de"),
        ink="#16161e",
        stem="#c0caf5",
        thread="#c0caf5",
        spore="#e0af68",
        crystals=("#7dcfff", "#e0af68"),
        sun="#7aa2f7",
        accent="#bb9af7",
        button="#9ece6a",
        button_alt="#7dcfff",
        ramp=(
            "#16161e",
            "#1f2335",
            "#2f3b6b",
            "#3d59a1",
            "#7aa2f7",
            "#bb9af7",
            "#7dcfff",
            "#c0caf5",
        ),
        swatch=("#1a1b26", "#3d59a1", "#7aa2f7", "#bb9af7", "#7dcfff", "#ff9e64"),
    ),
    # https://github.com/catppuccin/catppuccin (MIT), the Mocha flavour
    "catppuccin": Palette(
        key="catppuccin",
        name="Catppuccin Mocha",
        cats=("#f38ba8", "#89dceb", "#fab387", "#a6e3a1"),
        spare=("#cba6f7", "#94e2d5", "#f9e2af", "#89b4fa"),
        ink="#11111b",
        stem="#f5e0dc",
        thread="#cdd6f4",
        spore="#f9e2af",
        crystals=("#89dceb", "#f9e2af"),
        sun="#f5c2e7",
        accent="#cba6f7",
        button="#a6e3a1",
        button_alt="#89b4fa",
        ramp=(
            "#11111b",
            "#1e1e2e",
            "#313244",
            "#585b70",
            "#89b4fa",
            "#cba6f7",
            "#f5c2e7",
            "#f9e2af",
        ),
        swatch=("#1e1e2e", "#585b70", "#89b4fa", "#cba6f7", "#f5c2e7", "#fab387"),
    ),
    # https://github.com/rose-pine/rose-pine-theme (MIT)
    "rose-pine": Palette(
        key="rose-pine",
        name="Rosé Pine",
        cats=("#eb6f92", "#9ccfd8", "#f6c177", "#c4a7e7"),
        spare=("#ebbcba", "#31748f", "#f6c177", "#9ccfd8"),
        ink="#191724",
        stem="#e0def4",
        thread="#e0def4",
        spore="#f6c177",
        crystals=("#9ccfd8", "#f6c177"),
        sun="#ebbcba",
        accent="#eb6f92",
        button="#f6c177",
        button_alt="#9ccfd8",
        ramp=(
            "#191724",
            "#1f1d2e",
            "#26233a",
            "#31748f",
            "#9ccfd8",
            "#c4a7e7",
            "#ebbcba",
            "#f6c177",
        ),
        swatch=("#191724", "#31748f", "#9ccfd8", "#c4a7e7", "#eb6f92", "#f6c177"),
    ),
}


@dataclass(frozen=True, slots=True)
class Appearance:
    """What the landing looks like right now: the saved choices over the config."""

    palette: PaletteName = "psychedelic"
    background: Literal["builtin", "own"] = "builtin"
    own_type: ImageType | None = None  # set while an uploaded image exists
    own_version: int = 0  # bumps on each upload, for cache busting
    recolor: bool | None = None  # None: on for the included painting, off for an upload
    soil: int = BUILTIN_SOIL
    headline: str = ""
    tagline: str | None = None  # None: the default; "" once saved empty: no tagline
    site_name: str = ""  # empty: the config's site.title
    title_font: TitleFont = "shrikhand"
    text_font: TextFont = "system"
    title_size: int = 100  # percent
    text_size: int = 16  # px
    graph_labels: int = 100  # percent
    title_effect: TitleEffect = "poster"
    board_color: BoardColor = "green"
    board_font: BoardFont = "caveat"
    said_font: BoardFont = "patrick-hand"  # the hand of the owner's words in `> [!said]`
    avatar_type: ImageType | None = None  # the owner's picture, set while one exists
    avatar_version: int = 0  # bumps on each upload, for cache busting

    @property
    def uses_own(self) -> bool:
        return self.background == "own" and self.own_type is not None

    @property
    def recolors(self) -> bool:
        if self.recolor is not None:
            return self.recolor
        return not self.uses_own

    @property
    def colors(self) -> Palette:
        return PALETTES[self.palette]


def ramp_tables(ramp: tuple[str, ...] | list[str]) -> tuple[str, str, str]:
    """The red, green and blue ``tableValues`` of the SVG filter that maps the background's
    brightness onto ``ramp`` (dark to light colors, ``#rrggbb``). The same table as
    ``rampFilter`` in static/js/draw.js, so the page paints recolored from the start."""
    stops = [[int(c[i : i + 2], 16) / 255 for i in (1, 3, 5)] for c in ramp]
    n = len(stops) - 1
    steps = 24
    table: tuple[list[str], list[str], list[str]] = ([], [], [])
    for i in range(steps + 1):
        t = (i / steps) ** 0.8 * n
        j = min(int(t), n - 1)
        f = t - j
        for ch in range(3):
            table[ch].append(f"{stops[j][ch] + (stops[j + 1][ch] - stops[j][ch]) * f:.3f}")
    return (" ".join(table[0]), " ".join(table[1]), " ".join(table[2]))


def palette_named(value: object, fallback: PaletteName) -> PaletteName:
    """``value`` if it names a palette, else ``fallback``."""
    return next((k for k in PALETTE_NAMES if k == value), fallback)


def in_range(value: object, low: int, high: int, fallback: int) -> int:
    """``value`` if it is a whole number from ``low`` to ``high``, else ``fallback``."""
    if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high:
        return value
    return fallback


def title_font_named(value: object, fallback: TitleFont) -> TitleFont:
    return next((k for k in TITLE_FONTS if k == value), fallback)


def text_font_named(value: object, fallback: TextFont) -> TextFont:
    return next((k for k in TEXT_FONTS if k == value), fallback)


def title_effect_named(value: object, fallback: TitleEffect) -> TitleEffect:
    return next((k for k in TITLE_EFFECTS if k == value), fallback)


def board_color_named(value: object, fallback: BoardColor) -> BoardColor:
    return next((k for k in BOARD_COLORS if k == value), fallback)


def board_font_named(value: object, fallback: BoardFont) -> BoardFont:
    return next((k for k in BOARD_FONTS if k == value), fallback)


def category_colors(config: Config, palette: Palette) -> dict[str, str]:
    """Each category's color: its own ``color`` if set, else the palette's for its place."""
    return {c.key: c.color or palette.slot(i) for i, c in enumerate(config.categories)}


# -- reading image headers ----------------------------------------------------------


class ImageError(ValueError):
    """The upload is not an image we accept. ``code`` names the reason for the page."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def image_info(data: bytes) -> tuple[ImageType, int, int]:
    """Type, width and height from the file's own bytes (never its name).

    Raises ``ImageError("type")`` when it is not PNG, JPEG or WebP, or the header is broken.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height
    if data.startswith(b"\xff\xd8"):
        return ("jpeg", *_jpeg_size(data))
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ("webp", *_webp_size(data))
    raise ImageError("type")


def _jpeg_size(data: bytes) -> tuple[int, int]:
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            raise ImageError("type")
        marker = data[i + 1]
        if marker == 0xFF:  # padding
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        (length,) = struct.unpack(">H", data[i + 2 : i + 4])
        # SOF0..SOF15 carry the size, except DHT (C4), JPG (C8) and DAC (CC).
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        i += 2 + length
    raise ImageError("type")


def _webp_size(data: bytes) -> tuple[int, int]:
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ImageError("type")


def check_upload(data: bytes) -> ImageType:
    """Accept a background image or raise ``ImageError`` with ``empty``, ``size``,
    ``type`` or ``small``."""
    if not data:
        raise ImageError("empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageError("size")
    kind, width, height = image_info(data)
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        raise ImageError("small")
    return kind


def check_avatar(data: bytes) -> ImageType:
    """Accept a profile picture or raise ``ImageError`` with ``empty``, ``avatar_size``,
    ``type`` or ``avatar_small``."""
    if not data:
        raise ImageError("empty")
    if len(data) > MAX_AVATAR_BYTES:
        raise ImageError("avatar_size")
    kind, width, height = image_info(data)
    if min(width, height) < MIN_AVATAR_SIDE:
        raise ImageError("avatar_small")
    return kind


# -- the store ------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
_KEY = "appearance"


def clean_text(value: str) -> str:
    """One line, no control characters, at most ``MAX_TEXT`` characters."""
    text = "".join(ch if ch.isprintable() else " " for ch in value)
    return " ".join(text.split())[:MAX_TEXT]


class AppearanceStore:
    """The Appearance page's choices, in ``data/site.sqlite3`` and ``data/backgrounds/``."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.folder = config.data.dir
        self._lock = threading.Lock()
        self._db: sqlite3.Connection | None = None

    def _conn(self) -> sqlite3.Connection:
        # Opened on first use, so a site nobody customizes never creates the file.
        if self._db is None:
            self.folder.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(
                self.folder / SITE_DB, check_same_thread=False, isolation_level=None
            )
            self._db.executescript(_SCHEMA)
        return self._db

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None

    def _saved(self) -> dict[str, object]:
        if self._db is None and not (self.folder / SITE_DB).is_file():
            return {}
        with self._lock:
            row = (
                self._conn().execute("SELECT value FROM settings WHERE key = ?", (_KEY,)).fetchone()
            )
        if row is None:
            return {}
        try:
            loaded = json.loads(row[0])
        except ValueError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def current(self) -> Appearance:
        defaults = self.config.landing
        type_defaults = self.config.typography
        saved = self._saved()
        palette = palette_named(saved.get("palette"), defaults.palette)
        own_type = next((k for k in MEDIA_TYPES if k == saved.get("own_type")), None)
        if own_type is not None and not self.own_path(own_type).is_file():
            own_type = None
        background: Literal["builtin", "own"] = (
            "own" if saved.get("background") == "own" and own_type else "builtin"
        )
        recolor = saved.get("recolor")
        soil = saved.get("soil", defaults.soil)
        version = saved.get("own_version", 0)
        avatar_type = next((k for k in MEDIA_TYPES if k == saved.get("avatar_type")), None)
        if avatar_type is not None and not self.avatar_path(avatar_type).is_file():
            avatar_type = None
        avatar_version = saved.get("avatar_version", 0)
        return Appearance(
            palette=palette,
            background=background,
            own_type=own_type,
            own_version=version if isinstance(version, int) else 0,
            recolor=recolor if isinstance(recolor, bool) else None,
            soil=soil if isinstance(soil, int) and SOIL_MIN <= soil <= SOIL_MAX else defaults.soil,
            headline=clean_text(str(saved.get("headline", ""))),
            tagline=None if saved.get("tagline") is None else clean_text(str(saved["tagline"])),
            site_name=clean_text(str(saved.get("site_name", "")))[:MAX_NAME],
            title_font=title_font_named(saved.get("title_font"), type_defaults.title_font),
            text_font=text_font_named(saved.get("text_font"), type_defaults.text_font),
            title_size=in_range(
                saved.get("title_size"), TITLE_SIZE_MIN, TITLE_SIZE_MAX, type_defaults.title_size
            ),
            text_size=in_range(
                saved.get("text_size"), TEXT_SIZE_MIN, TEXT_SIZE_MAX, type_defaults.text_size
            ),
            graph_labels=in_range(
                saved.get("graph_labels"),
                LABEL_SIZE_MIN,
                LABEL_SIZE_MAX,
                type_defaults.graph_labels,
            ),
            title_effect=title_effect_named(saved.get("title_effect"), type_defaults.title_effect),
            board_color=board_color_named(saved.get("board_color"), "green"),
            board_font=board_font_named(saved.get("board_font"), "caveat"),
            said_font=board_font_named(saved.get("said_font"), "patrick-hand"),
            avatar_type=avatar_type,
            avatar_version=avatar_version if isinstance(avatar_version, int) else 0,
        )

    def save(self, appearance: Appearance) -> None:
        data = asdict(appearance)
        with self._lock:
            self._conn().execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (_KEY, json.dumps(data)),
            )

    # -- other settings in the same table (looks.py) -----------------------------

    def read_setting(self, key: str) -> object:
        if self._db is None and not (self.folder / SITE_DB).is_file():
            return None
        with self._lock:
            row = (
                self._conn().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            )
        if row is None:
            return None
        try:
            value: object = json.loads(row[0])
        except ValueError:
            return None
        return value

    def write_setting(self, key: str, value: object) -> None:
        with self._lock:
            self._conn().execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )

    # -- the uploaded background --------------------------------------------------

    def own_path(self, kind: str) -> Path:
        return self.folder / BACKGROUNDS / f"background.{kind}"

    def store_background(self, data: bytes) -> Appearance:
        """Validate and keep ``data`` as the background, replacing any earlier upload."""
        kind = check_upload(data)
        folder = self.folder / BACKGROUNDS
        folder.mkdir(parents=True, exist_ok=True)
        target = self.own_path(kind)
        partial = target.with_suffix(".part")
        partial.write_bytes(data)
        partial.replace(target)
        for other in MEDIA_TYPES:
            if other != kind:
                self.own_path(other).unlink(missing_ok=True)
        now = self.current()
        updated = replace(
            now,
            background="own",
            own_type=kind,
            own_version=now.own_version + 1,
            recolor=None,
        )
        self.save(updated)
        return updated

    def remove_background(self) -> Appearance:
        for kind in MEDIA_TYPES:
            self.own_path(kind).unlink(missing_ok=True)
        updated = replace(self.current(), background="builtin", own_type=None, recolor=None)
        self.save(updated)
        return updated

    # -- the owner's profile picture (the speaker of `> [!said]` callouts) -----------

    def avatar_path(self, kind: str) -> Path:
        return self.folder / AVATARS / f"avatar.{kind}"

    def store_avatar(self, data: bytes) -> Appearance:
        """Validate and keep ``data`` as the profile picture, replacing any earlier one."""
        kind = check_avatar(data)
        folder = self.folder / AVATARS
        folder.mkdir(parents=True, exist_ok=True)
        target = self.avatar_path(kind)
        partial = target.with_suffix(".part")
        partial.write_bytes(data)
        partial.replace(target)
        for other in MEDIA_TYPES:
            if other != kind:
                self.avatar_path(other).unlink(missing_ok=True)
        now = self.current()
        updated = replace(now, avatar_type=kind, avatar_version=now.avatar_version + 1)
        self.save(updated)
        return updated

    def remove_avatar(self) -> Appearance:
        for kind in MEDIA_TYPES:
            self.avatar_path(kind).unlink(missing_ok=True)
        updated = replace(self.current(), avatar_type=None)
        self.save(updated)
        return updated
