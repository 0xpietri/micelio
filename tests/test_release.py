"""The release files agree with each other: version, changelog, image and demo."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from micelio import DISTRIBUTION, __version__
from micelio.config import load_config

from .conftest import EXAMPLE_VAULT

ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def test_installed_version_is_the_project_version() -> None:
    project = _pyproject()["project"]
    assert isinstance(project, dict)
    assert project["name"] == DISTRIBUTION
    assert __version__ == project["version"]


def test_the_command_runs_the_cli() -> None:
    project = _pyproject()["project"]
    assert isinstance(project, dict)
    assert project["scripts"] == {"micelio": "micelio.cli:main"}


def test_changelog_has_a_dated_section_for_the_version() -> None:
    project = _pyproject()["project"]
    assert isinstance(project, dict)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    version = re.escape(str(project["version"]))
    assert re.search(rf"^## \[{version}\] - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.M)
    assert re.search(rf"^\[{version}\]: https://", changelog, re.M)


def test_demo_config_turns_sign_in_off_for_the_sample_vault() -> None:
    config = load_config(ROOT / "examples" / "demo.toml", vault_override=EXAMPLE_VAULT)
    assert config.auth.mode == "none"


def test_compose_example_mounts_files_that_exist() -> None:
    compose = (ROOT / "compose.example.yml").read_text(encoding="utf-8")
    sources = re.findall(r"^\s+- \./([^:]+):", compose, re.M)
    assert sources, "no bind mounts found"
    for source in sources:
        assert (ROOT / source).exists(), source
    assert ":/vault:ro" in compose
    assert "read_only: true" in compose


def test_image_runs_as_a_user_and_reads_the_vault_from_its_mount() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^USER micelio$", dockerfile, re.M)
    for env in ("MICELIO_VAULT=/vault", "MICELIO_DATA=/data", "MICELIO_HOST=0.0.0.0"):
        assert env in dockerfile
    assert "uv sync --locked --no-dev" in dockerfile
