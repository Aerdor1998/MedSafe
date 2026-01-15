"""
Teste de integração mínimo: healthz.
"""

def test_healthz_up(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
