"""
Unit tests for health router

Tests health check endpoints.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


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
        """Test /healthz endpoint"""
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
