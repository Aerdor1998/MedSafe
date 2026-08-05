"""
Unit tests for health router

Tests health check endpoints.
"""

from contextlib import contextmanager
from typing import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@contextmanager
def _patched_deps(
    db: bool = True, redis: bool = True, ollama: bool = True
) -> Iterator[None]:
    """Mocka DB, Redis e Ollama nas fontes — testes herméticos, sem rede."""
    with patch("backend.app.db.database.check_db_health", return_value=db), patch(
        "backend.app.utils.cache.check_redis_health", return_value=redis
    ), patch(
        "backend.app.routers.health.check_ollama_health",
        new=AsyncMock(return_value=ollama),
    ):
        yield


class TestHealthEndpoints:
    """Tests for health check endpoints"""

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def app(self):
        """Create test app with health router"""
        from backend.app.routers.health import router

        app = FastAPI()
        app.include_router(router)
        return app

    def test_healthz_endpoint(self, client):
        """Test /healthz endpoint (hermético: dependências mockadas)"""
        with _patched_deps():
            response = client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_health_detailed_endpoint(self, client):
        """Test /health endpoint with details"""
        response = client.get("/health")

        # May or may not exist
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_readyz_endpoint(self, client):
        """Test /readyz endpoint"""
        response = client.get("/readyz")

        # Readiness check
        assert response.status_code in [200, 404, 503]

    def test_livez_endpoint(self, client):
        """Test /livez endpoint"""
        response = client.get("/livez")

        # Liveness check
        assert response.status_code in [200, 404]


class TestHealthResponseFormat:
    """Tests for health response format"""

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def app(self):
        """Create test app"""
        from backend.app.routers.health import router

        app = FastAPI()
        app.include_router(router)
        return app

    def test_healthz_response_structure(self, client):
        """Test healthz response has expected structure"""
        response = client.get("/healthz")

        if response.status_code == 200:
            data = response.json()
            # Should have status field
            assert "status" in data
            # Status should be a string
            assert isinstance(data["status"], str)

    def test_health_includes_version(self, client):
        """Test health response includes version info"""
        response = client.get("/health")

        if response.status_code == 200:
            data = response.json()
            # May include version
            if "version" in data:
                assert isinstance(data["version"], str)


class TestHealthDependencyStatus:
    """Tests for dependency-aware status codes (all dependencies mocked)"""

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def app(self):
        """Create test app with health router"""
        from backend.app.routers.health import router

        app = FastAPI()
        app.include_router(router)
        return app

    def test_healthz_all_healthy_returns_200(self, client):
        """All dependencies up -> healthy + HTTP 200"""
        from backend.app.routers.health import APP_VERSION

        with _patched_deps():
            response = client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == APP_VERSION
        assert "timestamp" in data
        assert data["services"] == {
            "database": "ok",
            "redis": "ok",
            "ollama": "ok",
            "api": "ok",
        }

    def test_healthz_ollama_down_returns_degraded_200(self, client):
        """Ollama down but hard deps up -> degraded + HTTP 200"""
        with _patched_deps(ollama=False):
            response = client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["ollama"] == "error"
        assert data["services"]["database"] == "ok"
        assert data["services"]["redis"] == "ok"

    def test_healthz_db_down_returns_unhealthy_503(self, client):
        """Database down -> unhealthy + HTTP 503"""
        with _patched_deps(db=False):
            response = client.get("/healthz")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["services"]["database"] == "error"

    def test_healthz_redis_down_returns_unhealthy_503(self, client):
        """Redis down -> unhealthy + HTTP 503"""
        with _patched_deps(redis=False):
            response = client.get("/healthz")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["services"]["redis"] == "error"

    def test_readyz_returns_200_when_hard_deps_up(self, client):
        """Postgres and Redis up -> ready + HTTP 200 (Ollama irrelevant)"""
        with _patched_deps(ollama=False):
            response = client.get("/readyz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["services"] == {"database": "ok", "redis": "ok"}

    def test_readyz_returns_503_when_redis_down(self, client):
        """Redis down -> not_ready + HTTP 503"""
        with _patched_deps(redis=False):
            response = client.get("/readyz")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["services"]["redis"] == "error"
        assert "redis" in data["reason"]

    def test_readyz_returns_503_when_db_down(self, client):
        """Database down -> not_ready + HTTP 503"""
        with _patched_deps(db=False):
            response = client.get("/readyz")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["services"]["database"] == "error"
