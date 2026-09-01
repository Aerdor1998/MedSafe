"""
MedSafe API - Drug Contraindication System
Main application entry point with FastAPI, LangGraph Multi-Agent, PostgreSQL + pgvector
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db.database import init_db
from .middleware import register_middlewares
from .middleware.prometheus import metrics_endpoint
from .utils.error_tracking import setup_error_tracking
from .utils.logging_config import setup_logging

# Setup structured logging
log_file = None  # None = console only (Docker-friendly)
setup_logging(log_level=settings.log_level, log_file=log_file)
logger = logging.getLogger(__name__)

# Error tracking (no-op sem SENTRY_DSN)
setup_error_tracking(settings)


async def check_services_health():
    """Check health of dependent services"""
    # Import here to avoid circular imports
    from .routers.health import check_services_health as _check

    await _check()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources"""
    logger.info("Starting MedSafe API...")

    try:
        # During automated tests we avoid heavyweight startup side-effects
        # (DB init, network checks, external services).
        if settings.testing or os.getenv("TESTING", "").lower() in {"1", "true", "yes"}:
            logger.info(
                "TESTING mode enabled: skipping init_db() and service health checks"
            )
            yield
            return

        init_db()
        logger.info("Database initialized")

        # Seed idempotente: cria o admin inicial a partir de
        # ADMIN_INITIAL_EMAIL/ADMIN_INITIAL_PASSWORD se ainda não existir.
        from .db.seed import seed_initial_admin

        seed_initial_admin()

        await check_services_health()

        logger.info("MedSafe API started successfully")

    except Exception as e:
        logger.error(f"Initialization error: {e}")
        raise

    yield

    logger.info("Shutting down MedSafe API...")


def create_app() -> FastAPI:
    """
    Application factory for FastAPI.

    Creates and configures the FastAPI application with:
    - Middleware (security, CORS, rate limiting, etc.)
    - Routers (health, langgraph, auth, legacy, monitoring)
    - Static files serving

    Returns:
        Configured FastAPI application instance
    """
    logger.info(
        "MedSafe - Drug Contraindication System v%s [%s]",
        settings.app_version,
        "Production" if not settings.debug else "Development",
    )

    app = FastAPI(
        title=settings.app_name,
        description="Drug Contraindication System based on WHO/ANVISA guidelines",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Register middlewares
    register_middlewares(app, settings)

    # Register routers
    _register_routers(app)

    # Mount static files
    _mount_static_files(app)

    # Add metrics endpoint
    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request):
        """Prometheus metrics endpoint"""
        return await metrics_endpoint(request)

    return app


def _register_routers(app: FastAPI) -> None:
    """Register all API routers"""
    from backend.app.routers.admin import router as admin_router
    from backend.app.routers.auth import router as auth_router
    from backend.app.routers.health import router as health_router
    from backend.app.routers.langgraph import router as langgraph_router
    from backend.app.routers.medications import router as medications_router
    from backend.app.routers.monitoring import router as monitoring_router
    from backend.app.routers.vision import router as vision_router

    app.include_router(health_router)
    logger.info("Health endpoints registered")

    app.include_router(langgraph_router)
    logger.info("LangGraph Multi-Agent endpoints registered")

    app.include_router(monitoring_router)
    logger.info("Performance Monitoring endpoints registered")

    app.include_router(auth_router)
    logger.info("Authentication endpoints registered")

    app.include_router(admin_router)
    logger.info("Admin API endpoints registered")

    app.include_router(vision_router)
    logger.info("Vision (OCR/VLM) endpoints registered")

    app.include_router(medications_router)
    logger.info("Medication search endpoints registered")


def _mount_static_files(app: FastAPI) -> None:
    """Mount static file directories"""
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    STATIC_DIR = BASE_DIR / "static"
    FRONTEND_DIR = BASE_DIR / "frontend"

    STATIC_DIR.mkdir(exist_ok=True)
    FRONTEND_DIR.mkdir(exist_ok=True)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # Execução direta é apenas para desenvolvimento local. O container define
    # explicitamente 0.0.0.0 no CMD.
    uvicorn.run(
        "backend.app.main:app", host="127.0.0.1", port=9000, reload=settings.debug
    )
