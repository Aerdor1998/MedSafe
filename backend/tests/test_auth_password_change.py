"""Public API tests for authenticated password rotation."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


def test_password_change_fails_closed_when_access_token_cannot_be_revoked(app, client):
    """A password must not change while the current token remains usable."""
    from backend.app.auth.jwt import get_current_user
    from backend.app.routers import auth as auth_module

    user = SimpleNamespace(
        email="doctor@example.com",
        password_hash="original-hash",
        role=SimpleNamespace(value="physician"),
        verify_password=MagicMock(side_effect=[True, False]),
    )
    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = user
    query.all.return_value = []
    db = MagicMock()
    db.query.return_value = query

    @contextmanager
    def db_context():
        yield db

    token_payload = {
        "jti": "access-jti",
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()),
    }
    app.dependency_overrides[get_current_user] = lambda: "user-1"
    try:
        with patch.object(
            auth_module, "get_db_context", return_value=db_context()
        ), patch(
            "backend.app.auth.jwt.verify_token", return_value=token_payload
        ), patch.object(
            auth_module, "revoke_token", AsyncMock(return_value=False)
        ), patch.object(
            auth_module.audit_logger, "log", AsyncMock()
        ):
            response = client.post(
                "/api/v2/auth/change-password",
                headers={"Authorization": "Bearer test-access-token"},
                json={
                    "current_password": "correct-current-password",
                    "new_password": "different-secure-password",
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 503
    assert response.json()["detail"] == "Token revocation unavailable"
    assert user.password_hash == "original-hash"
    db.commit.assert_not_called()
