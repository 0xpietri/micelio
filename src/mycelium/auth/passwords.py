"""Password hashing with argon2id."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

MIN_LENGTH = 12


def hash_password(password: str) -> str:
    if len(password) < MIN_LENGTH:
        raise ValueError(f"use at least {MIN_LENGTH} characters")
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def is_valid_hash(password_hash: str) -> bool:
    return password_hash.startswith("$argon2")
