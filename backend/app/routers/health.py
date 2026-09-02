"""
Health & Monitoring Endpoints

SKILL: @api-design-principles - Observability endpoints
SKILL: @fastapi-templates - Health check patterns
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health & Monitoring"])

APP_VERSION = settings.app_version

# Ollama probe tuning:
# - Short timeout keeps probes fast even when Ollama is unreachable.
# - /api/tags responds even while a model is still loading, so a slow model
#   load does not flip the check to unhealthy.
# - Short TTL cache: /healthz is hit concurrently by the Docker healthcheck,
#   monitoring and load balancers; when Ollama is down each uncached probe
#   would cost the full timeout (~2s). 5s is short enough to not mask outages.
_OLLAMA_PROBE_TIMEOUT_SECONDS = 2.0
_OLLAMA_CACHE_TTL_SECONDS = 5.0


@dataclass
class _OllamaProbeCache:
    """Cache curto do probe do Ollama (TTL em relógio monotônico)."""

    healthy: Optional[bool] = None
    expires_at: float = 0.0


_ollama_cache = _OllamaProbeCache()


async def check_ollama_health(use_cache: bool = True) -> bool:
    """Verificar saúde do Ollama (não-bloqueante, com cache curto)"""
    if (
        use_cache
        and _ollama_cache.healthy is not None
        and time.monotonic() < _ollama_cache.expires_at
    ):
        return _ollama_cache.healthy

    healthy = False
    try:
        async with httpx.AsyncClient(timeout=_OLLAMA_PROBE_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{settings.ollama_host}/api/tags")
        healthy = response.status_code == 200
        if not healthy:
            logger.warning(f"Ollama não está respondendo: HTTP {response.status_code}")
    except Exception as e:
        logger.warning(f"Ollama não está disponível: {e}")

    _ollama_cache.healthy = healthy
    _ollama_cache.expires_at = time.monotonic() + _OLLAMA_CACHE_TTL_SECONDS
    return healthy


async def _check_hard_dependencies() -> Tuple[bool, bool]:
    """Verificar dependências obrigatórias (Postgres/Redis) sem bloquear o loop."""
    # Import here to avoid circular dependency
    from ..db.database import check_db_health
    from ..utils.cache import check_redis_health

    db_healthy, redis_healthy = await asyncio.gather(
        run_in_threadpool(check_db_health),
        run_in_threadpool(check_redis_health),
    )
    return db_healthy, redis_healthy


def _service_states(**checks: bool) -> Dict[str, str]:
    """Mapear probes booleanos para o payload de serviços ("ok"/"error")."""
    return {name: "ok" if healthy else "error" for name, healthy in checks.items()}


async def check_services_health() -> None:
    """Verificar saúde dos serviços essenciais (usado no startup)"""
    db_healthy, redis_healthy = await _check_hard_dependencies()
    if not db_healthy:
        raise Exception("Banco de dados não está saudável")
    if not redis_healthy:
        logger.warning("Redis não está disponível no startup")

    # Verificar Ollama (não bloqueia o startup — apenas alerta)
    if not await check_ollama_health(use_cache=False):
        logger.warning("Ollama não está disponível no startup")


@router.get("/healthz")
async def health_check() -> JSONResponse:
    """
    Health check endpoint

    Full dependency report:
    - healthy: all services ok (HTTP 200)
    - degraded: Ollama down but DB + Redis ok — API still accepts/queues work (HTTP 200)
    - unhealthy: a hard dependency (Postgres/Redis) down (HTTP 503)
    """
    try:
        (db_healthy, redis_healthy), ollama_healthy = await asyncio.gather(
            _check_hard_dependencies(),
            check_ollama_health(),
        )

        if db_healthy and redis_healthy:
            status = "healthy" if ollama_healthy else "degraded"
        else:
            status = "unhealthy"

        return JSONResponse(
            status_code=200 if status != "unhealthy" else 503,
            content={
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "version": APP_VERSION,
                "services": _service_states(
                    database=db_healthy,
                    redis=redis_healthy,
                    ollama=ollama_healthy,
                    api=True,
                ),
            },
        )
    except Exception:
        logger.exception("Health check failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": "Internal server error",
                "timestamp": datetime.now().isoformat(),
            },
        )


@router.get("/readyz")
async def readiness_check() -> JSONResponse:
    """
    Readiness probe (Kubernetes)

    Returns 200 only when the hard dependencies (Postgres and Redis) are up;
    otherwise 503 so orchestrators/load balancers stop routing traffic.
    """
    try:
        db_healthy, redis_healthy = await _check_hard_dependencies()

        services = _service_states(database=db_healthy, redis=redis_healthy)

        if not (db_healthy and redis_healthy):
            failed = [name for name, state in services.items() if state != "ok"]
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "reason": f"Unavailable: {', '.join(failed)}",
                    "services": services,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "services": services,
                "timestamp": datetime.now().isoformat(),
            },
        )
    except Exception:
        logger.exception("Readiness check failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "Internal server error",
                "timestamp": datetime.now().isoformat(),
            },
        )


@router.get("/livez")
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness probe (Kubernetes)

    Returns 200 if application process is alive.
    """
    response = {"status": "live", "timestamp": datetime.now().isoformat()}
    return response
