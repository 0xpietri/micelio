from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from micelio import cli
from micelio.auth.passwords import verify_password
from micelio.auth.store import AuthStore
from micelio.auth.totp import code_at, step_for

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


def test_serve_takes_defaults_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: seen.update(kwargs))
    monkeypatch.setenv("MICELIO_HOST", "localhost")
    monkeypatch.setenv("MICELIO_PORT", "9100")
    monkeypatch.setenv("MICELIO_FORWARDED_ALLOW_IPS", "172.17.0.1")
    assert cli.main(["serve", "--vault", str(EXAMPLE_VAULT)]) == 0
    assert seen["host"] == "localhost"
    assert seen["port"] == 9100
    assert seen["forwarded_allow_ips"] == "172.17.0.1"
    # Flags still win over the environment.
    assert cli.main(["serve", "--vault", str(EXAMPLE_VAULT), "--port", "9200"]) == 0
    assert seen["port"] == 9200


def test_serve_rejects_a_bad_port_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MICELIO_PORT", "eighty")
    with pytest.raises(SystemExit) as exc:
        cli.main(["serve", "--vault", str(EXAMPLE_VAULT)])
    assert exc.value.code == 2


def test_serve_on_a_public_address_needs_secrets(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["serve", "--vault", str(EXAMPLE_VAULT), "--host", "0.0.0.0"]) == 2
    assert "MICELIO_PASSWORD_HASH" in capsys.readouterr().err


def test_serve_says_when_sign_in_is_off(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: None)
    cli.main(["serve", "--vault", str(EXAMPLE_VAULT)])
    assert "sign-in is off" in capsys.readouterr().err


def answers(*values: str) -> Callable[[str], str]:
    queue = list(values)
    return lambda _prompt: queue.pop(0)


def test_set_password(capsys: pytest.CaptureFixture[str]) -> None:
    pw = "a long enough passphrase"
    assert cli.main(["user", "set-password"], prompt=answers(pw, pw)) == 0
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert line.startswith("MICELIO_PASSWORD_HASH='$argon2id$")
    assert line.endswith("'")
    assert verify_password(line.split("=", 1)[1].strip("'"), pw)


def test_set_password_mismatch_and_short(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["user", "set-password"], prompt=answers("one", "two")) == 1
    assert "do not match" in capsys.readouterr().err
    assert cli.main(["user", "set-password"], prompt=answers("short", "short")) == 1
    assert "at least 12" in capsys.readouterr().err


def test_session_key(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["user", "session-key"]) == 0
    value = capsys.readouterr().out.strip().split("=", 1)[1].strip("'")
    assert len(value) >= 32


def test_totp_setup_confirms_a_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, str] = {}
    real = cli.generate_secret

    def capture() -> str:
        seen["secret"] = real()
        return seen["secret"]

    monkeypatch.setattr(cli, "generate_secret", capture)
    now = 1_800_000_000.0

    def prompt(_text: str) -> str:
        return code_at(seen["secret"], step_for(now))

    assert cli.main(["user", "totp", "--account", "ada"], prompt=prompt, clock=lambda: now) == 0
    out = capsys.readouterr().out
    assert "otpauth" not in out  # the QR carries it; the secret is printed for manual entry
    assert f"MICELIO_TOTP_SECRET='{seen['secret']}'" in out
    assert "\u2588" in out


def test_totp_setup_gives_up_after_three_wrong_codes(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["user", "totp"], prompt=answers("000000", "000000", "000000")) == 1
    assert "not confirmed" in capsys.readouterr().err


def test_sign_out_all(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = tmp_path / "m.toml"
    cfg.write_text('[data]\ndir = "state"\n', encoding="utf-8")
    assert cli.main(["user", "sign-out-all", "--config", str(cfg)]) == 0
    assert "No sessions" in capsys.readouterr().out
    store = AuthStore(tmp_path / "state" / "auth.sqlite3")
    store.create_session(now=time.time(), ttl_seconds=60)
    store.close()
    assert cli.main(["user", "sign-out-all", "--config", str(cfg)]) == 0
    assert "Ended 1 session" in capsys.readouterr().out


def test_totp_without_a_unicode_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_can_print", lambda text: False)
    cli.main(["user", "totp"], prompt=answers("x", "x", "x"))
    out = capsys.readouterr().out
    assert "otpauth://totp/" in out
