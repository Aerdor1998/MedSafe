"""
Módulo de autenticação e segurança do MedSafe

FASE 1.1: Adicionadas funções de token revocation e verificação async
"""

from .jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_token_async,
    verify_refresh_token,
    verify_refresh_token_async,
    get_current_user,
    get_current_active_user,
    revoke_token,
    revoke_all_user_tokens,
    is_token_revoked,
)
from .password import hash_password, verify_password
from .models import User, Token

__all__ = [
    # Token creation
    "create_access_token",
    "create_refresh_token",
    # Token verification (sync)
    "verify_token",
    "verify_refresh_token",
    # Token verification (async with revocation check)
    "verify_token_async",
    "verify_refresh_token_async",
    # User extraction
    "get_current_user",
    "get_current_active_user",
    # Token revocation (FASE 1.1)
    "revoke_token",
    "revoke_all_user_tokens",
    "is_token_revoked",
    # Password utilities
    "hash_password",
    "verify_password",
    # Models
    "User",
    "Token",
]
