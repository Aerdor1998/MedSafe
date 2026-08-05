"""
Teste de integração mínimo: healthz.

Hermético: valida roteamento e wiring do app sem serviços externos
(DB/Redis/Ollama mockados na fonte).
"""

from unittest.mock import AsyncMock, patch


def test_healthz_up(client):
    with patch("backend.app.db.database.check_db_health", return_value=True), patch(
        "backend.app.utils.cache.check_redis_health", return_value=True
    ), patch(
        "backend.app.routers.health.check_ollama_health",
        new=AsyncMock(return_value=True),
    ):
        resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json().get("status") == "healthy"
