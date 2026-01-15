"""
Rate Limiting Module

Centralized rate limiting using SlowAPI.
Configures limits per endpoint type and provides custom error handling.

PATTERN: Token bucket algorithm for API rate limiting
SKILLS: @api-design-principles, @backend-dev-guidelines
"""

import os
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Rate limit configurations per endpoint type
RATE_LIMITS = {
    "health": "120/minute",      # High limit for health checks
    "analysis": "10/minute",     # Low limit for expensive LLM analysis
    "vision": "15/minute",       # Low limit for vision analysis (VLM is slow)
    "triage": "20/minute",       # Medium limit for triage creation
    "public": "60/minute",       # Default for public endpoints
    "admin": "100/minute",       # Higher limit for admin
    "auth": "30/minute",         # Auth endpoints
}


def get_rate_limit(endpoint_type: str = "public") -> str:
    """
    Get rate limit string for endpoint type.

    Args:
        endpoint_type: Type of endpoint (health, analysis, vision, etc.)

    Returns:
        Rate limit string (e.g., "10/minute")
    """
    return RATE_LIMITS.get(endpoint_type, RATE_LIMITS["public"])


def get_rate_limit_key(request: Request) -> str:
    """
    Extract identifier for rate limiting.

    Priority:
    1. API key from header (if present)
    2. User ID from session (if authenticated)
    3. IP address (fallback)

    Args:
        request: FastAPI/Starlette Request object

    Returns:
        Identifier string for rate limiting
    """
    # Try API key header first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api_key:{api_key}"

    # Try Authorization: Bearer <JWT> (prefer user_id when authenticated)
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token:
            try:
                # Local import avoids circular deps at import time
                from backend.app.auth.jwt import verify_token

                payload = verify_token(token, expected_type="access", check_revocation=False)
                user_id = payload.get("sub")
                role = payload.get("role")
                if user_id:
                    # Optional: expose to downstream code without forcing auth dependency
                    request.state.user_id = user_id
                    if role:
                        request.state.user_role = role
                    return f"user:{user_id}"
            except Exception:
                # Invalid/expired token -> fall back to IP-based limiting
                pass

    # Fallback to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return f"ip:{ip}"


# Storage configuration
# memory:// for development, redis:// for production
storage_uri = os.getenv("RATE_LIMIT_STORAGE", "memory://")

# Create limiter instance
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["100/minute", "1000/hour"],
    storage_uri=storage_uri,
    # Roadmap (Fase 1.4): moving-window is fairer than fixed-window
    strategy="moving-window",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.

    Returns HTTP 429 (Too Many Requests) with Retry-After header.

    Args:
        request: FastAPI Request
        exc: RateLimitExceeded exception

    Returns:
        JSONResponse with 429 status
    """
    identifier = get_rate_limit_key(request)
    logger.warning(f"Rate limit exceeded: {identifier} - Endpoint: {request.url.path}")

    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": "Too many requests. Please try again later.",
            "retry_after": 60,
            "limit": str(exc.detail),
        },
        headers={
            "Retry-After": "60",
            # Best-effort hints to clients; SlowAPI backends may not expose remaining/reset.
            "X-RateLimit-Limit": str(exc.detail),
        },
    )
