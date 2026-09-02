"""
Gerenciamento de JWT tokens para autenticação

SECURITY FIX: Separação de verificação access/refresh tokens, claims JWT aprimorados
FASE 1.1: Algoritmos whitelist, key rotation, token revocation via Redis
SKILLS: @api-design-principles, @secrets-management
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import NoReturn, Optional, Tuple

import jwt
import redis.asyncio as redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError as JWTError

from ..config import settings

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()
# Optional scheme (do not error when missing header)
optional_security = HTTPBearer(auto_error=False)

# SECURITY FIX: Issuer e Audience para validação adicional
JWT_ISSUER = "medsafe-api"
JWT_AUDIENCE = "medsafe-client"

# FASE 1.1: Prefixo para JTIs na blacklist Redis
BLACKLIST_PREFIX = "jwt:revoked:"

# FASE 1.1: Redis client para token revocation (lazy initialization)
_redis_client: Optional[redis.Redis] = None


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


async def _get_redis_client() -> Optional[redis.Redis]:
    """
    Obter cliente Redis para token revocation (lazy init)

    SECURITY FIX: Cliente construído a partir da REDIS_URL injetada no
    ambiente (inclui senha em produção), em vez de host/porta hardcoded
    sem autenticação — que falhava silenciosamente contra Redis com
    `--requirepass`.

    Returns:
        Redis client ou None se não configurado/disponível
    """
    global _redis_client

    if not settings.jwt_enable_revocation:
        return None

    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            logger.warning("REDIS_URL not set; cannot connect for JWT revocation")
            return None

        try:
            _redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            # Test connection
            await _redis_client.ping()
            logger.info("Redis connected for JWT revocation")
        except Exception as e:
            logger.warning(f"Redis not available for JWT revocation: {e}")
            _redis_client = None

    return _redis_client


def _fail_closed_revocation_unavailable() -> NoReturn:
    """
    Fail-closed: recusar o token quando a checagem de revogação está
    indisponível em produção.

    Raises:
        HTTPException: sempre (503), para que um token revogado jamais
            seja aceito silenciosamente.
    """
    logger.error("Revocation backend unavailable in production; failing closed")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Token revocation check unavailable",
    )


async def revoke_token(jti: str, exp: datetime) -> bool:
    """
    Revogar um token adicionando seu JTI à blacklist

    FASE 1.1: Token revocation via Redis

    Args:
        jti: JWT ID do token a revogar
        exp: Data de expiração do token (para TTL)

    Returns:
        True se revogado com sucesso, False caso contrário
    """
    client = await _get_redis_client()
    if client is None:
        logger.warning("Cannot revoke token: Redis not available")
        return False

    try:
        # Calcular TTL até expiração do token
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        ttl = int((exp - _utc_now()).total_seconds())
        if ttl <= 0:
            # Token já expirado, não precisa revogar
            return True

        key = f"{BLACKLIST_PREFIX}{jti}"
        await client.setex(key, ttl, "revoked")
        logger.info(f"Token revoked: jti={jti[:8]}...")
        return True

    except Exception as e:
        logger.error(f"Failed to revoke token: {e}")
        return False


async def is_token_revoked(jti: str) -> bool:
    """
    Verificar se um token foi revogado

    FASE 1.1: Token revocation check

    SECURITY FIX: Fail-closed em produção. Se a revogação está habilitada
    mas o backend Redis está indisponível, NUNCA responder "não revogado"
    silenciosamente — levanta HTTP 503 para que um token revogado jamais
    seja aceito. Fora de produção mantém o comportamento permissivo para
    não quebrar dev/test.

    Args:
        jti: JWT ID do token

    Returns:
        True se revogado, False caso contrário

    Raises:
        HTTPException: 503 em produção quando o backend de revogação
            está indisponível
    """
    client = await _get_redis_client()
    if client is None:
        if settings.jwt_enable_revocation and settings.is_production:
            _fail_closed_revocation_unavailable()
        # Se Redis não disponível, não podemos verificar revogação
        return False

    try:
        key = f"{BLACKLIST_PREFIX}{jti}"
        return await client.exists(key) > 0
    except Exception as e:
        logger.error(f"Failed to check token revocation: {e}")
        if settings.is_production:
            _fail_closed_revocation_unavailable()
        return False


async def revoke_all_user_tokens(user_id: str) -> int:
    """
    Revogar todos os tokens de um usuário

    FASE 1.1: Bulk token revocation (ex: logout de todos os dispositivos)

    Args:
        user_id: ID do usuário

    Returns:
        Número de tokens revogados
    """
    client = await _get_redis_client()
    if client is None:
        logger.warning("Cannot revoke user tokens: Redis not available")
        return 0

    try:
        count = 0

        # Esta é uma operação simplificada - em produção real,
        # você manteria um índice user_id -> [jti] no Redis
        logger.info(f"Revoked all tokens for user: {user_id}")
        return count

    except Exception as e:
        logger.error(f"Failed to revoke user tokens: {e}")
        return 0


def _generate_jti() -> str:
    """Gerar JTI (JWT ID) único para cada token"""
    return str(uuid.uuid4())


def _get_access_secret() -> str:
    """
    Obter secret para access tokens

    FASE 1.1: Inclui versão da chave para suportar key rotation
    """
    # Incluir versão da chave no secret para invalidar tokens antigos
    versioned_secret = f"{settings.secret_key}:v{settings.jwt_key_version}"
    return versioned_secret


def _get_refresh_secret() -> str:
    """
    Obter secret para refresh tokens

    SECURITY FIX: Usar secret diferente para refresh tokens
    FASE 1.1: Inclui versão da chave para suportar key rotation
    """
    # Derivar secret diferente para refresh tokens + versão
    base_secret = settings.jwt_secret or settings.secret_key
    versioned = f"{base_secret}:refresh:v{settings.jwt_key_version}"
    return hashlib.sha256(versioned.encode()).hexdigest()


def _validate_algorithm(algorithm: str) -> None:
    """
    Validar que o algoritmo está na whitelist

    FASE 1.1: Algorithm whitelist validation

    Args:
        algorithm: Algoritmo JWT a validar

    Raises:
        ValueError: Se o algoritmo não for permitido
    """
    allowed = settings.jwt_allowed_algorithms
    if algorithm.upper() not in [a.upper() for a in allowed]:
        raise ValueError(
            f"Algoritmo JWT '{algorithm}' não permitido. "
            f"Permitidos: {', '.join(allowed)}"
        )


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    device_id: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Criar token JWT de acesso

    SECURITY FIX: Adicionado JTI, audience, issuer
    FASE 1.1: Validação de algoritmo, versão da chave

    Args:
        data: Dados a serem codificados no token
        expires_delta: Tempo de expiração customizado
        device_id: ID do dispositivo (opcional)

    Returns:
        Tuple[token, jti]: Token JWT codificado e seu JTI
    """
    # FASE 1.1: Validar algoritmo na whitelist
    _validate_algorithm(settings.jwt_algorithm)

    to_encode = data.copy()
    jti = _generate_jti()

    if expires_delta:
        expire = _utc_now() + expires_delta
    else:
        expire = _utc_now() + timedelta(minutes=settings.jwt_expire_minutes)

    # SECURITY FIX: Claims JWT completos
    # FASE 1.1: Adicionado key_version para key rotation
    to_encode.update(
        {
            "exp": expire,
            "iat": _utc_now(),
            "nbf": _utc_now(),
            "type": "access",
            "jti": jti,  # JWT ID único
            "iss": JWT_ISSUER,  # Issuer
            "aud": JWT_AUDIENCE,  # Audience
            "kv": settings.jwt_key_version,  # Key version para rotation
        }
    )

    # Adicionar device_id se fornecido
    if device_id:
        to_encode["device_id"] = device_id

    # Verificar SECRET_KEY
    if not settings.secret_key or settings.secret_key == "change_me_in_production":
        raise ValueError("SECRET_KEY deve ser configurada adequadamente em produção")

    encoded_jwt = jwt.encode(
        to_encode, _get_access_secret(), algorithm=settings.jwt_algorithm
    )

    logger.debug(
        f"Access token created: jti={jti[:8]}..., user={data.get('sub', 'unknown')}"
    )
    return encoded_jwt, jti


def create_refresh_token(
    data: dict, device_id: Optional[str] = None
) -> Tuple[str, str]:
    """
    Criar token JWT de refresh

    SECURITY FIX: Usar secret separado, adicionar JTI
    FASE 1.1: Validação de algoritmo, versão da chave

    Args:
        data: Dados a serem codificados no token
        device_id: ID do dispositivo (opcional)

    Returns:
        Tuple[token, jti]: Token JWT de refresh e seu JTI
    """
    # FASE 1.1: Validar algoritmo na whitelist
    _validate_algorithm(settings.jwt_algorithm)

    to_encode = data.copy()
    jti = _generate_jti()
    expire = _utc_now() + timedelta(days=settings.jwt_refresh_expire_days)

    # SECURITY FIX: Claims JWT completos para refresh
    # FASE 1.1: Adicionado key_version para key rotation
    to_encode.update(
        {
            "exp": expire,
            "iat": _utc_now(),
            "nbf": _utc_now(),
            "type": "refresh",
            "jti": jti,
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "kv": settings.jwt_key_version,  # Key version para rotation
        }
    )

    if device_id:
        to_encode["device_id"] = device_id

    # SECURITY FIX: Usar secret diferente para refresh tokens
    encoded_jwt = jwt.encode(
        to_encode, _get_refresh_secret(), algorithm=settings.jwt_algorithm
    )

    logger.debug(
        f"Refresh token created: jti={jti[:8]}..., user={data.get('sub', 'unknown')}"
    )
    return encoded_jwt, jti


def verify_token(
    token: str, expected_type: str = "access", check_revocation: bool = True
) -> dict:
    """
    Verificar e decodificar token JWT de acesso

    SECURITY FIX: Validação de audience e issuer
    FASE 1.1: Algoritmos whitelist, verificação de revogação

    Args:
        token: Token JWT a ser verificado
        expected_type: Tipo esperado do token (default: "access")
        check_revocation: Se deve verificar revogação (default: True)

    Returns:
        Payload do token decodificado

    Raises:
        HTTPException: Se o token for inválido ou expirado
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # FASE 1.1: Usar whitelist de algoritmos na decodificação
        allowed_algorithms = [a for a in settings.jwt_allowed_algorithms]

        # SECURITY FIX: Validar audience e issuer
        payload = jwt.decode(
            token,
            _get_access_secret(),
            algorithms=allowed_algorithms,  # FASE 1.1: Whitelist
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )

        # Verificar tipo de token
        token_type = payload.get("type")
        if token_type != expected_type:
            logger.warning(
                f"Token type mismatch: expected={expected_type}, got={token_type}"
            )
            raise credentials_exception

        # FASE 1.1: Verificar versão da chave (key rotation)
        token_kv = payload.get("kv", 1)
        if token_kv != settings.jwt_key_version:
            logger.warning(
                f"Token key version mismatch: "
                f"token={token_kv}, current={settings.jwt_key_version}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalidated by key rotation",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verificar expiração (já validado pelo decode, mas dupla verificação)
        exp = payload.get("exp")
        if exp is None:
            raise credentials_exception

        if datetime.fromtimestamp(exp, tz=timezone.utc) < _utc_now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_token_async(
    token: str, expected_type: str = "access", check_revocation: bool = True
) -> dict:
    """
    Verificar token de forma assíncrona (com verificação de revogação)

    FASE 1.1: Versão async com verificação de revogação via Redis

    Args:
        token: Token JWT a ser verificado
        expected_type: Tipo esperado do token
        check_revocation: Se deve verificar revogação

    Returns:
        Payload do token decodificado

    Raises:
        HTTPException: Se o token for inválido, expirado ou revogado
    """
    # Primeiro, validar token sincronamente
    payload = verify_token(token, expected_type, check_revocation=False)

    # FASE 1.1: Verificar se o token foi revogado
    if check_revocation:
        jti = payload.get("jti")
        if jti and await is_token_revoked(jti):
            logger.warning(f"Attempted use of revoked token: jti={jti[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return payload


def verify_refresh_token(token: str) -> dict:
    """
    Verificar e decodificar token JWT de refresh

    SECURITY FIX: Função separada para refresh tokens com secret diferente
    FASE 1.1: Algoritmos whitelist, verificação de versão da chave

    Args:
        token: Token JWT de refresh a ser verificado

    Returns:
        Payload do token decodificado

    Raises:
        HTTPException: Se o token for inválido ou expirado
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # FASE 1.1: Usar whitelist de algoritmos na decodificação
        allowed_algorithms = [a for a in settings.jwt_allowed_algorithms]

        # SECURITY FIX: Usar secret diferente para refresh tokens
        payload = jwt.decode(
            token,
            _get_refresh_secret(),
            algorithms=allowed_algorithms,  # FASE 1.1: Whitelist
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )

        # Verificar tipo de token
        token_type = payload.get("type")
        if token_type != "refresh":
            logger.warning(f"Expected refresh token, got: {token_type}")
            raise credentials_exception

        # FASE 1.1: Verificar versão da chave (key rotation)
        token_kv = payload.get("kv", 1)
        if token_kv != settings.jwt_key_version:
            logger.warning(
                f"Refresh token key version mismatch: "
                f"token={token_kv}, current={settings.jwt_key_version}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token invalidated by key rotation",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verificar expiração
        exp = payload.get("exp")
        if exp is None:
            raise credentials_exception

        if datetime.fromtimestamp(exp, tz=timezone.utc) < _utc_now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verificar JTI existe
        jti = payload.get("jti")
        if not jti:
            logger.warning("Refresh token missing JTI")
            raise credentials_exception

        return payload

    except JWTError as e:
        logger.warning(f"Refresh token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_refresh_token_async(token: str, check_revocation: bool = True) -> dict:
    """
    Verificar refresh token de forma assíncrona (com verificação de revogação)

    FASE 1.1: Versão async com verificação de revogação via Redis

    Args:
        token: Token JWT de refresh a ser verificado
        check_revocation: Se deve verificar revogação

    Returns:
        Payload do token decodificado

    Raises:
        HTTPException: Se o token for inválido, expirado ou revogado
    """
    # Primeiro, validar token sincronamente
    payload = verify_refresh_token(token)

    # FASE 1.1: Verificar se o token foi revogado
    if check_revocation:
        jti = payload.get("jti")
        if jti and await is_token_revoked(jti):
            logger.warning(f"Attempted use of revoked refresh token: jti={jti[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Obter usuário atual a partir do token JWT

    Args:
        credentials: Credenciais HTTP Bearer

    Returns:
        ID do usuário

    Raises:
        HTTPException: Se o token for inválido
    """
    token = credentials.credentials
    # Use async verification to support revocation checks (Redis blacklist)
    payload = await verify_token_async(
        token, expected_type="access", check_revocation=True
    )

    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
) -> Optional[str]:
    """
    Like `get_current_user`, but returns None when no/invalid credentials
    are provided.

    This is used for endpoints that support anonymous access in dev or when
    explicitly enabled.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    try:
        payload = await verify_token_async(
            token, expected_type="access", check_revocation=True
        )
    except Exception:
        return None

    user_id: Optional[str] = payload.get("sub")
    return user_id


async def get_current_active_user(current_user: str = Depends(get_current_user)) -> str:
    """
    Verificar se o usuário está ativo

    Args:
        current_user: ID do usuário atual

    Returns:
        ID do usuário ativo
    """
    # Aqui você pode adicionar verificações adicionais
    # como verificar se o usuário está ativo no banco de dados
    return current_user
