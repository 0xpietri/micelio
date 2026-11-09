from __future__ import annotations

from pathlib import Path

from mycelium.auth.store import AuthStore


def test_sessions(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "deep" / "auth.sqlite3")
    token = store.create_session(now=1000, ttl_seconds=60)
    assert store.session_valid(token, 1059)
    assert not store.session_valid(token, 1060)
    assert not store.session_valid("forged", 1001)
    store.delete_session(token)
    assert not store.session_valid(token, 1001)


def test_only_hashes_are_stored(tmp_path: Path) -> None:
    path = tmp_path / "auth.sqlite3"
    store = AuthStore(path)
    token = store.create_session(now=0, ttl_seconds=60)
    store.close()
    assert token.encode() not in path.read_bytes()


def test_sessions_survive_a_restart_and_can_all_be_ended(tmp_path: Path) -> None:
    path = tmp_path / "auth.sqlite3"
    first = AuthStore(path)
    token = first.create_session(now=0, ttl_seconds=60)
    first.create_session(now=0, ttl_seconds=60)
    first.close()
    second = AuthStore(path)
    assert second.session_valid(token, 1)
    assert second.delete_all_sessions() == 2
    assert not second.session_valid(token, 1)


def test_expired_sessions_are_pruned(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    store.create_session(now=0, ttl_seconds=10)
    store.create_session(now=100, ttl_seconds=10)
    assert store.delete_all_sessions() == 1


def test_failures_window(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    for at in (0, 10, 20):
        store.record_failure("1.2.3.4", at)
    store.record_failure("5.6.7.8", 20)
    assert store.failures_since("1.2.3.4", 0) == 3
    assert store.failures_since("1.2.3.4", 15) == 1
    store.clear_failures("1.2.3.4")
    assert store.failures_since("1.2.3.4", 0) == 0
    assert store.failures_since("5.6.7.8", 0) == 1


def test_totp_steps_are_single_use_and_monotonic(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    assert store.claim_totp_step(100)
    assert not store.claim_totp_step(100)
    assert not store.claim_totp_step(99)
    assert store.claim_totp_step(101)
