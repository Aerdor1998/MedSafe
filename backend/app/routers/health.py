"""
Health & Monitoring Endpoints

SKILL: @api-design-principles - Observability endpoints
SKILL: @fastapi-templates - Health check patterns
"""

import logging
from datetime import datetime
from typing import Any, Dict

import requests
from fastapi import APIRouter

from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health & Monitoring"])


async def check_services_health():
    """Verificar saúde dos serviços essenciais"""
    # Verificar banco de dados
    from ..db.database import check_db_health

    if not check_db_health():
        raise Exception("Banco de dados não está saudável")

    # Verificar Ollama
    try:
        response = requests.get(f"{settings.ollama_host}/api/tags", timeout=5)
        if response.status_code != 200:
            raise Exception("Ollama não está respondendo")
    except Exception as e:
        logger.warning(f"Ollama não está disponível: {e}")


@router.get("/healthz")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint

    Returns application health status and service availability
    """
    try:
        # Import here to avoid circular dependency
        from ..db.database import check_db_health

        db_healthy = check_db_health()

        return {
            "status": "healthy" if db_healthy else "degraded",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0-langgraph",
            "services": {"database": "ok" if db_healthy else "error", "api": "ok"},
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """
    (DEPRECATED) Metrics endpoint.

    NOTE:
    - The canonical Prometheus endpoint is provided by `backend.app.middleware.prometheus`
      at `GET /metrics` (text format).
    - This JSON endpoint conflicted with the Prometheus endpoint and could break app startup.
    """
    return {
        "deprecated": True,
        "message": "This JSON metrics endpoint was deprecated. Use GET /metrics for Prometheus scraping.",
    }


@router.get("/readyz")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe (Kubernetes)

    Returns 200 if application is ready to serve traffic
    """
    try:
        from ..db.database import check_db_health

        db_healthy = check_db_health()

        if not db_healthy:
            return {"status": "not_ready", "reason": "Database not available"}

        return {"status": "ready", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {"status": "not_ready", "reason": str(e)}


@router.get("/livez")
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness probe (Kubernetes)

    Returns 200 if application process is alive.
    """
    response = {"status": "live", "timestamp": datetime.now().isoformat()}
    return response
