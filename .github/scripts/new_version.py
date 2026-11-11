"""Make a new version: number it and move CHANGELOG's Unreleased changes under it.

Run by .github/workflows/version.yml (``miceliodeploy edge`` starts it). It edits
``pyproject.toml`` and ``CHANGELOG.md`` and prints the new version; the workflow then
updates ``uv.lock``, commits, tags ``v<version>`` and builds the image and the package.

    python .github/scripts/new_version.py --last-tag v0.1.0 [--bump patch|minor|major]
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

REPO = "https://github.com/0xpietri/micelio"
_VERSION = re.compile(r'^(version = ")(\d+)\.(\d+)\.(\d+)(")$', re.M)
_UNRELEASED = re.compile(r"^## \[Unreleased\][ \t]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", re.M | re.S)
_UNRELEASED_LINK = re.compile(r"^\[Unreleased\]: .*$", re.M)


class NothingNewError(Exception):
    """CHANGELOG.md has no changes under Unreleased."""


def parse(version: str) -> tuple[int, int, int]:
    major, minor, patch = (int(part) for part in version.removeprefix("v").split("."))
    return major, minor, patch


def next_version(current: str, last_tag: str, bump: str = "patch") -> str:
    """``current`` itself while it was never tagged, else ``current`` bumped."""
    if not last_tag or parse(current) > parse(last_tag):
        return current
    major, minor, patch = parse(current)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def release_changelog(text: str, version: str, date: str, last_tag: str) -> str:
    """Unreleased's changes become the section of ``version``; the links follow."""
    found = _UNRELEASED.search(text)
    body = found.group(1).strip() if found else ""
    if found is None or not body:
        raise NothingNewError
    if re.search(rf"^## \[{re.escape(version)}\]", text, re.M):
        raise ValueError(f"CHANGELOG.md already has a section for {version}")
    section = f"## [Unreleased]\n\n## [{version}] - {date}\n\n{body}\n\n"
    text = text[: found.start()] + section + text[found.end() :]
    link = (
        f"[{version}]: {REPO}/compare/{last_tag}...v{version}"
        if last_tag
        else f"[{version}]: {REPO}/releases/tag/v{version}"
    )
    unreleased = f"[Unreleased]: {REPO}/compare/v{version}...HEAD"
    if _UNRELEASED_LINK.search(text):
        text = _UNRELEASED_LINK.sub(f"{unreleased}\n{link}", text, count=1)
    else:
        text = text.rstrip("\n") + f"\n\n{unreleased}\n{link}\n"
    return text


def set_version(pyproject: str, version: str) -> str:
    return _VERSION.sub(rf"\g<1>{version}\g<5>", pyproject, count=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--last-tag", default="", help="the newest v* tag, if any")
    parser.add_argument("--bump", choices=("patch", "minor", "major"), default="patch")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--date", default=dt.datetime.now(dt.UTC).date().isoformat())
    args = parser.parse_args(argv)
    pyproject = args.root / "pyproject.toml"
    changelog = args.root / "CHANGELOG.md"
    source = pyproject.read_text(encoding="utf-8")
    current = _VERSION.search(source)
    if current is None:
        print("pyproject.toml has no version", file=sys.stderr)
        return 1
    version = next_version(".".join(current.group(2, 3, 4)), args.last_tag, args.bump)
    try:
        notes = release_changelog(
            changelog.read_text(encoding="utf-8"), version, args.date, args.last_tag
        )
    except NothingNewError:
        print("Nothing new under Unreleased in CHANGELOG.md", file=sys.stderr)
        return 2
    changelog.write_text(notes, encoding="utf-8", newline="\n")
    pyproject.write_text(set_version(source, version), encoding="utf-8", newline="\n")
    print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
