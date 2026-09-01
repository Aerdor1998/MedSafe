"""
Prometheus Metrics Middleware for FastAPI

PATTERN: Metrics collection and export for observability
SKILLS: @prometheus-configuration, @grafana-dashboards, @api-design-principles
"""

import logging
import platform
import secrets
import time
from pathlib import Path
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings

logger = logging.getLogger(__name__)

# Create Prometheus registry
registry = CollectorRegistry()

# ============================================================================
# METRICS DEFINITIONS
# ============================================================================

# ---------------------------------------------------------------------------
# Request metrics (MedSafe-specific)
# ---------------------------------------------------------------------------
medsafe_requests_total = Counter(
    "medsafe_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

medsafe_response_time_seconds = Histogram(
    "medsafe_response_time_seconds",
    "HTTP request response time in seconds",
    ["method", "endpoint"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    registry=registry,
)

# ---------------------------------------------------------------------------
# Request metrics (Prometheus-conventional names)
# These are referenced by infra/prometheus/alerts.yml
# ---------------------------------------------------------------------------
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    registry=registry,
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["endpoint"],
    registry=registry,
)

# Agent execution metrics
medsafe_agent_execution_time_seconds = Gauge(
    "medsafe_agent_execution_time_seconds",
    "Agent execution time in seconds",
    ["agent"],
    registry=registry,
)

# LLM metrics
medsafe_llm_tokens_total = Counter(
    "medsafe_llm_tokens_total",
    "Total LLM tokens used",
    ["agent"],
    registry=registry,
)

medsafe_llm_cost_usd_total = Counter(
    "medsafe_llm_cost_usd_total",
    "Total LLM cost in USD",
    ["agent"],
    registry=registry,
)

# Cache metrics
medsafe_cache_hits = Counter(
    "medsafe_cache_hits",
    "Total cache hits",
    ["cache_type"],
    registry=registry,
)

medsafe_cache_misses = Counter(
    "medsafe_cache_misses",
    "Total cache misses",
    ["cache_type"],
    registry=registry,
)

# Database metrics
medsafe_db_query_duration_seconds = Histogram(
    "medsafe_db_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
    registry=registry,
)

medsafe_db_queries_total = Counter(
    "medsafe_db_queries_total",
    "Total database queries",
    ["query_type"],
    registry=registry,
)


# System health
medsafe_health_status = Gauge(
    "medsafe_health_status",
    "System health status (0=healthy, 1=degraded, 2=unhealthy)",
    registry=registry,
)

# Embedding cache metrics
medsafe_embedding_cache_hits = Counter(
    "medsafe_embedding_cache_hits",
    "Total embedding cache hits",
    registry=registry,
)

medsafe_embedding_cache_misses = Counter(
    "medsafe_embedding_cache_misses",
    "Total embedding cache misses",
    registry=registry,
)

# Application info
medsafe_info = Info(
    "medsafe_application",
    "MedSafe application information",
    registry=registry,
)

# ============================================================================
# HITL (Human-in-the-Loop) METRICS
# ============================================================================

medsafe_hitl_queue_size = Gauge(
    "medsafe_hitl_queue_size",
    "Number of analyses pending human review",
    registry=registry,
)

medsafe_hitl_wait_time_seconds = Histogram(
    "medsafe_hitl_wait_time_seconds",
    "Time spent waiting for human review in seconds",
    buckets=(60, 300, 600, 1800, 3600, 7200, 14400, 28800),
    registry=registry,
)

medsafe_hitl_approved_total = Counter(
    "medsafe_hitl_approved_total",
    "Total number of approved reviews",
    registry=registry,
)

medsafe_hitl_rejected_total = Counter(
    "medsafe_hitl_rejected_total",
    "Total number of rejected reviews",
    registry=registry,
)

medsafe_hitl_pending_by_risk = Gauge(
    "medsafe_hitl_pending_by_risk",
    "Number of pending reviews by risk level",
    ["risk_level"],
    registry=registry,
)

medsafe_hitl_review_time_seconds = Histogram(
    "medsafe_hitl_review_time_seconds",
    "Time taken to complete a review in seconds",
    buckets=(30, 60, 120, 300, 600, 1200, 1800),
    registry=registry,
)

# Alias for alerts compatibility
medsafe_hitl_pending_reviews = Gauge(
    "medsafe_hitl_pending_reviews",
    "Number of analyses awaiting human review (alias for queue_size)",
    registry=registry,
)


# ============================================================================
# ANALYSIS JOB METRICS
# ============================================================================

medsafe_analysis_jobs_pending = Gauge(
    "medsafe_analysis_jobs_pending",
    "Number of pending analysis jobs",
    registry=registry,
)

medsafe_analysis_jobs_running = Gauge(
    "medsafe_analysis_jobs_running",
    "Number of running analysis jobs",
    registry=registry,
)

medsafe_analysis_jobs_completed_total = Counter(
    "medsafe_analysis_jobs_completed_total",
    "Total number of completed analysis jobs",
    registry=registry,
)

medsafe_analysis_jobs_failed_total = Counter(
    "medsafe_analysis_jobs_failed_total",
    "Total number of failed analysis jobs",
    registry=registry,
)


# ============================================================================
# LLM CALL METRICS (for alerts)
# ============================================================================

medsafe_llm_call_duration_seconds = Histogram(
    "medsafe_llm_call_duration_seconds",
    "LLM call duration in seconds",
    buckets=(1, 5, 10, 15, 30, 60, 120),
    registry=registry,
)

medsafe_llm_call_total = Counter(
    "medsafe_llm_call_total",
    "Total LLM calls",
    registry=registry,
)

medsafe_llm_call_errors_total = Counter(
    "medsafe_llm_call_errors_total",
    "Total LLM call errors",
    registry=registry,
)


# ============================================================================
# SECURITY METRICS (for alerts)
# ============================================================================

medsafe_rate_limit_exceeded_total = Counter(
    "medsafe_rate_limit_exceeded_total",
    "Total rate limit exceeded events",
    ["endpoint"],
    registry=registry,
)

medsafe_auth_failures_total = Counter(
    "medsafe_auth_failures_total",
    "Total authentication failures",
    registry=registry,
)


# ============================================================================
# DATABASE CONNECTION POOL METRICS
# ============================================================================

medsafe_db_pool_size = Gauge(
    "medsafe_db_pool_size",
    "Database connection pool size",
    registry=registry,
)

medsafe_db_pool_active = Gauge(
    "medsafe_db_pool_active",
    "Active database connections",
    registry=registry,
)


# ============================================================================
# MIDDLEWARE
# ============================================================================


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to collect Prometheus metrics

    PATTERN: Middleware-based metrics collection
    SKILL: @api-design-principles - Non-invasive metrics
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Collect metrics for each request"""

        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = time.time()
        method = request.method
        # Avoid unbounded label cardinality (e.g. /status/{session_id})
        # Prefer the route template when available.
        route = request.scope.get("route")
        path = getattr(route, "path", None) or request.url.path

        # In-flight tracking
        http_requests_in_progress.labels(endpoint=path).inc()

        # Process request
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as e:
            logger.error(f"Request failed: {e}")
            status = 500
            raise
        finally:
            http_requests_in_progress.labels(endpoint=path).dec()

            # Calculate duration
            duration = time.time() - start_time

            # Record metrics
            medsafe_requests_total.labels(
                method=method,
                endpoint=path,
                status=status,
            ).inc()

            medsafe_response_time_seconds.labels(
                method=method,
                endpoint=path,
            ).observe(duration)

            # Conventional metrics for alert rules
            http_requests_total.labels(
                method=method,
                endpoint=path,
                status=status,
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=path,
            ).observe(duration)

        return response


# ============================================================================
# METRICS UPDATER
# ============================================================================


def update_metrics():
    """Update basic metrics before export"""
    # Health status defaults to healthy
    medsafe_health_status.set(0)


# ============================================================================
# METRICS ENDPOINT
# ============================================================================


async def metrics_endpoint(request: Request):
    """
    Prometheus metrics endpoint

    Endpoint: GET /metrics
    Returns: Prometheus-formatted metrics

    SKILL: @prometheus-configuration
    """
    if not settings.enable_metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if settings.is_production:
        token_file = settings.metrics_auth_token_file
        try:
            expected_token = Path(token_file or "").read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            logger.error("Metrics credential is unavailable")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Metrics endpoint unavailable",
            )

        if len(expected_token) < 32:
            logger.error("Metrics credential is missing or too short")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Metrics endpoint unavailable",
            )

        authorization = request.headers.get("Authorization", "")
        scheme, _, supplied_token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(
            supplied_token, expected_token
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid metrics credential",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Update metrics before export
    update_metrics()

    # Generate Prometheus format
    metrics_output = generate_latest(registry)

    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST,
    )


# ============================================================================
# INITIALIZATION
# ============================================================================


def setup_prometheus():
    """
    Initialize Prometheus metrics and set application info

    PATTERN: Metrics initialization
    """
    # Set application info
    medsafe_info.info(
        {
            "version": "2.0.0",
            "python_version": platform.python_version(),
            "framework": "FastAPI + LangGraph",
            "llm_provider": "Ollama",
            "database": "PostgreSQL + pgvector",
        }
    )

    logger.info("Prometheus metrics initialized")
