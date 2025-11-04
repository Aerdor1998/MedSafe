"""
CSRF Protection Middleware

Implementa proteção contra ataques Cross-Site Request Forgery (CSRF)
seguindo as melhores práticas de segurança.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from typing import Callable
import secrets
import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Middleware para proteção CSRF usando Double Submit Cookie pattern.

    Este middleware:
    1. Gera um token CSRF para cada sessão
    2. Valida tokens em requisições que modificam dados (POST, PUT, DELETE, PATCH)
    3. Permite requisições GET, HEAD, OPTIONS sem validação
    4. Fornece endpoint para obter novo token

    Uso:
        app.add_middleware(
            CSRFMiddleware,
            secret_key=settings.secret_key,
            cookie_name="csrf_token",
            header_name="X-CSRF-Token"
        )
    """

    # Métodos HTTP que requerem validação CSRF
    CSRF_REQUIRED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    # Métodos HTTP seguros (não modificam dados)
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    # Endpoints que não requerem CSRF (ex: login, health checks)
    EXEMPT_PATHS = {
        "/api/health",
        "/api/healthz",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/auth/login",  # Login não precisa de CSRF
    }

    def __init__(
        self,
        app,
        secret_key: str,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        cookie_secure: bool = True,
        cookie_httponly: bool = True,
        cookie_samesite: str = "Strict",
        max_age: int = 3600,  # 1 hora
    ):
        """
        Inicializar middleware CSRF.

        Args:
            app: Aplicação ASGI
            secret_key: Chave secreta para geração de tokens
            cookie_name: Nome do cookie CSRF
            header_name: Nome do header CSRF
            cookie_secure: Se cookie deve ser HTTPS only
            cookie_httponly: Se cookie deve ser HTTP only
            cookie_samesite: Política SameSite (Strict, Lax, None)
            max_age: Tempo de vida do token em segundos
        """
        super().__init__(app)
        self.secret_key = secret_key.encode()
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.cookie_secure = cookie_secure
        self.cookie_httponly = cookie_httponly
        self.cookie_samesite = cookie_samesite
        self.max_age = max_age

    def generate_csrf_token(self) -> str:
        """
        Gerar token CSRF criptograficamente seguro.

        Returns:
            str: Token CSRF em formato hexadecimal
        """
        random_bytes = secrets.token_bytes(32)
        signature = hmac.new(self.secret_key, random_bytes, hashlib.sha256).digest()

        # Combinar random bytes com assinatura
        token = random_bytes + signature
        return token.hex()

    def verify_csrf_token(self, token: str) -> bool:
        """
        Verificar validade de um token CSRF.

        Args:
            token: Token a ser verificado

        Returns:
            bool: True se token é válido, False caso contrário
        """
        try:
            # Decodificar token
            token_bytes = bytes.fromhex(token)

            if len(token_bytes) != 64:  # 32 bytes random + 32 bytes signature
                return False

            # Separar random bytes e assinatura
            random_bytes = token_bytes[:32]
            provided_signature = token_bytes[32:]

            # Recalcular assinatura
            expected_signature = hmac.new(
                self.secret_key, random_bytes, hashlib.sha256
            ).digest()

            # Comparação constant-time para prevenir timing attacks
            return hmac.compare_digest(expected_signature, provided_signature)

        except (ValueError, TypeError):
            return False

    def is_exempt(self, path: str) -> bool:
        """
        Verificar se caminho está isento de validação CSRF.

        Args:
            path: Caminho da requisição

        Returns:
            bool: True se isento, False caso contrário
        """
        return path in self.EXEMPT_PATHS or path.startswith("/static/")

    async def dispatch(self, request: Request, call_next: Callable):
        """
        Processar requisição e aplicar proteção CSRF.

        Args:
            request: Requisição HTTP
            call_next: Próximo middleware/handler

        Returns:
            Response: Resposta HTTP
        """
        # Verificar se requisição requer validação CSRF
        requires_csrf = (
            request.method in self.CSRF_REQUIRED_METHODS
            and not self.is_exempt(request.url.path)
        )

        if requires_csrf:
            # Obter token do cookie
            cookie_token = request.cookies.get(self.cookie_name)

            # Obter token do header
            header_token = request.headers.get(self.header_name)

            # Validar presença de ambos os tokens
            if not cookie_token or not header_token:
                logger.warning(
                    f"CSRF validation failed: Missing tokens for {request.method} {request.url.path}"
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "CSRF token missing",
                        "message": "CSRF token is required for this request",
                        "details": "Include CSRF token in both cookie and request header",
                    },
                )

            # Validar tokens
            if not self.verify_csrf_token(cookie_token):
                logger.warning("CSRF validation failed: Invalid cookie token")
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Invalid CSRF token",
                        "message": "CSRF token in cookie is invalid or expired",
                    },
                )

            if not self.verify_csrf_token(header_token):
                logger.warning("CSRF validation failed: Invalid header token")
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Invalid CSRF token",
                        "message": "CSRF token in header is invalid or expired",
                    },
                )

            # Verificar se tokens são iguais (Double Submit Cookie)
            if cookie_token != header_token:
                logger.warning("CSRF validation failed: Token mismatch")
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "CSRF token mismatch",
                        "message": "CSRF tokens in cookie and header do not match",
                    },
                )

        # Processar requisição
        response = await call_next(request)

        # Se não há token no cookie, gerar um novo
        if not request.cookies.get(self.cookie_name):
            new_token = self.generate_csrf_token()
            response.set_cookie(
                key=self.cookie_name,
                value=new_token,
                max_age=self.max_age,
                secure=self.cookie_secure,
                httponly=self.cookie_httponly,
                samesite=self.cookie_samesite,
                path="/",
            )

            # Adicionar token ao header de resposta para facilitar acesso no frontend
            response.headers[self.header_name] = new_token

        return response


def get_csrf_token_endpoint():
    """
    Endpoint para obter um novo token CSRF.

    Este endpoint pode ser usado pelo frontend para obter
    um token CSRF válido antes de fazer requisições.

    Returns:
        dict: Token CSRF
    """
    # Este endpoint será implementado em main.py
    pass
