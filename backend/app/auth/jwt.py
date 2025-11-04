"""
Gerenciamento de JWT tokens para autenticação
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from ..config import settings

# Security scheme
security = HTTPBearer()

# Configurações JWT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Criar token JWT de acesso

    Args:
        data: Dados a serem codificados no token
        expires_delta: Tempo de expiração customizado

    Returns:
        Token JWT codificado
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Adicionar claims padrão
    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.utcnow(),
            "nbf": datetime.utcnow(),
            "type": "access",
        }
    )

    # Verificar SECRET_KEY
    if not settings.secret_key or settings.secret_key == "change_me_in_production":
        raise ValueError("SECRET_KEY deve ser configurada adequadamente em produção")

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)

    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Criar token JWT de refresh

    Args:
        data: Dados a serem codificados no token

    Returns:
        Token JWT de refresh
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)

    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Verificar e decodificar token JWT

    Args:
        token: Token JWT a ser verificado

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
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])

        # Verificar tipo de token
        token_type = payload.get("type")
        if token_type != "access":
            raise credentials_exception

        # Verificar expiração
        exp = payload.get("exp")
        if exp is None:
            raise credentials_exception

        if datetime.fromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


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
    payload = verify_token(token)

    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
