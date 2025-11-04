"""
Modelos Pydantic para autenticação
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """Schema base de usuário"""

    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    """Schema para criação de usuário"""

    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema para atualização de usuário"""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None


class User(UserBase):
    """Schema de usuário completo"""

    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema de token JWT"""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutos


class TokenPayload(BaseModel):
    """Schema do payload do token"""

    sub: str
    exp: int
    iat: int
    type: str


class LoginRequest(BaseModel):
    """Schema de requisição de login"""

    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Schema de requisição de refresh token"""

    refresh_token: str
