"""Making a new version (.github/scripts/new_version.py, run by version.yml)."""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "new_version.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("new_version", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["new_version"] = module
    spec.loader.exec_module(module)
    return module


nv = load()


def test_the_number_grows_only_after_a_published_version() -> None:
    assert nv.next_version("0.1.0", "v0.1.0") == "0.1.1"
    assert nv.next_version("0.1.0", "v0.1.0", "minor") == "0.2.0"
    assert nv.next_version("0.9.3", "v0.9.3", "major") == "1.0.0"
    assert nv.next_version("0.2.0", "v0.1.4") == "0.2.0"  # numbered by hand, never tagged
    assert nv.next_version("0.1.0", "") == "0.1.0"


CHANGELOG = """# Changelog

## [Unreleased]

### Added

- Something new.

## [0.1.0] - 2026-11-10

- First.

[Unreleased]: https://github.com/0xpietri/micelio/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/0xpietri/micelio/releases/tag/v0.1.0
"""


def test_unreleased_changes_move_under_the_new_version() -> None:
    text = nv.release_changelog(CHANGELOG, "0.1.1", "2026-11-12", "v0.1.0")
    assert (
        "## [Unreleased]\n\n## [0.1.1] - 2026-11-12\n\n### Added\n\n- Something new.\n\n## [0.1.0]"
        in text
    )
    assert "[Unreleased]: https://github.com/0xpietri/micelio/compare/v0.1.1...HEAD" in text
    assert "[0.1.1]: https://github.com/0xpietri/micelio/compare/v0.1.0...v0.1.1" in text
    assert text.count("[0.1.0]: ") == 1
    with pytest.raises(nv.NothingNewError):  # nothing is left under Unreleased
        nv.release_changelog(text, "0.1.2", "2026-11-13", "v0.1.1")


def test_the_whole_run_on_a_copy_of_the_repository(tmp_path: Path) -> None:
    for name in ("pyproject.toml", "CHANGELOG.md"):
        shutil.copy(ROOT / name, tmp_path / name)
    version = re.search(r'^version = "(.+)"$', (ROOT / "pyproject.toml").read_text("utf-8"), re.M)
    assert version is not None
    last = f"v{version.group(1)}"
    assert nv.main(["--root", str(tmp_path), "--last-tag", last, "--date", "2030-01-02"]) in (0, 2)
    changelog = (tmp_path / "CHANGELOG.md").read_text("utf-8")
    pyproject = (tmp_path / "pyproject.toml").read_text("utf-8")
    new = nv.next_version(version.group(1), last)
    if f'version = "{new}"' in pyproject:  # there was something new to release
        assert f"## [{new}] - 2030-01-02" in changelog
    else:
        assert changelog == (ROOT / "CHANGELOG.md").read_text("utf-8")


def test_the_workflow_starts_the_builds_on_the_new_tag() -> None:
    workflow = (ROOT / ".github" / "workflows" / "version.yml").read_text("utf-8")
    assert "python3 .github/scripts/new_version.py" in workflow
    assert 'gh workflow run image.yml --ref "v$VERSION"' in workflow
    assert 'gh workflow run release.yml --ref "v$VERSION"' in workflow
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text("utf-8")
    assert "workflow_dispatch:" in release
    image = (ROOT / ".github" / "workflows" / "image.yml").read_text("utf-8")
    assert '"$GITHUB_REF" != refs/tags/v*' in image
