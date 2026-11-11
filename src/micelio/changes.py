"""What changed: the project's CHANGELOG.md, shown in the footer and at ``/changes``.

The changelog travels inside the package (the wheel and the image), so a deployed site
can list what each build brought without reaching GitHub. The build's commit comes from
``MICELIO_REVISION``, which the image sets; it is empty when running from a checkout.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

import nh3
from markdown_it import MarkdownIt
from markupsafe import Markup

from micelio import __version__

_HEADING = re.compile(r"^## \[([^\]]+)\](?: - (\d{4}-\d{2}-\d{2}))?[ \t]*$", re.M)
_LINKS = re.compile(r"^\[[^\]]+\]: \S+[ \t]*$", re.M)
_TAGS = {"h3", "h4", "p", "ul", "ol", "li", "code", "strong", "em", "a"}


@dataclass(frozen=True)
class Release:
    """One section of the changelog: ``version`` is "Unreleased" for what main has."""

    version: str
    date: str | None
    html: Markup

    @property
    def unreleased(self) -> bool:
        return self.version.lower() == "unreleased"


def _source() -> str:
    """The packaged changelog, or the checkout's own when running from the source tree."""
    packaged = files("micelio").joinpath("CHANGELOG.md")
    if packaged.is_file():
        return packaged.read_text(encoding="utf-8")
    checkout = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
    return checkout.read_text(encoding="utf-8") if checkout.is_file() else ""


def parse(text: str) -> list[Release]:
    """The changelog's sections, newest first, each rendered to safe HTML."""
    text = _LINKS.sub("", text)
    md = MarkdownIt("commonmark")
    headings = list(_HEADING.finditer(text))
    releases = []
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[heading.end() : end].strip()
        html = nh3.clean(md.render(body), tags=_TAGS, attributes={"a": {"href"}}) if body else ""
        releases.append(Release(heading.group(1), heading.group(2), Markup(html)))  # noqa: S704
    return releases


class Changes:
    """The changelog and the build, read once when the site starts."""

    def __init__(self, text: str | None = None, environ: Mapping[str, str] | None = None) -> None:
        env = os.environ if environ is None else environ
        self.releases = parse(_source() if text is None else text)
        revision = env.get("MICELIO_REVISION", "").strip()
        self.build = revision[:7] if re.fullmatch(r"[0-9a-f]{7,40}", revision) else ""
        self.version = __version__

    @property
    def latest(self) -> Release | None:
        """What this build brought: main's unreleased changes, else the newest release."""
        for release in self.releases:
            if release.html:
                return release
        return None
