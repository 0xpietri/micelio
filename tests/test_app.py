from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mycelium.app import create_app

from .conftest import EXAMPLE_VAULT, config_for


def test_healthz_reports_counts_only() -> None:
    client = TestClient(create_app(config_for(EXAMPLE_VAULT), local_only=True))
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["notes"] == 27
    assert set(data) == {"status", "version", "notes"}
    assert "Bayes" not in response.text


def test_healthz_when_vault_is_missing(tmp_path: Path) -> None:
    client = TestClient(create_app(config_for(tmp_path / "gone"), local_only=True))
    assert client.get("/healthz").json()["status"] == "vault-missing"


def test_no_api_docs() -> None:
    client = TestClient(create_app(config_for(EXAMPLE_VAULT), local_only=True))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_home_without_sign_in_on_localhost() -> None:
    client = TestClient(create_app(config_for(EXAMPLE_VAULT), local_only=True))
    response = client.get("/")
    assert response.status_code == 200
    assert "27 notes in the vault" in response.text
    assert "Sign out" not in response.text


def test_security_headers() -> None:
    client = TestClient(create_app(config_for(EXAMPLE_VAULT), local_only=True))
    response = client.get("/")
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_static_files_are_served() -> None:
    client = TestClient(create_app(config_for(EXAMPLE_VAULT), local_only=True))
    response = client.get("/static/css/mycelium.css")
    assert response.status_code == 200
    assert "--accent" in response.text
