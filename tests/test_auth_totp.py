from __future__ import annotations

import base64

import pytest

from mycelium.auth.totp import (
    code_at,
    generate_secret,
    is_valid_secret,
    matching_step,
    provisioning_uri,
    step_for,
)

# RFC 6238 appendix B, SHA-1 key "12345678901234567890".
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_rfc_6238_vectors(timestamp: int, expected: str) -> None:
    assert code_at(RFC_SECRET, step_for(timestamp), digits=8) == expected


def test_matching_step_allows_one_step_of_drift() -> None:
    now = 1_700_000_000.0
    step = step_for(now)
    for offset in (-1, 0, 1):
        assert matching_step(RFC_SECRET, code_at(RFC_SECRET, step + offset), now) == step + offset
    assert matching_step(RFC_SECRET, code_at(RFC_SECRET, step + 2), now) is None
    assert matching_step(RFC_SECRET, code_at(RFC_SECRET, step - 2), now) is None


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "12 34 5"])
def test_malformed_codes(code: str) -> None:
    assert matching_step(RFC_SECRET, code, 1_700_000_000.0) is None


def test_spaces_in_code_are_ignored() -> None:
    now = 1_700_000_000.0
    code = code_at(RFC_SECRET, step_for(now))
    assert matching_step(RFC_SECRET, f"{code[:3]} {code[3:]}", now) == step_for(now)


def test_generated_secrets() -> None:
    secret = generate_secret()
    assert is_valid_secret(secret)
    assert len(secret) == 32
    assert secret != generate_secret()
    assert is_valid_secret(secret.lower())
    assert not is_valid_secret("")
    assert not is_valid_secret("not base32 !")
    assert not is_valid_secret("AAAA")  # too short


def test_provisioning_uri() -> None:
    uri = provisioning_uri("ABCDEFGH", account="Ada Lovelace", issuer="Mycelium")
    assert uri.startswith("otpauth://totp/Mycelium%3AAda%20Lovelace?")
    assert "secret=ABCDEFGH" in uri
    assert "issuer=Mycelium" in uri
