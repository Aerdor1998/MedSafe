"""
Testes alinhados à versão LangGraph v2 da API (via HTTP).

Herméticos: dependências externas (Postgres/Redis/Ollama) mockadas na
fonte, com códigos de status exatos.
"""

from unittest.mock import AsyncMock, patch

import pytest


def test_healthz(client):
    """Deve responder saudável no probe principal (deps mockadas)."""
    with patch("backend.app.db.database.check_db_health", return_value=True), patch(
        "backend.app.utils.cache.check_redis_health", return_value=True
    ), patch(
        "backend.app.routers.health.check_ollama_health",
        new=AsyncMock(return_value=True),
    ):
        resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json().get("status") == "healthy"


def test_v2_health_model(client):
    """v2 health deve expor o modelo em uso."""
    resp = client.get("/api/v2/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "healthy"
    assert "model" in data


def test_analyze_legacy_accepts_request(client):
    """Endpoint legado /api/analyze deve responder (200/500 se model
    indisponível)."""
    pytest.skip(
        "Endpoint /api/analyze pode demorar (LLM); cobrir em suíte e2e "
        "com timeouts maiores."
    )


@pytest.mark.skip(reason="Rotas legacy de upload/busca removidas na versão atual.")
def test_legacy_routes_removed():
    pass


def test_login_accepts_reserved_tld_email(client):
    """Regressão: EmailStr rejeitava `admin@medsafe.local` (TLD reservado)
    com 422, bloqueando qualquer login do admin seedado.

    Formato de e-mail não deve ser validado no login (só igualdade);
    credencial errada deve retornar 401, nunca 422.
    """
    with patch("backend.app.routers.auth.get_db_context") as mock_ctx:
        db = mock_ctx.return_value.__enter__.return_value
        db.query.return_value.filter.return_value.first.return_value = None
        resp = client.post(
            "/api/v2/auth/login",
            json={"email": "admin@medsafe.local", "password": "senha-errada"},
        )
    assert resp.status_code == 401


def test_login_password_comparison_decides_outcome(client):
    """Regressão (discrimination sensor): mutante que inverte
    `user.verify_password(...)` no login deve ser morto — a comparação
    de senha na ROTA decide o resultado: errada 401, correta 200.
    """
    from backend.app.auth.rbac import UserRole
    from backend.app.db.user_models import User

    user = User(
        id=1,
        email="sensor@medsafe.local",
        password_hash=User.hash_password("senha-correta-sensor-123"),
        role=UserRole.ADMIN,
        is_active=True,
        failed_login_attempts=0,
    )

    with patch("backend.app.routers.auth.get_db_context") as mock_ctx:
        db = mock_ctx.return_value.__enter__.return_value
        db.query.return_value.filter.return_value.first.return_value = user

        wrong = client.post(
            "/api/v2/auth/login",
            json={
                "email": "sensor@medsafe.local",
                "password": "senha-errada",
            },
        )
        right = client.post(
            "/api/v2/auth/login",
            json={
                "email": "sensor@medsafe.local",
                "password": "senha-correta-sensor-123",
            },
        )

    assert wrong.status_code == 401
    assert right.status_code == 200
    assert right.json().get("access_token")
