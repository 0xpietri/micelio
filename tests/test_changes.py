"""What changed: the changelog in the footer and at /changes (§7c)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from micelio import __version__
from micelio.changes import Changes, parse

from .test_graph import client_for
from .test_public import SiteFor
from .test_public import site_for as site_for  # the fixture

ROOT = Path(__file__).resolve().parents[1]

SAMPLE = """# Changelog

Intro text.

## [Unreleased]

## [0.2.0] - 2026-12-01

### Added

- A `footer` with **news**.
- <script>alert(1)</script>Safe.

## [0.1.0] - 2026-11-10

- First.

[0.2.0]: https://example.org/compare
"""


def test_sections_are_read_newest_first_and_made_safe() -> None:
    releases = parse(SAMPLE)
    assert [(r.version, r.date) for r in releases] == [
        ("Unreleased", None),
        ("0.2.0", "2026-12-01"),
        ("0.1.0", "2026-11-10"),
    ]
    unreleased, newest, _ = releases
    assert unreleased.unreleased
    assert not unreleased.html
    assert "<code>footer</code>" in newest.html
    assert "<strong>news</strong>" in newest.html
    assert "<h3>Added</h3>" in newest.html
    assert "<script" not in newest.html
    assert "example.org" not in "".join(r.html for r in releases)


def test_latest_is_mains_changes_or_else_the_newest_release() -> None:
    assert Changes(SAMPLE, {}).latest.version == "0.2.0"  # type: ignore[union-attr]
    ahead = SAMPLE.replace("## [Unreleased]\n", "## [Unreleased]\n\n- Coming.\n")
    latest = Changes(ahead, {}).latest
    assert latest is not None
    assert latest.unreleased
    assert "Coming." in latest.html
    assert Changes("", {}).latest is None


def test_the_build_is_a_commit_or_nothing() -> None:
    sha = "0123456789abcdef0123456789abcdef01234567"
    assert Changes(SAMPLE, {"MICELIO_REVISION": sha}).build == "0123456"
    assert Changes(SAMPLE, {"MICELIO_REVISION": "<b>x</b>"}).build == ""
    assert Changes(SAMPLE, {}).build == ""


def test_the_real_changelog_is_found_and_has_this_version() -> None:
    changes = Changes(environ={})
    assert __version__ in [r.version for r in changes.releases]
    assert changes.latest is not None


def test_the_changelog_ships_in_the_wheel_and_the_image() -> None:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        hatch = tomllib.load(fh)["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert hatch["force-include"] == {"CHANGELOG.md": "micelio/CHANGELOG.md"}
    assert "!CHANGELOG.md" in (ROOT / ".dockerignore").read_text("utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text("utf-8")
    assert "CHANGELOG.md" in dockerfile
    assert "MICELIO_REVISION=${REVISION}" in dockerfile
    workflow = (ROOT / ".github" / "workflows" / "image.yml").read_text("utf-8")
    assert workflow.count("REVISION=${{ github.sha }}") == 2


def test_every_page_has_the_footer_but_the_landing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MICELIO_REVISION", "abcdef1234567")
    client = client_for("es")
    for path in ("/projects", "/explore", "/journal", "/health"):
        html = client.get(path).text
        assert 'class="site-foot"' in html, path
        assert f"v{__version__}" in html, path
        assert "compilación abcdef1" in html, path  # in the tooltip
        assert 'class="foot-version"' in html, path
        assert 'href="/changes"' in html
    assert 'class="site-foot"' not in client.get("/").text
    page = client.get("/changes")
    assert page.status_code == 200
    assert "compilación abcdef1" in page.text
    assert f"<h2>{__version__}" in page.text


def test_visitors_can_read_what_changed(site_for: SiteFor) -> None:
    visitor = site_for().client  # not signed in
    page = visitor.get("/changes")
    assert page.status_code == 200
    assert "What&#39;s new" in page.text or "What's new" in page.text
    assert 'class="site-foot"' in visitor.get("/projects").text


def test_static_files_are_checked_again_by_their_content() -> None:
    # Every build has the same file times, so browsers must not cache by them (§10).
    client = client_for("en")
    first = client.get("/static/css/micelio.css")
    assert first.headers["cache-control"] == "no-cache"
    assert "last-modified" not in first.headers
    etag = first.headers["etag"]
    assert client.get("/static/css/graph.css").headers["etag"] != etag
    again = client.get("/static/css/micelio.css", headers={"If-None-Match": etag})
    assert again.status_code == 304
    stale = client.get("/static/css/micelio.css", headers={"If-None-Match": '"old"'})
    assert stale.status_code == 200


def test_no_page_asks_the_browser_to_clear_its_cache() -> None:
    # Chrome on Android can hang a page for minutes while it clears a big HTTP cache
    # for `Clear-Site-Data: "cache"`, so no answer may carry that header.
    client = client_for("en")
    client.cookies.clear()
    for path in ("/", "/projects", "/explore", "/static/css/micelio.css"):
        response = client.get(path)
        assert "clear-site-data" not in response.headers
        assert "micelio_static" not in response.headers.get("set-cookie", "")
