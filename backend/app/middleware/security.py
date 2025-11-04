"""
Middleware de segurança para headers HTTP
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware para adicionar security headers em todas as respostas
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # CSP - Mais restritivo em produção, permite 'unsafe-inline' apenas em debug
        if settings.debug:
            # Em desenvolvimento, permitir unsafe-inline para facilitar desenvolvimento
            csp = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:"
        else:
            # Em produção, CSP mais restritivo
            # Nota: Se o frontend usar inline scripts/styles, será necessário usar nonces ou hashes
            csp = "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'"

        response.headers["Content-Security-Policy"] = csp
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Remove headers que expõem informações do servidor
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        return response


async def add_security_headers(request: Request, call_next):
    """
    Função middleware para adicionar security headers
    (Alternativa mais simples ao SecurityHeadersMiddleware)
    """
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # CSP baseado no ambiente
    if settings.debug:
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    else:
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'"

    return response
