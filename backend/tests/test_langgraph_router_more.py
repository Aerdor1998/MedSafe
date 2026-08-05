"""
Additional tests for LangGraph router (full app)

Usa as rotas reais montadas em backend.app.main — o prefixo do router é
/api/v2 (NÃO existe prefixo /api/v2/langgraph). Asserts exatos e
herméticos: nenhuma chamada externa e nenhum código 500 aceito.
"""

import pytest
from fastapi.testclient import TestClient


def _validation_locs(response) -> set:
    """Extrai o conjunto de `loc` dos erros de uma resposta 422."""
    return {tuple(err["loc"]) for err in response.json()["detail"]}


class TestLangGraphRouterSetup:
    """Tests for LangGraph router setup"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.app.main import app

        return TestClient(app)

    def test_router_is_mounted(self, client):
        """GET /api/v2/health responde 200 — router montado no app."""
        response = client.get("/api/v2/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_analyze_endpoint_exists(self, client):
        """POST /api/v2/analyze existe: corpo vazio falha validação (422)."""
        response = client.post("/api/v2/analyze", json={})

        assert response.status_code == 422
        locs = _validation_locs(response)
        assert ("body", "medication") in locs
        assert ("body", "patient_data") in locs

    def test_triage_route_absent(self, client):
        """
        Não existe POST /api/v2/triage no app.

        O mount StaticFiles em "/" (html=True) captura caminhos
        desconhecidos e só aceita GET/HEAD, logo POST -> 405.
        """
        response = client.post(
            "/api/v2/triage",
            json={"symptoms": ["headache"], "patient_info": {}},
        )

        assert response.status_code == 405


class TestLangGraphHealthEndpoint:
    """Tests for health endpoint"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.app.main import app

        return TestClient(app)

    def test_health_returns_json(self, client):
        """Health endpoint retorna JSON com status e modelo em uso."""
        response = client.get("/api/v2/health")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert data["status"] == "healthy"
        assert "model" in data


class TestLangGraphInputValidation:
    """Tests for input validation"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.app.main import app

        return TestClient(app)

    def test_empty_body_rejected(self, client):
        """Corpo vazio é rejeitado pela validação com 422."""
        response = client.post("/api/v2/analyze", json={})

        assert response.status_code == 422
        assert ("body", "medication") in _validation_locs(response)

    def test_missing_medications_rejected(self, client):
        """medication ausente -> 422 apontando o campo obrigatório."""
        response = client.post("/api/v2/analyze", json={"patient_data": {"age": 30}})

        assert response.status_code == 422
        assert ("body", "medication") in _validation_locs(response)
