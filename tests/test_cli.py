from __future__ import annotations

from pathlib import Path

import pytest

from mycelium import cli

from .conftest import EXAMPLE_VAULT


def test_check_lists_issues(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["check", "--vault", str(EXAMPLE_VAULT)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("27 notes, ")
    assert "broken-link" in out


def test_check_clean_vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "A.md").write_text("[[B]]", encoding="utf-8")
    (tmp_path / "B.md").write_text("", encoding="utf-8")
    assert cli.main(["check", "--vault", str(tmp_path)]) == 0
    assert "2 notes, 1 links, 0 issues" in capsys.readouterr().out


def test_missing_vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["check", "--vault", str(tmp_path / "nope")]) == 2
    assert "vault folder not found" in capsys.readouterr().err


def test_bad_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = tmp_path / "m.toml"
    cfg.write_text("[site\n", encoding="utf-8")
    assert cli.main(["check", "--config", str(cfg)]) == 2
    assert "invalid TOML" in capsys.readouterr().err


def test_serve_runs_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(app: object, **kwargs: object) -> None:
        seen.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)
    assert cli.main(["serve", "--vault", str(EXAMPLE_VAULT), "--port", "9000"]) == 0
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 9000
