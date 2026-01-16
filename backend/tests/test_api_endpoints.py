"""
Testes alinhados à versão LangGraph v2 da API (via HTTP).
"""

import json

import pytest


def test_healthz(client):
    """Deve responder saudável no probe principal."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in {"healthy", "degraded"}


def test_v2_health_model(client):
    """v2 health deve expor o modelo em uso."""
    resp = client.get("/api/v2/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "healthy"
    assert "model" in data


def test_analyze_legacy_accepts_request(client):
    """Endpoint legado /api/analyze deve responder (200 ou 500 em caso de model indisponível)."""
    pytest.skip(
        "Endpoint /api/analyze pode demorar (LLM); cobrir em suíte e2e com timeouts maiores."
    )


@pytest.mark.skip(reason="Rotas legacy de upload/busca removidas na versão atual.")
def test_legacy_routes_removed():
    pass
