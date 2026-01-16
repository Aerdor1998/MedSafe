"""
Configurações do MedSafe usando pydantic-settings.

SECURITY: Este módulo implementa validações de segurança críticas:
- Bloqueio de secrets default em staging/produção
- Validação de entropia mínima em secrets
- Validação de ambiente para compliance
"""

import math
import os
import re
import sys
from typing import List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _calculate_entropy(s: str) -> float:
    """
    Calcula a entropia de Shannon de uma string.

    Valores de referência:
    - Entropia baixa (<3.0): string repetitiva ou previsível
    - Entropia média (3.0-4.0): alguma aleatoriedade
    - Entropia alta (>4.0): boa aleatoriedade
    """
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    entropy = 0.0
    length = len(s)
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


class Settings(BaseSettings):
    """Configurações da aplicação MedSafe"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """
        Make tests deterministic by ignoring `.env`.

        In CI/tests we set `TESTING=true` and rely exclusively on `os.environ`
        (e.g. `patch.dict(os.environ, ..., clear=True)`), so the working tree
        `.env` can't override test expectations.
        """
        # We also detect pytest itself because some tests use `patch.dict(..., clear=True)`
        # and may temporarily unset TESTING.
        is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules)
        if is_pytest or os.getenv("TESTING", "").lower() in {"1", "true", "yes"}:
            return (init_settings, env_settings, file_secret_settings)
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)

    # Configurações da aplicação
    app_name: str = "MedSafe"
    app_version: str = "1.0.0"
    debug: bool = False
    # True durante testes automatizados (evita inicializações pesadas no startup)
    testing: bool = False

    # ==========================================================================
    # ENVIRONMENT CONFIGURATION
    # ==========================================================================
    # SECURITY: Define o ambiente de execução para validações de segurança
    # Valores: development, staging, production
    environment: str = "development"

    # Defaults exist to keep imports/tests deterministic, but are blocked in production via model_post_init.
    secret_key: str = "CHANGE_ME_MIN_32_CHARS__SET_SECRET_KEY_IN_ENV__"

    # Configurações do banco de dados
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "medsafe"
    postgres_user: str = "medsafe"
    postgres_password: str = "CHANGE_ME__SET_POSTGRES_PASSWORD_IN_ENV__"
    database_url: Optional[str] = None

    # Configurações do pgvector
    pgvector_dim: int = 1024

    # Configurações do Ollama
    # NOTE: do not call os.getenv() here; pydantic-settings already reads env.
    ollama_host: str = "http://ollama:11434"
    ollama_llm: str = "qwen3:8b"
    ollama_vlm: str = "qwen2.5vl:7b"
    embedding_model: str = "qwen3-embedding:0.6b"

    # Configurações de APIs externas
    enable_rxnorm: bool = True
    rxnorm_base_url: str = "https://rxnav.nlm.nih.gov/REST"

    # Configurações de CORS
    allowed_origins: Union[str, List[str]] = (
        "http://localhost:9000"  # Será parseado para lista
    )

    # Configurações de hosts permitidos (TrustedHostMiddleware)
    # SECURITY FIX: Hosts específicos para produção, não usar wildcard
    allowed_hosts: Union[str, List[str]] = (
        "localhost,127.0.0.1"  # Será parseado para lista
    )

    # Configurações de segurança
    jwt_secret: str = "CHANGE_ME_MIN_32_CHARS__SET_JWT_SECRET_IN_ENV__"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7

    # FASE 1.1: Configurações avançadas de JWT
    # Algoritmos seguros permitidos (whitelist)
    jwt_allowed_algorithms: Union[str, List[str]] = "HS256,HS384,HS512"
    # Key rotation: versão atual da chave (incrementar para invalidar tokens antigos)
    jwt_key_version: int = 1
    # Token revocation: habilitar blacklist via Redis
    jwt_enable_revocation: bool = True
    # TTL para JTIs na blacklist (em segundos) - deve ser >= refresh token TTL
    jwt_blacklist_ttl: int = 604800  # 7 dias

    # Configurações de upload
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: Union[str, List[str]] = (
        "jpg,jpeg,png,pdf"  # Será parseado para lista
    )

    # Configurações de OCR
    tesseract_cmd: str = "/usr/bin/tesseract"
    ocr_lang: str = "por+eng"

    # Configurações de logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Configurações de telemetria
    enable_metrics: bool = True
    metrics_port: int = 9090

    # ==========================================================================
    # DATA RETENTION & PRIVACY (LGPD Compliance)
    # ==========================================================================

    # Habilitar redação automática de PHI/PII em logs (SEMPRE true em produção)
    enable_log_redaction: bool = True

    # Retenção de dados em dias (padrões seguros para compliance médica)
    retention_analysis_jobs_days: int = 365  # 1 ano
    retention_triages_days: int = 365 * 5  # 5 anos (CFM Res. 1821/2007)
    retention_reports_days: int = 365 * 5  # 5 anos
    retention_hitl_reviews_days: int = 365 * 5  # 5 anos (auditoria médica)
    retention_audit_logs_days: int = 365 * 5  # 5 anos (LGPD Art. 37)
    retention_user_sessions_days: int = 90  # 90 dias após expiração
    retention_ingest_jobs_days: int = 180  # 6 meses

    # Criptografia de dados em repouso (configuração para volumes/DB)
    data_encryption_at_rest: bool = True

    # ==========================================================================
    # FEATURE FLAGS
    # ==========================================================================
    # FASE 1: Feature flags para deprecação gradual de endpoints legacy

    # V1 endpoints removidos - mantido para compatibilidade do middleware
    enable_legacy_v1: bool = False

    # Data de sunset dos endpoints V1 (para header X-API-Sunset)
    legacy_v1_sunset_date: str = "2025-03-01"

    # Habilitar logging de uso de endpoints deprecated
    log_deprecated_usage: bool = True

    # Allow anonymous (unauthenticated) access to some v2 endpoints.
    # Default: disabled in production. Enable explicitly for demos/dev environments.
    allow_anonymous_analysis: bool = False

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse comma-separated CORS origins"""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def parse_allowed_extensions(cls, v):
        """Parse comma-separated file extensions"""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """Parse comma-separated allowed hosts"""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @field_validator("jwt_allowed_algorithms", mode="before")
    @classmethod
    def parse_jwt_algorithms(cls, v):
        """Parse and validate JWT algorithms whitelist"""
        # Algoritmos considerados seguros (NIST/OWASP recomendados)
        SECURE_ALGORITHMS = {
            "HS256",
            "HS384",
            "HS512",  # HMAC-SHA
            "RS256",
            "RS384",
            "RS512",  # RSA-SHA
            "ES256",
            "ES384",
            "ES512",  # ECDSA
            "PS256",
            "PS384",
            "PS512",  # RSA-PSS
        }

        if isinstance(v, str):
            algorithms = [x.strip().upper() for x in v.split(",") if x.strip()]
        else:
            algorithms = [x.upper() for x in v]

        # Validar que todos os algoritmos são seguros
        for alg in algorithms:
            if alg not in SECURE_ALGORITHMS:
                raise ValueError(
                    f"Algoritmo JWT '{alg}' não é seguro. "
                    f"Permitidos: {', '.join(sorted(SECURE_ALGORITHMS))}"
                )

        # Bloquear algoritmo 'none' explicitamente
        if "NONE" in [a.upper() for a in algorithms]:
            raise ValueError(
                "Algoritmo 'none' não é permitido por questões de segurança"
            )

        return algorithms

    def model_post_init(self, __context) -> None:
        """
        Validação pós-inicialização.

        SECURITY: Este método implementa validações críticas de segurança:
        1. Bloqueio de secrets default em staging/produção
        2. Validação de entropia mínima
        3. Validação de padrões inseguros conhecidos
        """
        is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules)
        is_testing_env = os.getenv("TESTING", "").lower() in {
            "1",
            "true",
            "yes",
        } or bool(getattr(self, "testing", False))

        # Determinar strictness baseado em ambiente e flags
        is_production = self.environment.lower() == "production"
        is_staging = self.environment.lower() == "staging"
        is_strict_env = (
            (is_production or is_staging) and (not is_testing_env) and (not is_pytest)
        )
        is_very_strict = is_production and (not is_testing_env) and (not is_pytest)

        # ==========================================================================
        # VALIDAÇÃO DE AMBIENTE
        # ==========================================================================
        valid_environments = {"development", "staging", "production"}
        if self.environment.lower() not in valid_environments:
            raise ValueError(
                f"ENVIRONMENT must be one of: {', '.join(valid_environments)}. "
                f"Got: {self.environment}"
            )

        # ==========================================================================
        # VALIDAÇÃO DE SECRETS - Valores default bloqueados
        # ==========================================================================
        # Padrões conhecidos de valores inseguros
        dangerous_values = {
            "change_me",
            "change_me_in_production",
            "secret",
            "password",
            "123456",
            "admin",
            "test",
            "medsafe",
            "default",
            "unsafe",
            "development",
            "staging",
            "production",
            "changeme",
            "qwerty",
        }

        # Padrões regex de valores inseguros
        unsafe_patterns = [
            r"^change.?me",  # change_me, changeme, change-me
            r"^(secret|password)",  # secret*, password*
            r"^(test|dev|demo)",  # test*, dev*, demo*
            r"^[a-z]{1,8}$",  # palavras curtas simples
            r"^[0-9]+$",  # apenas números
            r"(.)\1{5,}",  # caracteres repetidos (aaaaaa)
        ]

        allow_test_prefix = is_pytest or is_testing_env

        def _is_unsafe_secret(value: str) -> bool:
            """Verifica se um secret é inseguro."""
            v_lower = value.lower()
            if allow_test_prefix and v_lower.startswith("test-") and len(value) >= 32:
                return False
            if v_lower in dangerous_values:
                return True
            for pattern in unsafe_patterns:
                if re.match(pattern, v_lower):
                    return True
            return False

        # In staging/production, block placeholder defaults
        if is_strict_env:
            if self.secret_key == "CHANGE_ME_MIN_32_CHARS__SET_SECRET_KEY_IN_ENV__":
                raise ValueError(
                    f"SECRET_KEY must be set via environment variables in {self.environment}. "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            if self.jwt_secret == "CHANGE_ME_MIN_32_CHARS__SET_JWT_SECRET_IN_ENV__":
                raise ValueError(
                    f"JWT_SECRET must be set via environment variables in {self.environment}. "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            if self.postgres_password == "CHANGE_ME__SET_POSTGRES_PASSWORD_IN_ENV__":
                raise ValueError(
                    f"POSTGRES_PASSWORD must be set via environment variables in {self.environment}. "
                    "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

        # ==========================================================================
        # VALIDAÇÃO DE SECRETS - Valores inseguros
        # ==========================================================================
        secret_unsafe = _is_unsafe_secret(self.secret_key)
        jwt_unsafe = _is_unsafe_secret(self.jwt_secret)
        if secret_unsafe:
            raise ValueError(
                "SECRET_KEY must be changed from default/unsafe value. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        if jwt_unsafe:
            raise ValueError(
                "JWT_SECRET must be changed from default/unsafe value. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        # Validar postgres_password em ambientes estritos
        if is_strict_env and _is_unsafe_secret(self.postgres_password):
            raise ValueError(
                f"POSTGRES_PASSWORD is too simple for {self.environment}. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(24))'"
            )

        # ==========================================================================
        # VALIDAÇÃO DE COMPRIMENTO MÍNIMO
        # ==========================================================================
        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")

        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")

        if is_strict_env and len(self.postgres_password) < 16:
            raise ValueError(
                f"POSTGRES_PASSWORD must be at least 16 characters in {self.environment}"
            )

        # ==========================================================================
        # VALIDAÇÃO DE ENTROPIA (apenas em produção)
        # ==========================================================================
        if is_very_strict:
            min_entropy = 3.5  # Mínimo aceitável para secrets

            secret_key_entropy = _calculate_entropy(self.secret_key)
            if secret_key_entropy < min_entropy:
                raise ValueError(
                    f"SECRET_KEY has low entropy ({secret_key_entropy:.2f}). "
                    f"Expected at least {min_entropy}. "
                    "Generate a more random value with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

            jwt_entropy = _calculate_entropy(self.jwt_secret)
            if jwt_entropy < min_entropy:
                raise ValueError(
                    f"JWT_SECRET has low entropy ({jwt_entropy:.2f}). "
                    f"Expected at least {min_entropy}. "
                    "Generate a more random value with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

        # ==========================================================================
        # VALIDAÇÃO DE CORS E HOSTS
        # ==========================================================================
        if (is_strict_env or not self.debug) and "*" in self.allowed_origins:
            raise ValueError(
                f"CORS wildcard '*' is not allowed in {self.environment}. "
                "Set specific allowed origins in ALLOWED_ORIGINS environment variable."
            )

        if (is_strict_env or not self.debug) and "*" in self.allowed_hosts:
            raise ValueError(
                f"Host wildcard '*' is not allowed in {self.environment}. "
                "Set specific allowed hosts in ALLOWED_HOSTS environment variable."
            )

        # ==========================================================================
        # VALIDAÇÃO DE DEBUG EM PRODUÇÃO
        # ==========================================================================
        if is_production and self.debug:
            raise ValueError(
                "DEBUG mode cannot be enabled in production. "
                "Set DEBUG=false in environment variables."
            )

        # ==========================================================================
        # VALIDAÇÃO DE LOG REDACTION EM PRODUÇÃO
        # ==========================================================================
        if is_production and not self.enable_log_redaction:
            raise ValueError(
                "Log redaction must be enabled in production for LGPD compliance. "
                "Set ENABLE_LOG_REDACTION=true in environment variables."
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


# Instância global das configurações
settings = Settings()
