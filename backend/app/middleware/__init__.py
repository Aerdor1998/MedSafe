"""
Middlewares personalizados do MedSafe
"""

# IMPORTANTE: Import logging ANTES dos imports locais para evitar shadowing
import logging as stdlib_logging

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi.errors import RateLimitExceeded

from .security import add_security_headers, SecurityHeadersMiddleware
from .logging import LoggingMiddleware  # Nosso middleware de logging
from .metrics import MetricsMiddleware
from .deprecation import DeprecationMiddleware
from .rate_limit import limiter, rate_limit_exceeded_handler
from .prometheus import PrometheusMiddleware, setup_prometheus
from .request_id import RequestIdMiddleware
from .db_query_count import DBQueryCountMiddleware

logger = stdlib_logging.getLogger(__name__)

__all__ = [
    "add_security_headers",
    "SecurityHeadersMiddleware",
    "LoggingMiddleware",
    "MetricsMiddleware",
    "DeprecationMiddleware",
    "register_middlewares",
]


def register_middlewares(app: FastAPI, settings) -> None:
    """
    Register all middlewares on the FastAPI application.

    This centralizes middleware registration for cleaner main.py
    and better testability.

    Args:
        app: FastAPI application instance
        settings: Application settings instance
    """
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(LoggingMiddleware)

    if getattr(settings, "debug", False) or getattr(settings, "testing", False):
        app.add_middleware(DBQueryCountMiddleware)

    app.add_middleware(SecurityHeadersMiddleware)

    is_testing = bool(getattr(settings, "testing", False)) or os.getenv("TESTING", "").lower() in {"1", "true", "yes"}
    if (not settings.debug) and (not is_testing):
        allowed_hosts = settings.allowed_hosts if hasattr(settings, 'allowed_hosts') else ["localhost"]
        if "*" not in allowed_hosts:
            app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    app.add_middleware(PrometheusMiddleware)
    setup_prometheus()

    app.add_middleware(DeprecationMiddleware)
    logger.info("Middleware stack initialized")
