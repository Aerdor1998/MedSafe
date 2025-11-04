"""
Rate limiting usando slowapi
"""

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse


def get_rate_limit_key(request: Request) -> str:
    """
    Função para obter chave de rate limiting
    Combina IP e user ID (se autenticado)
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0]
    else:
        ip = request.client.host if request.client else "unknown"

    # Se tiver autenticação, adicionar user_id
    user_id = request.state.user_id if hasattr(request.state, "user_id") else None
    if user_id:
        return f"{ip}:{user_id}"

    return ip


# Criar limiter
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["100/minute", "1000/hour"],
    storage_uri="redis://localhost:6379/0",  # Usar Redis para distribuído
    strategy="fixed-window",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Handler customizado para rate limit exceeded
    """
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": "Too many requests. Please try again later.",
            "retry_after": exc.detail
        }
    )
