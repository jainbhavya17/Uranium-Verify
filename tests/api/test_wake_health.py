from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from uranium.config import Settings
from uranium.main import create_app


@pytest.fixture
def wake_app(tmp_path):
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 'wake.db').as_posix()}",
        storage_root=tmp_path / "private",
        cors_allowed_origins=(
            "https://uraniumverify.vercel.app",
            "http://localhost:5184",
        ),
    )
    return create_app(settings)


def test_public_health_queries_db_without_auth(wake_app):
    with TestClient(wake_app) as client:
        result = client.get("/health")
        assert result.status_code == 200
        assert result.json() == {"ok": True, "db": True}
        assert result.headers["cache-control"] == "no-store"


def test_public_health_still_returns_200_when_db_fails(wake_app):
    failure = OperationalError("SELECT 1", {}, Exception("test DB unavailable"))
    with TestClient(wake_app) as client, patch.object(wake_app.state.engine, "begin", side_effect=failure):
        result = client.get("/health")
        assert result.status_code == 200
        assert result.json() == {"ok": True, "db": False}


def test_strict_health_still_fails_when_database_is_unavailable(wake_app):
    failure = OperationalError("SELECT 1", {}, Exception("test DB unavailable"))
    with TestClient(wake_app) as client, patch.object(wake_app.state.engine, "connect", side_effect=failure):
        assert client.get("/api/v1/health").status_code == 503


@pytest.mark.parametrize("origin", ["https://uraniumverify.vercel.app", "http://localhost:5184"])
def test_allowed_origins_can_read_wake_route(wake_app, origin):
    with TestClient(wake_app) as client:
        result = client.get("/health", headers={"Origin": origin})
        assert result.status_code == 200
        assert result.headers["access-control-allow-origin"] == origin
        assert result.headers["access-control-allow-credentials"] == "true"


def test_preflight_allows_existing_csrf_header(wake_app):
    with TestClient(wake_app) as client:
        result = client.options(
            "/api/v1/auth/session",
            headers={
                "Origin": "https://uraniumverify.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-CSRF-Token",
            },
        )
        assert result.status_code == 200
        assert result.headers["access-control-allow-origin"] == "https://uraniumverify.vercel.app"


def test_untrusted_origin_is_not_granted_cors_access(wake_app):
    with TestClient(wake_app) as client:
        result = client.get("/health", headers={"Origin": "https://untrusted.invalid"})
        assert "access-control-allow-origin" not in result.headers


def test_cors_origins_are_configurable_and_cannot_use_wildcards(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://preview.example.test/,http://localhost:5184")
    settings = Settings(environment="test")
    settings.validate()
    assert settings.cors_allowed_origins == ("https://preview.example.test", "http://localhost:5184")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="exact HTTP"):
        Settings(environment="test").validate()
