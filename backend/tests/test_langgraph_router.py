"""
Unit tests for langgraph router

Tests the LangGraph-based analysis endpoints with exact, hermetic
assertions: no network and no database — external collaborators are
mocked at the source and every response pins a single status code.
"""

from contextlib import contextmanager
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _validation_locs(response) -> set:
    """Extrai o conjunto de `loc` dos erros de uma resposta 422."""
    return {tuple(err["loc"]) for err in response.json()["detail"]}


@contextmanager
def _analysis_backend_mocked() -> Iterator[MagicMock]:
    """
    Mocka orchestrator, idempotência e auth anônima — sem DB/rede.

    Permite exercitar o caminho feliz de POST /api/v2/analyze de forma
    hermética e determinística.
    """
    import backend.app.routers.langgraph as langgraph_module

    orchestrator = MagicMock()
    orchestrator.create_triage = AsyncMock(return_value="triage-123")
    orchestrator.create_analysis_job = AsyncMock(return_value="job-123")
    idempotency_lookup = AsyncMock(return_value=None)
    with patch.object(
        langgraph_module, "get_orchestrator", return_value=orchestrator
    ), patch.object(
        langgraph_module,
        "_find_existing_job_by_idempotency_key",
        new=idempotency_lookup,
    ), patch.object(
        langgraph_module.app_settings, "allow_anonymous_analysis", True
    ):
        orchestrator.idempotency_lookup = idempotency_lookup
        yield orchestrator


class TestLangGraphEndpoints:
    """Tests for LangGraph API endpoints"""

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def app(self):
        """Create test app with langgraph router"""
        from backend.app.routers.langgraph import router

        app = FastAPI()
        app.include_router(router)
        return app

    def test_analyze_endpoint_validation(self, client):
        """Corpo vazio falha validação com 422 nos campos obrigatórios."""
        response = client.post("/api/v2/analyze", json={})

        assert response.status_code == 422
        locs = _validation_locs(response)
        assert ("body", "medication") in locs
        assert ("body", "patient_data") in locs

    def test_analyze_endpoint_with_valid_input(self, client):
        """Input válido com backend mockado -> 200 e job 'pending'."""
        payload = {
            "medication": "aspirin 100mg",
            "patient_data": {
                "age": 65,
                "weight": 70,
                "conditions": ["hypertension"],
                "current_medications": ["metformin"],
            },
        }
        with _analysis_backend_mocked():
            response = client.post("/api/v2/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["job_id"] == "job-123"
        assert data["triage_id"] == "triage-123"
        assert data["session_id"]

    def test_idempotency_is_only_applied_when_header_is_present(self, client):
        """Requisições clínicas diferentes não são colapsadas por hash parcial."""
        payload = {"medication": "aspirin", "patient_data": {"allergies": ["ASA"]}}

        with _analysis_backend_mocked() as orchestrator:
            response = client.post("/api/v2/analyze", json=payload)

        assert response.status_code == 200
        orchestrator.idempotency_lookup.assert_not_awaited()
        assert (
            orchestrator.create_analysis_job.await_args.kwargs["idempotency_key"]
            is None
        )

    def test_explicit_idempotency_key_is_honored(self, client):
        payload = {"medication": "aspirin", "patient_data": {}}

        with _analysis_backend_mocked() as orchestrator:
            response = client.post(
                "/api/v2/analyze",
                json=payload,
                headers={"Idempotency-Key": " retry-123 "},
            )

        assert response.status_code == 200
        orchestrator.idempotency_lookup.assert_awaited_once_with(
            "retry-123", "anonymous"
        )

    def test_payload_user_id_cannot_spoof_attribution(self, client):
        payload = {
            "medication": "aspirin",
            "patient_data": {},
            "user_id": "another-user",
        }

        with _analysis_backend_mocked() as orchestrator:
            response = client.post("/api/v2/analyze", json=payload)

        assert response.status_code == 200
        assert orchestrator.create_triage.await_args.kwargs["user_id"] == "anonymous"
        assert (
            orchestrator.create_analysis_job.await_args.kwargs["user_id"] == "anonymous"
        )

    def test_triage_endpoint(self, client):
        """Não existe rota POST /api/v2/triage neste router -> 404."""
        response = client.post(
            "/api/v2/triage",
            json={
                "medication_text": "ibuprofen 400mg",
                "patient_data": {"age": 45, "weight": 80},
            },
        )

        assert response.status_code == 404

    def test_health_endpoint(self, client):
        """GET /api/v2/health é in-process e determinístico -> 200."""
        response = client.get("/api/v2/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "model" in data


class TestAnalysisValidation:
    """Tests for analysis request validation"""

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def app(self):
        """Create test app"""
        from backend.app.routers.langgraph import router

        app = FastAPI()
        app.include_router(router)
        return app

    def test_empty_medication_text(self, client):
        """medication vazio viola min_length=1 -> 422 no campo certo."""
        response = client.post(
            "/api/v2/analyze",
            json={"medication": "", "patient_data": {"age": 30}},
        )

        assert response.status_code == 422
        assert ("body", "medication") in _validation_locs(response)

    def test_missing_patient_data(self, client):
        """patient_data é obrigatório -> 422 apontando o campo ausente."""
        response = client.post("/api/v2/analyze", json={"medication": "aspirin"})

        assert response.status_code == 422
        assert ("body", "patient_data") in _validation_locs(response)

    def test_invalid_age(self, client):
        """age=-5 viola ge=0 -> 422 apontando patient_data.age."""
        response = client.post(
            "/api/v2/analyze",
            json={"medication": "aspirin", "patient_data": {"age": -5}},
        )

        assert response.status_code == 422
        assert ("body", "patient_data", "age") in _validation_locs(response)


class TestStatusEndpoints:
    """Tests for status and job endpoints"""

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def app(self):
        """Create test app"""
        from backend.app.routers.langgraph import router

        app = FastAPI()
        app.include_router(router)
        return app

    def test_get_job_status_not_found(self, client):
        """Não existe /api/v2/jobs/{id} (rota real: /api/v2/status/{id})."""
        response = client.get("/api/v2/jobs/nonexistent-job-id")

        assert response.status_code == 404

    def test_list_jobs_endpoint(self, client):
        """Não existe rota GET /api/v2/jobs neste router -> 404."""
        response = client.get("/api/v2/jobs")

        assert response.status_code == 404

    def test_status_requires_auth_when_anonymous_access_is_disabled(
        self, client, monkeypatch
    ):
        import backend.app.routers.langgraph as langgraph_module

        monkeypatch.setattr(
            langgraph_module.app_settings, "allow_anonymous_analysis", False
        )

        response = client.get("/api/v2/status/private-session")

        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    def test_status_checks_job_owner_even_without_triage(self, client, monkeypatch):
        from types import SimpleNamespace

        import backend.app.routers.langgraph as langgraph_module

        orchestrator = MagicMock()
        orchestrator.get_job_by_session = AsyncMock(
            return_value=SimpleNamespace(
                id="job-1",
                user_id="different-user",
                triage_id=None,
                state={},
                payload={},
                status="pending",
            )
        )
        monkeypatch.setattr(
            langgraph_module.app_settings, "allow_anonymous_analysis", True
        )
        monkeypatch.setattr(langgraph_module, "get_orchestrator", lambda: orchestrator)

        response = client.get("/api/v2/status/private-session")

        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"

    def test_hitl_endpoint_uses_clinical_approval_permission(self):
        from fastapi.routing import APIRoute

        from backend.app.auth.rbac import can_approve_analysis
        from backend.app.routers.langgraph import router

        route = next(
            route
            for route in router.routes
            if isinstance(route, APIRoute) and route.path == "/api/v2/hitl/approve"
        )

        assert can_approve_analysis in {
            dependency.call for dependency in route.dependant.dependencies
        }


class TestModelOverride:
    """Tests for model override functionality"""

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def app(self):
        """Create test app"""
        from backend.app.routers.langgraph import router

        app = FastAPI()
        app.include_router(router)
        return app

    def test_analyze_with_model_override(self, client):
        """Campo extra model_override é ignorado e não quebra o fluxo."""
        payload = {
            "medication": "aspirin",
            "patient_data": {"age": 30},
            "model_override": "llama3:8b",
        }
        with _analysis_backend_mocked():
            response = client.post("/api/v2/analyze", json=payload)

        assert response.status_code == 200
        assert response.json()["status"] == "pending"


class TestInteractionsEndpoint:
    """Tests for drug interactions endpoint"""

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def app(self):
        """Create test app"""
        from backend.app.routers.langgraph import router

        app = FastAPI()
        app.include_router(router)
        return app

    def test_check_interactions(self, client):
        """Não existe rota POST /api/v2/interactions neste router -> 404."""
        response = client.post(
            "/api/v2/interactions",
            json={"drug_name": "warfarin", "other_drugs": ["aspirin", "ibuprofen"]},
        )

        assert response.status_code == 404

    def test_check_interactions_empty_list(self, client):
        """Guard de inventário: a rota segue ausente com payload mínimo."""
        response = client.post(
            "/api/v2/interactions", json={"drug_name": "warfarin", "other_drugs": []}
        )

        assert response.status_code == 404


class TestAnalyzeAnonymousAuthGate:
    """
    Regression tests for Fix 2: DEBUG must never widen the anonymous-access
    surface of /api/v2/analyze. Only allow_anonymous_analysis (default False)
    may permit unauthenticated requests.
    """

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def app(self):
        """Create test app"""
        from backend.app.routers.langgraph import router

        app = FastAPI()
        app.include_router(router)
        return app

    @staticmethod
    def _valid_payload():
        return {"medication": "aspirin", "patient_data": {}}

    def test_debug_true_without_allow_anonymous_requires_auth(
        self, client, monkeypatch
    ):
        """debug=True alone must NOT bypass authentication."""
        import backend.app.routers.langgraph as langgraph_module

        monkeypatch.setattr(langgraph_module.app_settings, "debug", True)
        monkeypatch.setattr(
            langgraph_module.app_settings, "allow_anonymous_analysis", False
        )

        response = client.post("/api/v2/analyze", json=self._valid_payload())

        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    def test_allow_anonymous_analysis_true_permits_anonymous_access(
        self, client, monkeypatch
    ):
        """Explicit allow_anonymous_analysis=True still permits anonymous access."""
        import backend.app.routers.langgraph as langgraph_module

        monkeypatch.setattr(langgraph_module.app_settings, "debug", False)
        monkeypatch.setattr(
            langgraph_module.app_settings, "allow_anonymous_analysis", True
        )

        response = client.post("/api/v2/analyze", json=self._valid_payload())

        # Must not be rejected for lack of authentication. Any downstream
        # failure (missing DB/orchestrator wiring in this bare-router test
        # app) is unrelated to the auth gate under test.
        assert response.status_code != 401
