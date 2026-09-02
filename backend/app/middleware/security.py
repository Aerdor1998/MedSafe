"""
Security Headers Middleware

Implements OWASP-recommended security headers including:
- Content Security Policy (CSP)
- HTTP Strict Transport Security (HSTS)
- X-Frame-Options, X-Content-Type-Options, X-XSS-Protection
- Referrer-Policy, Permissions-Policy

SECURITY NOTES:
- 'unsafe-inline' is conditionally allowed (controlled by CSP_STRICT_MODE)
- 'unsafe-eval' has been removed as it's not needed
- To fully remove 'unsafe-inline':
  1. Pre-compile Tailwind CSS (build step)
  2. Move inline scripts to external files with nonces
  3. Set CSP_STRICT_MODE=true in environment

CSP MIGRATION PATH:
- Development: unsafe-inline allowed (easier debugging)
- Production (CSP_STRICT_MODE=false): unsafe-inline + nonces (backwards compatible)
- Production (CSP_STRICT_MODE=true): nonces only (hardened)

SKILLS: @api-design-principles, @secrets-management
"""

import base64
import hashlib
import os
import secrets
from typing import List, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ============================================================================
# CSP Configuration
# ============================================================================

# Environment-controlled strict mode
# When True, removes 'unsafe-inline' and relies only on nonces/hashes
CSP_STRICT_MODE = os.getenv("CSP_STRICT_MODE", "false").lower() in ("1", "true", "yes")

# Pre-computed SHA256 hashes for known inline scripts (add as needed)
# Generate with: echo -n "script content" | openssl dgst -sha256 -binary | base64
ALLOWED_SCRIPT_HASHES: List[str] = [
    # Add hashes of known inline scripts here
    # Example: "'sha256-abc123...'"
]

# Pre-computed hashes for known inline styles
ALLOWED_STYLE_HASHES: List[str] = [
    # Add hashes of known inline styles here
]


# Trusted CDN domains for scripts and styles
TRUSTED_SCRIPT_SOURCES_BASE = [
    "'self'",
    "https://cdn.tailwindcss.com",
    "https://cdnjs.cloudflare.com",
    "https://unpkg.com",
]

TRUSTED_STYLE_SOURCES_BASE = [
    "'self'",
    "https://cdnjs.cloudflare.com",
    "https://fonts.googleapis.com",
    "https://unpkg.com",
]

TRUSTED_FONT_SOURCES = [
    "'self'",
    "data:",
    "https://cdnjs.cloudflare.com",
    "https://fonts.gstatic.com",
]

TRUSTED_IMG_SOURCES = [
    "'self'",
    "data:",
    "blob:",
    "https://images.unsplash.com",
    "https://cdn.dribbble.com",
]


def get_script_sources(nonce: str, strict: bool = CSP_STRICT_MODE) -> List[str]:
    """Build script-src directive based on strictness level.

    IMPORTANT: In CSP Level 2+, if a nonce or hash is present, 'unsafe-inline'
    is ignored. So we only add nonce in strict mode, and unsafe-inline in non-strict.
    """
    sources = list(TRUSTED_SCRIPT_SOURCES_BASE)

    if strict:
        # Strict mode: use nonce + hashes only
        sources.append(f"'nonce-{nonce}'")
        sources.extend(ALLOWED_SCRIPT_HASHES)
    else:
        # Non-strict mode: allow unsafe-inline (no nonce needed, as it would disable unsafe-inline)
        sources.append("'unsafe-inline'")

    return sources


def get_style_sources(nonce: str, strict: bool = CSP_STRICT_MODE) -> List[str]:
    """Build style-src directive based on strictness level.

    IMPORTANT: In CSP Level 2+, if a nonce or hash is present, 'unsafe-inline'
    is ignored. So we only add nonce in strict mode, and unsafe-inline in non-strict.
    """
    sources = list(TRUSTED_STYLE_SOURCES_BASE)

    if strict:
        # Strict mode: use nonce + hashes only
        sources.append(f"'nonce-{nonce}'")
        sources.extend(ALLOWED_STYLE_HASHES)
    else:
        # Non-strict mode: allow unsafe-inline (no nonce needed, as it would disable unsafe-inline)
        sources.append("'unsafe-inline'")

    return sources


def compute_sha256_hash(content: str) -> str:
    """Compute SHA256 hash for CSP hash-source."""
    digest = hashlib.sha256(content.encode("utf-8")).digest()
    b64 = base64.b64encode(digest).decode("utf-8")
    return f"'sha256-{b64}'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware para adicionar security headers em todas as respostas

    SECURITY FIX:
    - CSP com CDNs confiáveis permitidos
    - HSTS com preload
    - Permissions-Policy completo
    - Cross-Origin headers relaxados para CDNs

    CSP MODES:
    - CSP_STRICT_MODE=false (default): allows unsafe-inline + nonces
    - CSP_STRICT_MODE=true: nonces only (requires frontend build pipeline)
    """

    def __init__(self, app, strict_csp: Optional[bool] = None):
        super().__init__(app)
        # Allow override via constructor or fall back to environment
        self.strict_csp = strict_csp if strict_csp is not None else CSP_STRICT_MODE

    async def dispatch(self, request: Request, call_next):
        # Gerar nonce único para esta requisição (para CSP)
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)

        # Security headers - OWASP recomendações
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS com preload (requer submissão em hstspreload.org para funcionar)
        # NOTE: Em desenvolvimento, pode ser desabilitado via HSTS_ENABLED=false
        hsts_enabled = os.getenv("HSTS_ENABLED", "true").lower() not in (
            "0",
            "false",
            "no",
        )
        if hsts_enabled:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content Security Policy - com suporte a strict mode
        script_sources = get_script_sources(nonce, strict=self.strict_csp)
        style_sources = get_style_sources(nonce, strict=self.strict_csp)

        csp_directives = [
            "default-src 'self'",
            f"script-src {' '.join(script_sources)}",
            f"script-src-elem {' '.join(script_sources)}",  # Explícito para <script> tags
            f"style-src {' '.join(style_sources)}",
            f"style-src-elem {' '.join(style_sources)}",  # Explícito para <link> e <style> tags
            f"font-src {' '.join(TRUSTED_FONT_SOURCES)}",
            f"img-src {' '.join(TRUSTED_IMG_SOURCES)}",
            # Permitir source maps (.map) de CDNs confiáveis
            "connect-src 'self' https://cdnjs.cloudflare.com https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.0.6/",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'",
            "object-src 'none'",
        ]

        # Add report-uri for CSP violation monitoring (if configured)
        csp_report_uri = os.getenv("CSP_REPORT_URI")
        if csp_report_uri:
            csp_directives.append(f"report-uri {csp_report_uri}")

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (Feature Policy successor)
        permissions = [
            "accelerometer=()",
            "camera=()",
            "geolocation=()",
            "gyroscope=()",
            "magnetometer=()",
            "microphone=()",
            "payment=()",
            "usb=()",
            "interest-cohort=()",  # Bloqueia FLoC do Google
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions)

        # Cross-Origin headers - relaxados para permitir CDNs
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        # Removido Cross-Origin-Embedder-Policy para permitir recursos externos

        # Remove headers que expõem informações do servidor
        headers_to_remove = [
            "Server",
            "X-Powered-By",
            "X-AspNet-Version",
            "X-AspNetMvc-Version",
        ]
        for header in headers_to_remove:
            if header in response.headers:
                del response.headers[header]

        return response


async def add_security_headers(request: Request, call_next):
    """
    Função middleware alternativa para adicionar security headers
    (mantida para compatibilidade)
    """
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Content-Security-Policy"] = "default-src 'self'"

    return response
