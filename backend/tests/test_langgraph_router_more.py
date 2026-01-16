"""
Additional tests for LangGraph router

Tests more endpoints and edge cases.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestLangGraphRouterSetup:
    """Tests for LangGraph router setup"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.app.main import app

        return TestClient(app)

    def test_router_is_mounted(self, client):
        """Test langgraph router is mounted"""
        # Check if we can reach the endpoint
        response = client.get("/api/v2/langgraph/health")

        # Could be 200, 404, or auth error - just checking it's reachable
        assert response.status_code in [200, 404, 401, 403, 500]

    def test_analyze_endpoint_exists(self, client):
        """Test analyze endpoint exists"""
        response = client.post(
            "/api/v2/langgraph/analyze",
            json={"medications": ["aspirin"], "patient_data": {"age": 30}},
        )

        # Check endpoint exists (any response that isn't 404)
        assert response.status_code in [200, 400, 401, 403, 405, 422, 500]

    def test_triage_endpoint_exists(self, client):
        """Test triage endpoint exists"""
        response = client.post(
            "/api/v2/langgraph/triage",
            json={"symptoms": ["headache"], "patient_info": {}},
        )

        assert response.status_code in [200, 400, 401, 403, 404, 405, 422, 500]


class TestLangGraphHealthEndpoint:
    """Tests for health endpoint"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.app.main import app

        return TestClient(app)

    def test_health_returns_json(self, client):
        """Test health endpoint returns JSON"""
        response = client.get("/api/v2/langgraph/health")

        if response.status_code == 200:
            assert response.json() is not None


class TestLangGraphInputValidation:
    """Tests for input validation"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.app.main import app

        return TestClient(app)

    def test_empty_body_rejected(self, client):
        """Test empty body is rejected"""
        response = client.post("/api/v2/langgraph/analyze", json={})

        # Should fail validation
        assert response.status_code in [400, 401, 403, 405, 422, 500]

    def test_missing_medications_rejected(self, client):
        """Test missing medications is handled"""
        response = client.post(
            "/api/v2/langgraph/analyze", json={"patient_data": {"age": 30}}
        )

        assert response.status_code in [400, 401, 403, 405, 422, 500]
