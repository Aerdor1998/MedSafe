"""
Tests for Deprecation Middleware

PHASE 1: Test feature flag and deprecation headers
SKILLS: @debugging-strategies
"""

from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI

from backend.app.middleware.deprecation import (
    DeprecationMiddleware,
    get_deprecation_info,
)


class TestDeprecationMiddleware:
    """Test suite for DeprecationMiddleware"""

    @pytest.fixture
    def app_with_middleware(self):
        """Create a test app with deprecation middleware"""
        app = FastAPI()

        # Add middleware
        app.add_middleware(DeprecationMiddleware)

        # Add test endpoints
        @app.get("/api/v1/test")
        async def v1_test():
            return {"message": "v1 endpoint"}

        @app.get("/api/v2/test")
        async def v2_test():
            return {"message": "v2 endpoint"}

        @app.post("/api/analyze")
        async def legacy_analyze():
            return {"message": "legacy endpoint"}

        @app.get("/api/normal")
        async def normal_endpoint():
            return {"message": "normal endpoint"}

        return app

    @pytest.mark.asyncio
    async def test_v2_endpoint_no_deprecation_header(self, app_with_middleware):
        """Test that V2 endpoints don't have deprecation headers"""
        transport = httpx.ASGITransport(app=app_with_middleware)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/v2/test")

        assert response.status_code == 200
        assert "x-api-deprecated" not in response.headers

    @pytest.mark.asyncio
    async def test_normal_endpoint_no_deprecation_header(self, app_with_middleware):
        """Test that non-API endpoints don't have deprecation headers"""
        transport = httpx.ASGITransport(app=app_with_middleware)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/normal")

        assert response.status_code == 200
        assert "x-api-deprecated" not in response.headers

    @patch("backend.app.middleware.deprecation.settings")
    @pytest.mark.asyncio
    async def test_v1_endpoint_has_deprecation_headers_when_enabled(
        self, mock_settings, app_with_middleware
    ):
        """Test V1 endpoints have deprecation headers when enabled"""
        mock_settings.enable_legacy_v1 = True
        mock_settings.legacy_v1_sunset_date = "2025-03-01"
        mock_settings.log_deprecated_usage = False

        transport = httpx.ASGITransport(app=app_with_middleware)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test")

        # Should work but have deprecation headers
        assert response.status_code == 200
        assert response.headers.get("x-api-deprecated") == "true"
        assert response.headers.get("x-api-sunset") == "2025-03-01"

    @patch("backend.app.middleware.deprecation.settings")
    @pytest.mark.asyncio
    async def test_v1_endpoint_returns_410_when_disabled(self, mock_settings):
        """Test V1 endpoints return 410 Gone when disabled"""
        mock_settings.enable_legacy_v1 = False
        mock_settings.legacy_v1_sunset_date = "2025-03-01"
        mock_settings.log_deprecated_usage = False

        # Create fresh app with middleware
        app = FastAPI()
        app.add_middleware(DeprecationMiddleware)

        @app.get("/api/v1/test")
        async def v1_test():
            return {"message": "should not reach"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test")

        assert response.status_code == 410
        data = response.json()
        assert "error" in data
        assert data["error"] == "Gone"
        assert "deprecated" in data["detail"].lower()

    @patch("backend.app.middleware.deprecation.settings")
    @pytest.mark.asyncio
    async def test_legacy_analyze_has_deprecation_headers(
        self, mock_settings, app_with_middleware
    ):
        """Test /api/analyze has deprecation headers"""
        mock_settings.enable_legacy_v1 = True
        mock_settings.legacy_v1_sunset_date = "2025-03-01"
        mock_settings.log_deprecated_usage = False

        transport = httpx.ASGITransport(app=app_with_middleware)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post("/api/analyze")

        assert response.status_code == 200
        assert response.headers.get("x-api-deprecated") == "true"


class TestDeprecationInfo:
    """Test deprecation info helper function"""

    def test_get_deprecation_info_known_endpoint(self):
        """Test deprecation info for known V1 endpoint"""
        with patch("backend.app.middleware.deprecation.settings") as mock_settings:
            mock_settings.enable_legacy_v1 = True
            mock_settings.legacy_v1_sunset_date = "2025-03-01"

            info = get_deprecation_info("/api/v1/triage")

            assert info["deprecated"] is True
            assert info["sunset_date"] == "2025-03-01"
            assert info["v1_endpoint"] == "/api/v1/triage"
            assert info["v2_endpoint"] == "/api/v2/analyze"

    def test_get_deprecation_info_unknown_endpoint(self):
        """Test deprecation info for unknown endpoint"""
        with patch("backend.app.middleware.deprecation.settings") as mock_settings:
            mock_settings.enable_legacy_v1 = True
            mock_settings.legacy_v1_sunset_date = "2025-03-01"

            info = get_deprecation_info("/api/unknown")

            assert info["deprecated"] is True
            assert info["v2_endpoint"] == "/api/v2/"  # Default fallback

    def test_get_deprecation_info_legacy_analyze(self):
        """Test deprecation info for legacy /api/analyze"""
        with patch("backend.app.middleware.deprecation.settings") as mock_settings:
            mock_settings.enable_legacy_v1 = True
            mock_settings.legacy_v1_sunset_date = "2025-03-01"

            info = get_deprecation_info("/api/analyze")

            assert info["deprecated"] is True
            assert info["v2_endpoint"] == "/api/v2/analyze"


class TestDeprecationLogging:
    """Test deprecation logging behavior"""

    @patch("backend.app.middleware.deprecation.settings")
    @patch("backend.app.middleware.deprecation.logger")
    @pytest.mark.asyncio
    async def test_logging_when_enabled(self, mock_logger, mock_settings):
        """Test that deprecated usage is logged when enabled"""
        mock_settings.enable_legacy_v1 = True
        mock_settings.legacy_v1_sunset_date = "2025-03-01"
        mock_settings.log_deprecated_usage = True

        app = FastAPI()
        app.add_middleware(DeprecationMiddleware)

        @app.get("/api/v1/test")
        async def v1_test():
            return {"message": "test"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            await client.get("/api/v1/test")

        # Should have logged a warning
        mock_logger.warning.assert_called()

    @patch("backend.app.middleware.deprecation.settings")
    @patch("backend.app.middleware.deprecation.logger")
    @pytest.mark.asyncio
    async def test_no_logging_when_disabled(self, mock_logger, mock_settings):
        """Test that deprecated usage is not logged when disabled"""
        mock_settings.enable_legacy_v1 = True
        mock_settings.legacy_v1_sunset_date = "2025-03-01"
        mock_settings.log_deprecated_usage = False

        app = FastAPI()
        app.add_middleware(DeprecationMiddleware)

        @app.get("/api/v1/test")
        async def v1_test():
            return {"message": "test"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            await client.get("/api/v1/test")

        # Should NOT have logged a warning
        mock_logger.warning.assert_not_called()
