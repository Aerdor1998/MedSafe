"""
Testes de smoke para o serviço de IA (versão atual via HTTP).
"""


def test_v2_health_returns_cloud_model(client):
    resp = client.get("/api/v2/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "healthy"
    assert isinstance(data.get("model"), str)
    assert data.get("model")
