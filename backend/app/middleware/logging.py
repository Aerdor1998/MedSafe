"""
Middleware de logging estruturado com redação PHI/PII.

SECURITY: Todos os logs passam por redação automática para compliance LGPD.
"""

import logging
import time
from typing import Any, Dict

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ..config import settings
from ..utils.log_redaction import redact_dict, redact_sensitive_data

logger = structlog.get_logger(__name__)


def _redact_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redacta dados sensíveis de um dicionário de log.

    SECURITY: Esta função é aplicada a todos os eventos de log
    para garantir compliance LGPD mesmo em casos de erro.
    """
    if not settings.enable_log_redaction:
        return data

    return redact_dict(data)


def _safe_str(value: Any) -> str:
    """Converte valor para string com redação."""
    if value is None:
        return ""
    text = str(value)
    if settings.enable_log_redaction:
        return redact_sensitive_data(text)
    return text


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para logging estruturado de requisições.

    SECURITY: Todos os campos são redactados antes de logging.
    Paths sensíveis são marcados para não logar body/params.
    """

    # Paths que podem conter PHI no body (não logar detalhes)
    SENSITIVE_PATHS = {
        "/api/v2/analyze",
        "/api/v2/vision/analyze",
        "/api/v2/hitl/approve",
        "/api/v1/analyze",  # Legacy
    }

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = getattr(request.state, "request_id", None)

        # Verificar se path é sensível (não logar detalhes)
        is_sensitive = any(request.url.path.startswith(p) for p in self.SENSITIVE_PATHS)

        # Log da requisição (redactado)
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else None,
            "request_id": request_id,
        }

        # Não incluir query params para paths sensíveis
        if not is_sensitive and request.url.query:
            log_data["query"] = _safe_str(request.url.query)

        logger.info("request_started", **_redact_log_data(log_data))

        # Processar requisição
        try:
            response = await call_next(request)

            # Calcular duração
            duration = time.time() - start_time

            # Log da resposta (redactado)
            response_log = {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": f"{duration:.3f}s",
                "client": request.client.host if request.client else None,
                "request_id": request_id,
            }

            logger.info("request_completed", **_redact_log_data(response_log))

            # Adicionar header de tempo de resposta
            response.headers["X-Response-Time"] = f"{duration:.3f}s"

            return response

        except Exception as e:
            duration = time.time() - start_time

            # SECURITY: Redactar mensagem de erro (pode conter PHI)
            error_msg = _safe_str(str(e))

            error_log = {
                "method": request.method,
                "path": request.url.path,
                "duration": f"{duration:.3f}s",
                "error": error_msg,
                "client": request.client.host if request.client else None,
                "request_id": request_id,
            }

            logger.error("request_failed", **_redact_log_data(error_log))

            raise
