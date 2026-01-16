"""
Tests for Configuration and Settings

PHASE 1: Test configuration validation
SKILLS: @debugging-strategies
"""

import os
from unittest.mock import patch

import pytest


class TestSettings:
    """Test Settings configuration class"""

    def test_parse_allowed_origins_string(self):
        """Test parsing comma-separated origins"""
        from backend.app.config import Settings

        # Mock environment
        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                "POSTGRES_PASSWORD": "test-password",
                "ALLOWED_ORIGINS": "http://localhost:3000,http://localhost:9000",
                "DEBUG": "true",
            },
            clear=True,
        ):
            s = Settings()
            assert s.allowed_origins == [
                "http://localhost:3000",
                "http://localhost:9000",
            ]

    def test_parse_allowed_hosts_string(self):
        """Test parsing comma-separated hosts"""
        from backend.app.config import Settings

        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                "POSTGRES_PASSWORD": "test-password",
                "ALLOWED_HOSTS": "localhost,127.0.0.1,medsafe.example.com",
                "DEBUG": "true",
            },
            clear=True,
        ):
            s = Settings()
            assert s.allowed_hosts == ["localhost", "127.0.0.1", "medsafe.example.com"]

    def test_parse_allowed_extensions_string(self):
        """Test parsing comma-separated extensions"""
        from backend.app.config import Settings

        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                "POSTGRES_PASSWORD": "test-password",
                "ALLOWED_EXTENSIONS": "jpg,jpeg,png,pdf",
                "DEBUG": "true",
            },
            clear=True,
        ):
            s = Settings()
            assert s.allowed_extensions == ["jpg", "jpeg", "png", "pdf"]

    def test_parse_jwt_allowed_algorithms(self):
        """JWT whitelist parsing/validation should accept secure algs."""
        from backend.app.config import Settings

        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                "POSTGRES_PASSWORD": "test-password",
                "JWT_ALLOWED_ALGORITHMS": "HS256,HS384,HS512",
                "DEBUG": "true",
            },
            clear=True,
        ):
            s = Settings()
            assert s.jwt_allowed_algorithms == ["HS256", "HS384", "HS512"]


class TestFeatureFlags:
    """Test feature flag configuration"""

    def test_enable_legacy_v1_default(self):
        """Test that legacy V1 is enabled by default"""
        from backend.app.config import Settings

        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                "POSTGRES_PASSWORD": "test-password",
                "DEBUG": "true",
            },
            clear=True,
        ):
            s = Settings()
            # Legacy V1 is now disabled by default (endpoints removed)
            assert s.enable_legacy_v1 is False

    def test_legacy_v1_sunset_date_format(self):
        """Test sunset date is in correct format"""
        sunset_date = "2025-03-01"

        from datetime import datetime

        parsed = datetime.strptime(sunset_date, "%Y-%m-%d")

        assert parsed.year == 2025
        assert parsed.month == 3
        assert parsed.day == 1


class TestDatabaseURL:
    """Test database URL construction"""

    def test_database_url_construction(self):
        """Test database URL is constructed correctly"""
        from backend.app.config import Settings

        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                "POSTGRES_PASSWORD": "test_password",
                "POSTGRES_USER": "medsafe",
                "POSTGRES_HOST": "localhost",
                "POSTGRES_PORT": "5432",
                "POSTGRES_DB": "medsafe_db",
                "DEBUG": "true",
            },
            clear=True,
        ):
            s = Settings()
            assert (
                s.database_url_safe
                == "postgresql://medsafe:test_password@localhost:5432/medsafe_db"
            )

    def test_database_url_uses_env_override(self):
        """Test that DATABASE_URL env var takes precedence"""
        from backend.app.config import Settings

        env_url = "postgresql://other:other@otherhost:5433/other_db"
        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                "POSTGRES_PASSWORD": "test-password",
                "DATABASE_URL": env_url,
                "DEBUG": "true",
            },
            clear=True,
        ):
            s = Settings()
            assert s.database_url_safe == env_url


class TestSecurityValidation:
    """Test security-related configuration validation"""

    def test_dangerous_secret_values(self):
        """Test that dangerous secret values are rejected"""
        from backend.app.config import Settings

        with pytest.raises(ValueError):
            with patch.dict(
                os.environ,
                {
                    "SECRET_KEY": "change_me_in_production",
                    "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                    "POSTGRES_PASSWORD": "test-password",
                    "DEBUG": "true",
                },
                clear=True,
            ):
                Settings()

    def test_secret_minimum_length(self):
        """Test that secrets must be at least 32 characters"""
        from backend.app.config import Settings

        with pytest.raises(ValueError):
            with patch.dict(
                os.environ,
                {
                    "SECRET_KEY": "short",
                    "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                    "POSTGRES_PASSWORD": "test-password",
                    "DEBUG": "true",
                },
                clear=True,
            ):
                Settings()

    def test_cors_wildcard_not_allowed_in_production(self):
        """Test that CORS wildcard is not allowed in production"""
        from backend.app.config import Settings

        with pytest.raises(ValueError):
            with patch.dict(
                os.environ,
                {
                    "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                    "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                    "POSTGRES_PASSWORD": "test-password",
                    "DEBUG": "false",
                    "ALLOWED_ORIGINS": "*",
                },
                clear=True,
            ):
                Settings()

    def test_hosts_wildcard_not_allowed_in_production(self):
        """Test that host wildcard is not allowed in production"""
        from backend.app.config import Settings

        with pytest.raises(ValueError):
            with patch.dict(
                os.environ,
                {
                    "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                    "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                    "POSTGRES_PASSWORD": "test-password",
                    "DEBUG": "false",
                    "ALLOWED_HOSTS": "*",
                },
                clear=True,
            ):
                Settings()


class TestOllamaConfiguration:
    """Test Ollama configuration"""

    def test_ollama_host_default(self):
        """Test Ollama host default value"""
        from backend.app.config import Settings

        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                "POSTGRES_PASSWORD": "test-password",
                "DEBUG": "true",
            },
            clear=True,
        ):
            s = Settings()
            assert "ollama" in s.ollama_host
            assert "11434" in s.ollama_host

    def test_ollama_model_defaults(self):
        """Test Ollama model defaults"""
        from backend.app.config import Settings

        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                "POSTGRES_PASSWORD": "test-password",
                "DEBUG": "true",
            },
            clear=True,
        ):
            s = Settings()
            assert "qwen" in s.ollama_llm.lower()
            assert "qwen" in s.ollama_vlm.lower()
            assert "embedding" in s.embedding_model.lower()

    def test_ollama_base_url_construction(self):
        """Test Ollama base URL is constructed correctly"""
        from backend.app.config import Settings

        with patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-secret-key-minimum-32-characters-long",
                "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
                "POSTGRES_PASSWORD": "test-password",
                "OLLAMA_HOST": "http://localhost:11434",
                "DEBUG": "true",
            },
            clear=True,
        ):
            s = Settings()
            assert s.ollama_base_url == "http://localhost:11434/v1"
