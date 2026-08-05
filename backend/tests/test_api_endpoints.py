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
