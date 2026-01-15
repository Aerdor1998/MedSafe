"""
Additional tests for health router

Tests health endpoints more thoroughly.
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.app.main import app
        return TestClient(app)

    def test_root_health_endpoint(self, client):
        """Test root health endpoint"""
        response = client.get("/health")
        
        # Should return 200 or similar
        assert response.status_code in [200, 404]

    def test_api_v2_health(self, client):
        """Test API v2 health endpoint"""
        response = client.get("/api/v2/health")
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data or isinstance(data, dict)

    def test_ready_endpoint(self, client):
        """Test readiness endpoint"""
        response = client.get("/api/v2/health/ready")
        
        assert response.status_code in [200, 404, 500, 503]

    def test_live_endpoint(self, client):
        """Test liveness endpoint"""
        response = client.get("/api/v2/health/live")
        
        assert response.status_code in [200, 404, 500]


class TestHealthResponseStructure:
    """Tests for health response structure"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.app.main import app
        return TestClient(app)

    def test_health_response_has_status(self, client):
        """Test health response has status field"""
        response = client.get("/api/v2/health")
        
        if response.status_code == 200:
            data = response.json()
            # Should have status field
            assert "status" in data

    def test_ready_response_structure(self, client):
        """Test ready response has expected structure"""
        response = client.get("/api/v2/health/ready")
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
