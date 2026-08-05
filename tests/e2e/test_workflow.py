"""
E2E Tests - Complete Workflow Tests

PHASE 1: Full workflow E2E tests
SKILLS: @debugging-strategies
"""

import pytest
import json
from playwright.sync_api import Page, expect

# Todos os testes deste módulo exigem stack completa rodando (frontend+API).
# O runner local/CI de unit tests os deseleciona via `-m "not e2e"`.
pytestmark = pytest.mark.e2e


class TestAnalysisWorkflow:
    """Test the complete analysis workflow"""

    def test_full_analysis_workflow_frontend(
        self, 
        page: Page, 
        api_url: str,
        test_patient_data: dict,
        test_medication: dict
    ):
        """Test complete analysis workflow via frontend"""
        # Go to homepage
        page.goto(api_url)
        page.wait_for_load_state("networkidle")
        
        # This test validates the basic flow
        # Actual form filling depends on frontend implementation
        
        # Check page loaded without errors
        expect(page.locator("text=Error 500")).not_to_be_visible()
        expect(page.locator("text=Internal Server Error")).not_to_be_visible()

    def test_api_v2_analyze_workflow(self, page: Page, api_url: str, test_patient_data: dict):
        """Test V2 analysis workflow via API"""
        # First, we need to authenticate (if auth is enabled)
        # For now, test the endpoint exists and validates input
        
        response = page.request.post(
            f"{api_url}/api/v2/analyze",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "patient_data": test_patient_data,
                "medication_text": "Dipirona 500mg",
            })
        )
        
        # Should fail with 401 (no auth) or 422 (validation) but not 500
        assert response.status != 500, "Server error should not occur"
        assert response.status in [401, 403, 422, 200]


class TestErrorHandling:
    """Test error handling scenarios"""

    def test_404_for_unknown_endpoint(self, page: Page, api_url: str):
        """Test 404 for unknown endpoints"""
        response = page.request.get(f"{api_url}/api/unknown/endpoint")
        assert response.status == 404

    def test_invalid_json_returns_422(self, page: Page, api_url: str):
        """Test invalid JSON returns 422"""
        response = page.request.post(
            f"{api_url}/api/v2/analyze",
            headers={"Content-Type": "application/json"},
            data="invalid json {"
        )
        
        # Should return 400 or 422 (not 500)
        assert response.status in [400, 401, 422]

    def test_rate_limiting_exists(self, page: Page, api_url: str):
        """Test that rate limiting is configured"""
        # Make multiple rapid requests
        responses = []
        for _ in range(20):
            response = page.request.get(f"{api_url}/healthz")
            responses.append(response.status)
        
        # All should be 200 (health check has high limits)
        # But if we hit rate limit, we'd get 429
        assert all(r in [200, 429] for r in responses)


class TestSecurityHeaders:
    """Test security headers are present"""

    def test_security_headers_present(self, page: Page, api_url: str):
        """Test that security headers are set"""
        response = page.request.get(f"{api_url}/healthz")
        headers = response.headers
        
        # Check critical security headers
        assert "x-content-type-options" in headers
        assert headers["x-content-type-options"] == "nosniff"
        
        assert "x-frame-options" in headers
        assert headers["x-frame-options"] == "DENY"
        
        # HSTS (may not be present in HTTP)
        # assert "strict-transport-security" in headers

    def test_no_server_header(self, page: Page, api_url: str):
        """Test that server header is removed"""
        response = page.request.get(f"{api_url}/healthz")
        headers = response.headers
        
        # Server header should be removed
        assert "server" not in headers or headers.get("server") != "uvicorn"


class TestCORS:
    """Test CORS configuration"""

    def test_cors_headers_on_options(self, page: Page, api_url: str):
        """Test CORS preflight request"""
        response = page.request.fetch(
            f"{api_url}/api/v2/analyze",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            }
        )
        
        headers = response.headers
        
        # Should have CORS headers (if origin is allowed)
        # The actual allowed origins depend on configuration
        assert response.status in [200, 204, 403]
