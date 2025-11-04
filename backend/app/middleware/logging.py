"""
Middleware de logging estruturado
"""

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para logging estruturado de requisições
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log da requisição
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        # Processar requisição
        try:
            response = await call_next(request)

            # Calcular duração
            duration = time.time() - start_time

            # Log da resposta
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration=f"{duration:.3f}s",
                client=request.client.host if request.client else None,
            )

            # Adicionar header de tempo de resposta
            response.headers["X-Response-Time"] = f"{duration:.3f}s"

            return response

        except Exception as e:
            duration = time.time() - start_time

            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration=f"{duration:.3f}s",
                error=str(e),
                client=request.client.host if request.client else None,
            )

            raise
