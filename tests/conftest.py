from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from mycelium.config import Config, VaultConfig
from mycelium.vault import VaultIndex

EXAMPLE_VAULT = Path(__file__).resolve().parents[1] / "examples" / "vault"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MYCELIUM_CONFIG", raising=False)
    monkeypatch.delenv("MYCELIUM_VAULT", raising=False)


def config_for(root: Path) -> Config:
    return Config(vault=VaultConfig(root=root))


@pytest.fixture(scope="session")
def example_index() -> VaultIndex:
    index = VaultIndex(config_for(EXAMPLE_VAULT))
    index.refresh(force=True)
    return index


VaultFactory = Callable[[dict[str, str]], VaultIndex]


@pytest.fixture
def make_vault(tmp_path: Path) -> VaultFactory:
    """Write ``{relative path: text}`` into a fresh vault and index it."""

    def factory(files: dict[str, str]) -> VaultIndex:
        root = tmp_path / "vault"
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        root.mkdir(exist_ok=True)
        index = VaultIndex(config_for(root))
        index.refresh(force=True)
        return index

    return factory
