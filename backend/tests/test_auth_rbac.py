"""
Tests for Authentication and RBAC

PHASE 1: Comprehensive auth tests
SKILLS: @debugging-strategies
"""

import os
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestJWTTokens:
    """Test JWT token creation and verification"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with valid secrets"""
        # Garantir timezone consistente para testes de expiração
        os.environ["TZ"] = "UTC"
        if hasattr(time, "tzset"):
            time.tzset()
        with patch("backend.app.auth.jwt.settings") as mock:
            mock.secret_key = "test-secret-key-minimum-32-characters-long"
            mock.jwt_secret = "test-jwt-secret-minimum-32-characters-long"
            # FASE 1.1: Novos campos de configuração
            mock.jwt_algorithm = "HS256"
            mock.jwt_allowed_algorithms = ["HS256", "HS384", "HS512"]
            mock.jwt_key_version = 1
            mock.jwt_expire_minutes = 30
            mock.jwt_refresh_expire_days = 7
            mock.jwt_enable_revocation = False  # Desabilitar para testes unitários
            yield mock

    def test_create_access_token(self, mock_settings):
        """Test access token creation"""
        from backend.app.auth.jwt import create_access_token

        data = {"sub": "test-user-id"}
        token, jti = create_access_token(data)

        assert token is not None
        assert len(token) > 0
        assert jti is not None
        assert len(jti) > 0

    def test_create_refresh_token(self, mock_settings):
        """Test refresh token creation"""
        from backend.app.auth.jwt import create_refresh_token

        data = {"sub": "test-user-id"}
        token, jti = create_refresh_token(data)

        assert token is not None
        assert len(token) > 0
        assert jti is not None

    def test_access_token_contains_correct_type(self, mock_settings):
        """Test that access token has correct type claim"""
        from backend.app.auth.jwt import create_access_token, verify_token

        data = {"sub": "test-user-id"}
        token, jti = create_access_token(data)

        # Verify token
        payload = verify_token(token, expected_type="access")

        assert payload["type"] == "access"
        assert payload["sub"] == "test-user-id"
        assert payload["jti"] == jti

    def test_refresh_token_contains_correct_type(self, mock_settings):
        """Test that refresh token has correct type claim"""
        from backend.app.auth.jwt import create_refresh_token, verify_refresh_token

        data = {"sub": "test-user-id"}
        token, jti = create_refresh_token(data)

        # Verify refresh token
        payload = verify_refresh_token(token)

        assert payload["type"] == "refresh"
        assert payload["sub"] == "test-user-id"

    def test_access_token_has_issuer_and_audience(self, mock_settings):
        """Test that tokens have issuer and audience claims"""
        from backend.app.auth.jwt import create_access_token, verify_token

        data = {"sub": "test-user-id"}
        token, _ = create_access_token(data)

        payload = verify_token(token)

        assert payload["iss"] == "medsafe-api"
        assert payload["aud"] == "medsafe-client"

    def test_verify_token_rejects_refresh_as_access(self, mock_settings):
        """Test that verify_token rejects refresh tokens"""
        from fastapi import HTTPException

        from backend.app.auth.jwt import create_refresh_token, verify_token

        data = {"sub": "test-user-id"}
        token, _ = create_refresh_token(data)

        # Should raise exception when verifying refresh token as access
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token, expected_type="access")

        assert exc_info.value.status_code == 401

    def test_verify_refresh_token_rejects_access(self, mock_settings):
        """Test that verify_refresh_token rejects access tokens"""
        from fastapi import HTTPException

        from backend.app.auth.jwt import create_access_token, verify_refresh_token

        data = {"sub": "test-user-id"}
        token, _ = create_access_token(data)

        # Should raise exception when verifying access token as refresh
        with pytest.raises(HTTPException) as exc_info:
            verify_refresh_token(token)

        assert exc_info.value.status_code == 401

    def test_token_with_device_id(self, mock_settings):
        """Test token creation with device ID"""
        from backend.app.auth.jwt import create_access_token, verify_token

        data = {"sub": "test-user-id"}
        token, _ = create_access_token(data, device_id="device-123")

        payload = verify_token(token)

        assert payload["device_id"] == "device-123"


class TestJWTRevocation:
    """Test JWT revocation helpers (Redis-backed, mocked)"""

    @pytest.mark.asyncio
    async def test_revoke_token_sets_key_with_ttl(self):
        from backend.app.auth import jwt as jwt_mod

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)

        with patch.object(
            jwt_mod, "_get_redis_client", AsyncMock(return_value=mock_redis)
        ):
            exp = datetime.utcnow() + timedelta(minutes=5)
            ok = await jwt_mod.revoke_token("jti-123", exp)

        assert ok is True
        mock_redis.setex.assert_awaited()

    @pytest.mark.asyncio
    async def test_is_token_revoked_true_when_exists(self):
        from backend.app.auth import jwt as jwt_mod

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)

        with patch.object(
            jwt_mod, "_get_redis_client", AsyncMock(return_value=mock_redis)
        ):
            revoked = await jwt_mod.is_token_revoked("jti-xyz")

        assert revoked is True

    @pytest.mark.asyncio
    async def test_is_token_revoked_false_when_no_redis(self):
        """Fora de produção: permissivo quando Redis indisponível"""
        from backend.app.auth import jwt as jwt_mod

        with patch.object(
            jwt_mod, "_get_redis_client", AsyncMock(return_value=None)
        ), patch.object(jwt_mod, "settings") as mock_settings:
            mock_settings.jwt_enable_revocation = True
            mock_settings.is_production = False
            revoked = await jwt_mod.is_token_revoked("jti-xyz")

        assert revoked is False

    @pytest.mark.asyncio
    async def test_get_redis_client_builds_from_redis_url(self):
        """SECURITY FIX: cliente deve ser construído a partir de REDIS_URL"""
        from backend.app.auth import jwt as jwt_mod

        mock_client = AsyncMock()

        with patch.object(jwt_mod, "_redis_client", None), patch.dict(
            os.environ, {"REDIS_URL": "redis://:s3cret@redis-host:6390/2"}
        ), patch.object(
            jwt_mod.redis, "from_url", MagicMock(return_value=mock_client)
        ) as mock_from_url, patch(
            "backend.app.auth.jwt.settings"
        ) as mock_settings:
            mock_settings.jwt_enable_revocation = True

            client = await jwt_mod._get_redis_client()

            assert client is mock_client
            mock_from_url.assert_called_once_with(
                "redis://:s3cret@redis-host:6390/2",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            mock_client.ping.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_redis_client_degrades_without_redis_url(self):
        """Sem REDIS_URL definido, degrada (None) em vez de crashar"""
        from backend.app.auth import jwt as jwt_mod

        env = {k: v for k, v in os.environ.items() if k != "REDIS_URL"}

        with patch.object(jwt_mod, "_redis_client", None), patch.dict(
            os.environ, env, clear=True
        ), patch("backend.app.auth.jwt.settings") as mock_settings:
            mock_settings.jwt_enable_revocation = True

            client = await jwt_mod._get_redis_client()

        assert client is None

    @pytest.mark.asyncio
    async def test_is_token_revoked_fails_closed_in_production(self):
        """SECURITY FIX: em produção, Redis indisponível => 503, não False"""
        from fastapi import HTTPException

        from backend.app.auth import jwt as jwt_mod

        with patch.object(
            jwt_mod, "_get_redis_client", AsyncMock(return_value=None)
        ), patch("backend.app.auth.jwt.settings") as mock_settings:
            mock_settings.jwt_enable_revocation = True
            mock_settings.environment = "production"
            mock_settings.is_production = True

            with pytest.raises(HTTPException) as exc_info:
                await jwt_mod.is_token_revoked("jti-xyz")

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_is_token_revoked_fails_closed_on_redis_error_in_production(self):
        """SECURITY FIX: erro de Redis em produção => 503, não False"""
        from fastapi import HTTPException

        from backend.app.auth import jwt as jwt_mod

        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(side_effect=ConnectionError("redis down"))

        with patch.object(
            jwt_mod, "_get_redis_client", AsyncMock(return_value=mock_redis)
        ), patch("backend.app.auth.jwt.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.is_production = True

            with pytest.raises(HTTPException) as exc_info:
                await jwt_mod.is_token_revoked("jti-xyz")

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_is_token_revoked_permissive_in_development(self):
        """Fora de produção, Redis indisponível mantém comportamento permissivo"""
        from backend.app.auth import jwt as jwt_mod

        with patch.object(
            jwt_mod, "_get_redis_client", AsyncMock(return_value=None)
        ), patch("backend.app.auth.jwt.settings") as mock_settings:
            mock_settings.jwt_enable_revocation = True
            mock_settings.environment = "development"
            mock_settings.is_production = False

            revoked = await jwt_mod.is_token_revoked("jti-xyz")

        assert revoked is False

    @pytest.mark.asyncio
    async def test_revoked_jti_still_reported_revoked(self):
        """JTI genuinamente revogado continua sendo reportado como revogado"""
        from backend.app.auth import jwt as jwt_mod

        store = {}

        async def fake_setex(key, ttl, value):
            store[key] = value
            return True

        async def fake_exists(key):
            return 1 if key in store else 0

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=fake_setex)
        mock_redis.exists = AsyncMock(side_effect=fake_exists)

        with patch.object(
            jwt_mod, "_get_redis_client", AsyncMock(return_value=mock_redis)
        ):
            exp = datetime.utcnow() + timedelta(minutes=5)
            ok = await jwt_mod.revoke_token("jti-revogado", exp)
            revoked = await jwt_mod.is_token_revoked("jti-revogado")
            other = await jwt_mod.is_token_revoked("jti-outro")

        assert ok is True
        assert revoked is True
        assert other is False


class TestRBAC:
    """Test Role-Based Access Control"""

    def test_role_hierarchy(self):
        """Test role hierarchy is correct"""
        from backend.app.auth.rbac import UserRole, check_role_hierarchy

        # Admin has all permissions
        assert check_role_hierarchy(UserRole.ADMIN, UserRole.ADMIN) is True
        assert check_role_hierarchy(UserRole.ADMIN, UserRole.PHYSICIAN) is True
        assert check_role_hierarchy(UserRole.ADMIN, UserRole.PHARMACIST) is True
        assert check_role_hierarchy(UserRole.ADMIN, UserRole.READONLY) is True

        # Physician has physician and below
        assert check_role_hierarchy(UserRole.PHYSICIAN, UserRole.ADMIN) is False
        assert check_role_hierarchy(UserRole.PHYSICIAN, UserRole.PHYSICIAN) is True
        assert check_role_hierarchy(UserRole.PHYSICIAN, UserRole.PHARMACIST) is True
        assert check_role_hierarchy(UserRole.PHYSICIAN, UserRole.READONLY) is True

        # Pharmacist has pharmacist and below
        assert check_role_hierarchy(UserRole.PHARMACIST, UserRole.ADMIN) is False
        assert check_role_hierarchy(UserRole.PHARMACIST, UserRole.PHYSICIAN) is False
        assert check_role_hierarchy(UserRole.PHARMACIST, UserRole.PHARMACIST) is True
        assert check_role_hierarchy(UserRole.PHARMACIST, UserRole.READONLY) is True

        # Readonly only has readonly
        assert check_role_hierarchy(UserRole.READONLY, UserRole.ADMIN) is False
        assert check_role_hierarchy(UserRole.READONLY, UserRole.PHYSICIAN) is False
        assert check_role_hierarchy(UserRole.READONLY, UserRole.PHARMACIST) is False
        assert check_role_hierarchy(UserRole.READONLY, UserRole.READONLY) is True

    def test_permission_check(self):
        """Test permission checking for roles"""
        from backend.app.auth.rbac import Permission, UserRole, check_permission

        # Admin has all permissions
        assert check_permission(UserRole.ADMIN, Permission.USER_CREATE) is True
        assert check_permission(UserRole.ADMIN, Permission.ANALYSIS_APPROVE) is True

        # Physician can approve analysis
        assert check_permission(UserRole.PHYSICIAN, Permission.ANALYSIS_APPROVE) is True
        assert check_permission(UserRole.PHYSICIAN, Permission.USER_CREATE) is False

        # Pharmacist is an explicit HITL reviewer in the production spec
        assert (
            check_permission(UserRole.PHARMACIST, Permission.ANALYSIS_APPROVE) is True
        )
        assert check_permission(UserRole.PHARMACIST, Permission.TRIAGE_CREATE) is True

        # Readonly can only read
        assert check_permission(UserRole.READONLY, Permission.TRIAGE_READ) is True
        assert check_permission(UserRole.READONLY, Permission.TRIAGE_CREATE) is False


class TestAuthSchemas:
    """Operational IAM contracts used by the production bootstrap."""

    def test_admin_can_assign_supported_role_on_registration(self):
        from backend.app.auth.models import UserCreate
        from backend.app.auth.rbac import UserRole

        physician = UserCreate(
            email="doctor@example.com",
            password="a-secure-password",
            role="physician",
        )
        default_user = UserCreate(
            email="reader@example.com", password="a-secure-password"
        )

        assert physician.role is UserRole.PHYSICIAN
        assert default_user.role is UserRole.READONLY

    def test_password_rotation_requires_twelve_characters(self):
        from pydantic import ValidationError

        from backend.app.auth.models import ChangePasswordRequest

        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password="old", new_password="too-short")


class TestUserModel:
    """Test User database model"""

    def test_password_hashing(self):
        """Test password hashing and verification"""
        from backend.app.db.user_models import User

        password = "test-password-123"
        hashed = User.hash_password(password)

        # Hash should be different from plain password
        assert hashed != password
        assert len(hashed) > 0

    def test_failed_login_tracking(self):
        """Test failed login attempt tracking"""
        from backend.app.db.user_models import User

        user = User(
            email="test@example.com",
            password_hash="hashed",
            failed_login_attempts=0,
        )

        # Record failed logins
        user.record_failed_login()
        assert user.failed_login_attempts == 1

        user.record_failed_login()
        assert user.failed_login_attempts == 2

        # After 5 attempts, should be locked
        for _ in range(3):
            user.record_failed_login()

        assert user.failed_login_attempts == 5
        assert user.is_locked() is True
        assert user.locked_until is not None

    def test_successful_login_resets_attempts(self):
        """Test that successful login resets failed attempts"""
        from backend.app.db.user_models import User

        user = User(
            email="test@example.com",
            password_hash="hashed",
            failed_login_attempts=3,
        )

        user.record_successful_login()

        assert user.failed_login_attempts == 0
        assert user.locked_until is None
        assert user.last_login is not None

    def test_is_locked_expires(self):
        """Test that lock expires after timeout"""
        from datetime import datetime, timedelta

        from backend.app.db.user_models import User

        user = User(
            email="test@example.com",
            password_hash="hashed",
            failed_login_attempts=5,
            locked_until=datetime.utcnow() - timedelta(minutes=1),  # Already expired
        )

        # Should not be locked since lock expired
        assert user.is_locked() is False


class TestUserSessionModel:
    """Test user_sessions model used for refresh token tracking"""

    def test_is_expired(self):
        """Test session expiration check"""
        from datetime import datetime, timedelta

        from backend.app.db.user_models import UserSession

        # Not expired
        token = UserSession(
            user_id=uuid.uuid4(),
            jti=str(uuid.uuid4()),
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        assert token.is_expired() is False

        # Expired
        token_expired = UserSession(
            user_id=uuid.uuid4(),
            jti=str(uuid.uuid4()),
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert token_expired.is_expired() is True

    def test_revoke(self):
        """Test session revocation"""
        from datetime import datetime, timedelta

        from backend.app.db.user_models import UserSession

        token = UserSession(
            user_id=uuid.uuid4(),
            jti=str(uuid.uuid4()),
            expires_at=datetime.utcnow() + timedelta(days=7),
            is_active=True,
        )

        token.revoke()

        assert token.is_active is False
        assert token.revoked_at is not None
