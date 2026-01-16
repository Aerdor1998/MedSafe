"""
Módulo de autenticação e segurança do MedSafe

FASE 1.1: Adicionadas funções de token revocation e verificação async
"""

from .jwt import (
    create_access_token,
    create_refresh_token,
    get_current_active_user,
    get_current_user,
    is_token_revoked,
    revoke_all_user_tokens,
    revoke_token,
    verify_refresh_token,
    verify_refresh_token_async,
    verify_token,
    verify_token_async,
)
from .models import Token, User
from .password import hash_password, verify_password

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
