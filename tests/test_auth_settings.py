from __future__ import annotations

import pytest

from mycelium.auth.passwords import hash_password, is_valid_hash, verify_password
from mycelium.auth.settings import AuthSetupError, is_loopback, resolve_auth
from mycelium.auth.totp import generate_secret
from mycelium.config import Config

GOOD = {
    "MYCELIUM_PASSWORD_HASH": "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$aGFzaA",
    "MYCELIUM_TOTP_SECRET": generate_secret(),
    "MYCELIUM_SESSION_KEY": "k" * 40,
}


def config(mode: str = "local") -> Config:
    return Config.model_validate({"auth": {"mode": mode}})


def test_mode_none_turns_sign_in_off_even_with_secrets() -> None:
    settings = resolve_auth(config("none"), GOOD, local_only=False)
    assert not settings.enabled


def test_localhost_without_secrets_is_open() -> None:
    settings = resolve_auth(config(), {}, local_only=True)
    assert not settings.enabled
    assert "localhost" in settings.reason


def test_all_secrets_turn_sign_in_on() -> None:
    settings = resolve_auth(config(), GOOD, local_only=False)
    assert settings.enabled
    assert settings.session_key == "k" * 40


def test_secrets_on_localhost_still_turn_sign_in_on() -> None:
    assert resolve_auth(config(), GOOD, local_only=True).enabled


@pytest.mark.parametrize(
    ("override", "names"),
    [
        ({}, ["PASSWORD_HASH", "TOTP_SECRET", "SESSION_KEY"]),
        ({**GOOD, "MYCELIUM_PASSWORD_HASH": "plain"}, ["PASSWORD_HASH"]),
        ({**GOOD, "MYCELIUM_TOTP_SECRET": "!!"}, ["TOTP_SECRET"]),
        ({**GOOD, "MYCELIUM_SESSION_KEY": "short"}, ["SESSION_KEY"]),
    ],
)
def test_missing_or_bad_secrets_refuse_to_start(override: dict[str, str], names: list[str]) -> None:
    with pytest.raises(AuthSetupError) as info:
        resolve_auth(config(), override, local_only=False)
    for name in names:
        assert f"MYCELIUM_{name}" in str(info.value)


def test_partial_secrets_on_localhost_are_an_error() -> None:
    with pytest.raises(AuthSetupError):
        resolve_auth(config(), {"MYCELIUM_SESSION_KEY": "k" * 40}, local_only=True)


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("127.0.0.1", True),
        ("::1", True),
        ("[::1]", True),
        ("localhost", True),
        ("0.0.0.0", False),
        ("192.168.1.5", False),
        ("example.com", False),
    ],
)
def test_is_loopback(host: str, loopback: bool) -> None:
    assert is_loopback(host) is loopback


def test_password_hashing() -> None:
    hashed = hash_password("correct horse battery")
    assert is_valid_hash(hashed)
    assert verify_password(hashed, "correct horse battery")
    assert not verify_password(hashed, "wrong horse battery")
    assert not verify_password("garbage", "correct horse battery")
    with pytest.raises(ValueError, match="at least 12"):
        hash_password("short")
