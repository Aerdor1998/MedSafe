"""
Configurações do MedSafe usando pydantic-settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional, List, Union
import os


class Settings(BaseSettings):
    """Configurações da aplicação MedSafe"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Configurações da aplicação
    app_name: str = "MedSafe"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str  # Obrigatório - sem valor padrão

    # Configurações do banco de dados
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "medsafe"
    postgres_user: str = "medsafe"
    postgres_password: str  # Obrigatório - sem valor padrão
    database_url: Optional[str] = None

    # Configurações do pgvector
    pgvector_dim: int = 1024

    # Configurações do Ollama
    ollama_host: str = "http://ollama:11434"
    ollama_llm: str = "qwen2.5:7b"
    ollama_vlm: str = "qwen2.5vl:7b"

    # Configurações de APIs externas
    enable_rxnorm: bool = True
    rxnorm_base_url: str = "https://rxnav.nlm.nih.gov/REST"

    # Configurações de CORS
    allowed_origins: Union[str, List[str]] = "http://localhost:8000"  # Será parseado para lista

    # Configurações de segurança
    jwt_secret: str  # Obrigatório - sem valor padrão
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    trusted_hosts: Union[str, List[str]] = "localhost,127.0.0.1"  # Hosts confiáveis para produção

    # Configurações de Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None  # Opcional - para Redis com autenticação

    # Configurações de upload
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: Union[str, List[str]] = "jpg,jpeg,png,pdf"  # Será parseado para lista

    # Configurações de OCR
    tesseract_cmd: str = "/usr/bin/tesseract"
    ocr_lang: str = "por+eng"

    # Configurações de logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Configurações de telemetria
    enable_metrics: bool = True
    metrics_port: int = 9090

    @field_validator('allowed_origins', mode='before')
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse comma-separated CORS origins"""
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v

    @field_validator('allowed_extensions', mode='before')
    @classmethod
    def parse_allowed_extensions(cls, v):
        """Parse comma-separated file extensions"""
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        return v

    @field_validator('trusted_hosts', mode='before')
    @classmethod
    def parse_trusted_hosts(cls, v):
        """Parse comma-separated trusted hosts"""
        if isinstance(v, str):
            hosts = [x.strip() for x in v.split(',') if x.strip()]
            # Validar que não seja wildcard em produção
            return hosts
        return v

    def model_post_init(self, __context) -> None:
        """Validação pós-inicialização"""
        # Validar secrets não são valores padrão inseguros
        dangerous_values = [
            "change_me", "change_me_in_production", "secret",
            "password", "123456", "admin", "test"
        ]

        if self.secret_key.lower() in dangerous_values:
            raise ValueError(
                "SECRET_KEY must be changed from default value. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        if self.jwt_secret.lower() in dangerous_values:
            raise ValueError(
                "JWT_SECRET must be changed from default value. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        # Validar comprimento mínimo
        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")

        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")

        # Validar CORS em produção
        if not self.debug and "*" in self.allowed_origins:
            raise ValueError(
                "CORS wildcard '*' is not allowed in production. "
                "Set specific allowed origins in ALLOWED_ORIGINS environment variable."
            )

        # Validar trusted_hosts em produção
        if not self.debug and "*" in self.trusted_hosts:
            raise ValueError(
                "Trusted hosts wildcard '*' is not allowed in production. "
                "Set specific trusted hosts in TRUSTED_HOSTS environment variable."
            )

    @property
    def database_url_safe(self) -> str:
        """Retorna a URL do banco de dados"""
        if self.database_url:
            return self.database_url
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def ollama_base_url(self) -> str:
        """Retorna a URL base do Ollama"""
        return f"{self.ollama_host}/v1"

    @property
    def redis_url(self) -> str:
        """Retorna a URL do Redis para rate limiting"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


# Instância global das configurações
settings = Settings()
