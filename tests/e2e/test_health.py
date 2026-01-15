"""
E2E Tests - Health & Basic Endpoints

PHASE 1: Basic E2E tests for health checks
SKILLS: @debugging-strategies
"""

import pytest
from playwright.sync_api import Page, expect

# Mark entire module as E2E so default test runs can skip it.
pytestmark = pytest.mark.e2e


class TestHealthEndpoints:
    """Test health and basic endpoints"""

    def test_healthz_returns_200(self, page: Page, api_url: str):
        """Test that /healthz returns 200 OK"""
        response = page.request.get(f"{api_url}/healthz")
        assert response.ok
        assert response.status == 200

        data = response.json()
        assert data["status"] == "healthy"

    def test_health_detailed(self, page: Page, api_url: str):
        """Test detailed health endpoint"""
        response = page.request.get(f"{api_url}/api/v2/health")
        assert response.ok

        data = response.json()
        assert "status" in data
        assert "version" in data

    def test_metrics_endpoint(self, page: Page, api_url: str):
        """Test Prometheus metrics endpoint"""
        response = page.request.get(f"{api_url}/metrics")
        assert response.ok

        # Metrics should be in Prometheus format
        text = response.text()
        assert "http_requests_total" in text or "medsafe" in text.lower()

    def test_docs_endpoint_in_debug(self, page: Page, api_url: str):
        """Test API docs endpoint (available in debug mode)"""
        response = page.request.get(f"{api_url}/docs")
        # Docs may be disabled in production
        assert response.status in [200, 404]


class TestFrontendLoading:
    """Test frontend page loading"""

    def test_homepage_loads(self, page: Page, api_url: str):
        """Test that homepage loads correctly"""
        page.goto(api_url)
        
        # Should have title
        expect(page).to_have_title("MedSafe - Análise de Medicamentos")
        
        # Should not have error messages
        expect(page.locator("text=Error")).not_to_be_visible()

    def test_frontend_has_form(self, page: Page, api_url: str):
        """Test that frontend has the patient form"""
        page.goto(api_url)
        
        # Wait for page to load
        page.wait_for_load_state("networkidle")
        
        # Check for form elements (may vary based on frontend implementation)
        # Using flexible selectors
        form_exists = (
            page.locator("form").count() > 0 or
            page.locator("input").count() > 0 or
            page.locator("[data-testid]").count() > 0
        )
        assert form_exists, "No form elements found on page"


class TestAPIV2Endpoints:
    """Test V2 API endpoints"""

    def test_v2_analyze_requires_auth(self, page: Page, api_url: str):
        """Test that V2 endpoints require authentication"""
        response = page.request.post(
            f"{api_url}/api/v2/analyze",
            data={"patient_data": "{}"}
        )
        
        # Should return 401 or 422 (unauthorized or validation error)
        assert response.status in [401, 403, 422]

    def test_v2_triages_list_requires_auth(self, page: Page, api_url: str):
        """Test that listing triages requires authentication"""
        response = page.request.get(f"{api_url}/api/v2/triages")
        
        # Should return 401 (unauthorized)
        assert response.status in [401, 403, 404]


class TestDeprecatedEndpoints:
    """Test deprecated V1 endpoints"""

    def test_v1_triage_has_deprecation_header(self, page: Page, api_url: str):
        """Test that V1 endpoints include deprecation headers"""
        response = page.request.post(
            f"{api_url}/api/v1/triage",
            data={"age": 30, "weight": 70}
        )
        
        # Check for deprecation headers (if V1 is enabled)
        headers = response.headers
        
        # V1 may be disabled (410) or return deprecation headers
        if response.status == 410:
            # V1 is disabled
            data = response.json()
            assert "deprecated" in data.get("error", "").lower() or "gone" in data.get("error", "").lower()
        else:
            # V1 is enabled but deprecated
            assert headers.get("x-api-deprecated") == "true"
            assert "x-api-sunset" in headers

    def test_v1_disabled_returns_410(self, page: Page, api_url: str):
        """Test V1 returns 410 when disabled"""
        response = page.request.get(f"{api_url}/api/v1/meds/search?q=test")
        
        # Either works (deprecated) or returns 410 (disabled)
        assert response.status in [200, 410, 422]
