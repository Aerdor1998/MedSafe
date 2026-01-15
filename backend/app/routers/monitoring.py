"""
Monitoring & Metrics API Router (Simplified)

Basic monitoring endpoints. Use Prometheus /metrics for detailed metrics.
"""

from fastapi import APIRouter
from typing import Dict, Any
import logging
from datetime import datetime

from ..utils.cache import get_cache_stats, clear_all_caches

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/monitoring",
    tags=["monitoring"],
    responses={404: {"description": "Not found"}},
)


@router.get("/health")
async def monitoring_health():
    """Health check for monitoring system"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/cache/stats")
async def get_cache_statistics():
    """Get cache statistics"""
    try:
        stats = get_cache_stats()
        return {"cache": stats, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}


@router.post("/cache/clear")
async def clear_caches():
    """Clear all caches"""
    try:
        clear_all_caches()
        logger.warning("Caches cleared via API")
        return {"status": "success", "message": "Caches cleared"}
    except Exception as e:
        logger.error(f"Error clearing caches: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/")
async def monitoring_root():
    """Monitoring API root"""
    return {
        "message": "MedSafe Monitoring API",
        "endpoints": {
            "GET /health": "Health check",
            "GET /cache/stats": "Cache statistics",
            "POST /cache/clear": "Clear caches",
        },
        "note": "For detailed metrics, use GET /metrics (Prometheus format)",
    }
