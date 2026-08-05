"""
Additional tests for health router (full app)

Exercita os endpoints reais montados em backend.app.main (/healthz,
/readyz, /livez e /api/v2/health) com dependências externas (Postgres,
Redis e Ollama) mockadas na fonte — herméticos e determinísticos.
"""

from contextlib import contextmanager
from typing import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@contextmanager
def _healthy_deps() -> Iterator[None]:
    """Mocka DB, Redis e Ollama saudáveis nas fontes — sem rede."""
    with patch("backend.app.db.database.check_db_health", return_value=True), patch(
        "backend.app.utils.cache.check_redis_health", return_value=True
    ), patch(
        "backend.app.routers.health.check_ollama_health",
        new=AsyncMock(return_value=True),
    ):
        yield


class TestHealthEndpoints:
    """Tests for health endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.app.main import app

        return TestClient(app)

    def test_root_health_endpoint(self, client):
        """Guard de rota: /health não existe — o probe canônico é /healthz."""
        response = client.get("/health")

        assert response.status_code == 404

    def test_api_v2_health(self, client):
        """GET /api/v2/health é in-process e determinístico -> 200."""
        response = client.get("/api/v2/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "model" in data

    def test_ready_endpoint(self, client):
        """/readyz com Postgres e Redis saudáveis -> 200 ready."""
        with _healthy_deps():
            response = client.get("/readyz")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_live_endpoint(self, client):
        """/livez não depende de serviços externos -> sempre 200 live."""
        response = client.get("/livez")

        assert response.status_code == 200
        assert response.json()["status"] == "live"


class TestHealthResponseStructure:
    """Tests for health response structure"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.app.main import app

        return TestClient(app)

    def test_health_response_has_status(self, client):
        """/healthz saudável reporta status e serviços individuais."""
        with _healthy_deps():
            response = client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"]["database"] == "ok"
        assert data["services"]["redis"] == "ok"

    def test_ready_response_structure(self, client):
        """/readyz reporta exatamente os serviços hard (DB e Redis)."""
        with _healthy_deps():
            response = client.get("/readyz")

        assert response.status_code == 200
        data = response.json()
        assert data["services"] == {"database": "ok", "redis": "ok"}
        assert "timestamp" in data
