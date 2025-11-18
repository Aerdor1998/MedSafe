"""
Performance Optimization: Rate Limiting

PATTERN: Token bucket algorithm for API rate limiting
SKILLS: @api-design-principles, @ultrathink, @backend-dev-guidelines

GOALS:
1. Prevent API abuse
2. Ensure fair resource allocation
3. Protect Ollama backend from overload
4. Improve system stability under load

LIMITS:
- Public endpoints: 60 requests/minute
- Analysis endpoints: 10 requests/minute (expensive LLM calls)
- Admin endpoints: 100 requests/minute
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException
from typing import Callable
import logging

logger = logging.getLogger(__name__)


def get_api_key(request: Request) -> str:
    """
    Extract API key or IP address for rate limiting

    PATTERN: Identifier extraction for rate limiting
    SKILL: @api-design-principles - Security best practices

    Priority:
    1. API key from header (if authenticated)
    2. User ID from session (if logged in)
    3. IP address (fallback)

    Args:
        request: FastAPI Request object

    Returns:
        Identifier string for rate limiting
    """
    # Try API key header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api_key:{api_key}"

    # Try user session
    user_id = request.state.user_id if hasattr(request.state, "user_id") else None
    if user_id:
        return f"user:{user_id}"

    # Fallback to IP address
    return f"ip:{get_remote_address(request)}"


# Initialize limiter
limiter = Limiter(
    key_func=get_api_key,
    default_limits=["60/minute"],  # Default: 60 req/min
    storage_uri="memory://",  # In-memory storage (upgrade to Redis for production)
    strategy="fixed-window",  # Simple fixed window (upgrade to sliding window for smoother limits)
)


# Rate limit configurations
RATE_LIMITS = {
    "health": "120/minute",  # High limit for health checks
    "analysis": "10/minute",  # Low limit for expensive LLM analysis
    "vision": "15/minute",  # Low limit for vision analysis (VLM is slow)
    "triage": "20/minute",  # Medium limit for triage creation
    "public": "60/minute",  # Default for public endpoints
    "admin": "100/minute",  # Higher limit for admin
}


def get_rate_limit(endpoint_type: str = "public") -> str:
    """
    Get rate limit string for endpoint type

    Args:
        endpoint_type: Type of endpoint (health, analysis, vision, etc.)

    Returns:
        Rate limit string (e.g., "10/minute")
    """
    return RATE_LIMITS.get(endpoint_type, RATE_LIMITS["public"])


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> HTTPException:
    """
    Custom handler for rate limit exceeded

    PATTERN: Graceful error handling
    SKILL: @api-design-principles - HTTP status codes

    Returns HTTP 429 (Too Many Requests) with Retry-After header

    Args:
        request: FastAPI Request
        exc: RateLimitExceeded exception

    Returns:
        HTTPException with 429 status
    """
    logger.warning(
        f"⚠️  Rate limit exceeded: "
        f"{get_api_key(request)} - "
        f"Endpoint: {request.url.path}"
    )

    return HTTPException(
        status_code=429,
        detail={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please wait before trying again.",
            "retry_after": 60,  # Retry after 60 seconds
            "limit": str(exc),
        },
        headers={"Retry-After": "60"}
    )


# Example usage in routers:
#
# from fastapi import APIRouter
# from .utils.rate_limit import limiter, get_rate_limit
#
# router = APIRouter()
#
# @router.post("/api/analyze")
# @limiter.limit(get_rate_limit("analysis"))
# async def analyze_medication(request: Request, ...):
#     ...
