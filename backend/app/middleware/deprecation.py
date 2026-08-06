"""
Deprecation Middleware for Legacy V1 Endpoints

PHASE 1: Gradual deprecation with feature flags
SKILLS: @api-design-principles, @backend-dev-guidelines
"""

import logging
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings

logger = logging.getLogger(__name__)


class DeprecationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle deprecated API endpoints

    Features:
    - Block V1 endpoints if feature flag disabled
    - Add deprecation headers to V1 responses
    - Log deprecated endpoint usage
    - Return 410 Gone if V1 disabled
    """

    # V1 endpoint prefixes that are deprecated
    DEPRECATED_PREFIXES = [
        "/api/v1/",
        "/api/analyze",  # Legacy compatibility endpoint
        "/admin/ingest/",
    ]

    # Explicit exceptions (kept alive even when legacy v1 is disabled)
    # Rationale: authentication is infrastructure and must remain available
    # during the migration window.
    EXCLUDED_PREFIXES = [
        "/api/v1/auth",
    ]

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path

        # Check if this is a deprecated endpoint
        is_excluded = any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES)
        is_deprecated = (not is_excluded) and any(
            path.startswith(prefix) for prefix in self.DEPRECATED_PREFIXES
        )

        if is_deprecated:
            # Log deprecated usage if enabled
            if settings.log_deprecated_usage:
                client_ip = request.client.host if request.client else "unknown"
                user_agent = request.headers.get("user-agent", "unknown")
                logger.warning(
                    f"DEPRECATED API CALL: {request.method} {path} "
                    f"from {client_ip} ({user_agent[:50]}...)"
                )

            # If V1 is disabled, return 410 Gone
            if not settings.enable_legacy_v1:
                return JSONResponse(
                    status_code=410,
                    content={
                        "error": "Gone",
                        "detail": (
                            "This API endpoint has been deprecated and removed. "
                            "Please migrate to /api/v2/*. "
                            "See /docs for the new API documentation."
                        ),
                        "migration_guide": "/docs#/LangGraph%20Multi-Agent%20v2",
                        "sunset_date": settings.legacy_v1_sunset_date,
                    },
                    headers={
                        "X-API-Deprecated": "true",
                        "X-API-Sunset": settings.legacy_v1_sunset_date,
                        "Link": '</api/v2/>; rel="successor-version"',
                    },
                )

            # V1 enabled - process request but add deprecation headers
            response = await call_next(request)

            # Add deprecation headers to response
            response.headers["X-API-Deprecated"] = "true"
            response.headers["X-API-Sunset"] = settings.legacy_v1_sunset_date
            response.headers["X-API-Deprecation-Notice"] = (
                "This endpoint is deprecated. Migrate to /api/v2/. "
                f"Removal scheduled for {settings.legacy_v1_sunset_date}."
            )
            response.headers["Link"] = '</api/v2/>; rel="successor-version"'

            return response

        # Not a deprecated endpoint - process normally
        return await call_next(request)


def get_deprecation_info(endpoint: str) -> dict:
    """
    Get deprecation information for an endpoint

    Args:
        endpoint: The API endpoint path

    Returns:
        Dict with deprecation details
    """
    migration_map = {
        "/api/v1/triage": "/api/v2/analyze",
        "/api/v1/triage/{id}/report": "/api/v2/triages/{id}/report",
        "/api/v1/vision/analyze": "/api/v2/analyze (with image parameter)",
        "/api/v1/ingest/bulas": "/api/v2/documents/ingest",
        "/api/v1/meds/search": "/api/v2/medications/search",
        "/api/analyze": "/api/v2/analyze",
        "/admin/ingest/status": "/api/v2/admin/ingest/status",
    }

    v2_endpoint = migration_map.get(endpoint, "/api/v2/")

    return {
        "deprecated": True,
        "sunset_date": settings.legacy_v1_sunset_date,
        "v1_endpoint": endpoint,
        "v2_endpoint": v2_endpoint,
        "migration_docs": "/docs#/LangGraph%20Multi-Agent%20v2",
        "enabled": settings.enable_legacy_v1,
    }
