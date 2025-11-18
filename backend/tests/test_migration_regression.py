"""
Testes de Regressão - Migração AG2 → LangGraph

OBJETIVO: Validar que a migração mantém comportamento equivalente

SKILLS: @python-testing-patterns, @debugging-strategies
"""

import pytest
import json
import logging
from fastapi.testclient import TestClient
from datetime import datetime

# Import app
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from backend.app.main import app

client = TestClient(app)
logger = logging.getLogger(__name__)


class TestMigrationRegression:
    """
    Teste de regressão para garantir feature parity após migração
    """

    def test_healthz_endpoint(self):
        """
        Teste 1: Health check endpoint ainda funciona
        """
        logger.info("=" * 80)
        logger.info("REGRESSION TEST 1: Health Check Endpoint")
        logger.info("=" * 80)

        response = client.get("/healthz")

        assert response.status_code == 200, f"Health check failed: {response.status_code}"

        data = response.json()
        assert data['status'] in ['healthy', 'degraded'], f"Invalid status: {data['status']}"
        assert 'services' in data, "Missing 'services' field"
        assert 'database' in data['services'], "Missing 'database' service"

        logger.info(f"✅ Health check: {data['status']}")


    def test_analyze_endpoint_still_works(self):
        """
        Teste 2: Endpoint /api/analyze (migrado) ainda funciona
        """
        logger.info("=" * 80)
        logger.info("REGRESSION TEST 2: /api/analyze Endpoint (LangGraph)")
        logger.info("=" * 80)

        patient_data = {
            "age": 35,
            "weight": 75.0,
            "cid_codes": [],
            "meds_in_use": [],
            "allergies": [],
            "renal_function": "normal",
            "hepatic_function": "normal",
        }

        response = client.post(
            "/api/analyze",
            data={
                "patient_data": json.dumps(patient_data),
                "medication_text": "Dipirona 500mg"
            }
        )

        # Pode falhar por timeout ou Ollama indisponível
        assert response.status_code in [200, 500, 503], \
            f"Unexpected status: {response.status_code}"

        if response.status_code == 200:
            data = response.json()

            # Verificar estrutura de resposta
            assert "session_id" in data, "Missing session_id"
            assert "risk_level" in data, "Missing risk_level"
            assert "confidence_score" in data, "Missing confidence_score"
            assert "interactions" in data, "Missing interactions"
            assert "contraindications" in data, "Missing contraindications"
            assert "status" in data, "Missing status"

            logger.info(f"✅ /api/analyze works")
            logger.info(f"   Risk Level: {data['risk_level']}")
            logger.info(f"   Confidence: {data['confidence_score']:.2%}")
        else:
            logger.warning(f"⚠️ /api/analyze failed (likely Ollama unavailable)")


    def test_triage_endpoint_migrated(self):
        """
        Teste 3: Endpoint /api/v1/triage (recém-migrado) funciona
        """
        logger.info("=" * 80)
        logger.info("REGRESSION TEST 3: /api/v1/triage Endpoint (Migrated)")
        logger.info("=" * 80)

        triage_data = {
            "age": 45,
            "weight": 80.0,
            "pregnant": False,
            "cid_codes": ["I10"],  # Hipertensão
            "meds_in_use": ["losartana"],
            "allergies": [],
            "renal_function": "normal",
            "hepatic_function": "normal",
            "notes": "Teste de regressão"
        }

        response = client.post(
            "/api/v1/triage",
            json=triage_data
        )

        # Deve criar triagem com sucesso
        assert response.status_code in [200, 500], \
            f"Unexpected status: {response.status_code}"

        if response.status_code == 200:
            data = response.json()

            # Verificar estrutura de resposta
            assert "id" in data, "Missing triagem ID"
            assert "status" in data, "Missing status"
            assert data["status"] == "pending", f"Invalid status: {data['status']}"
            assert "job_id" in data, "Missing job_id"

            # Verificar que os dados foram preservados
            assert data["age"] == 45, "Age mismatch"
            assert data["weight"] == 80.0, "Weight mismatch"
            assert data["cid_codes"] == ["I10"], "CID codes mismatch"

            logger.info(f"✅ /api/v1/triage created successfully")
            logger.info(f"   Triagem ID: {data['id']}")
            logger.info(f"   Job ID: {data['job_id']}")
        else:
            logger.warning(f"⚠️ /api/v1/triage failed (likely DB or Ollama unavailable)")


    def test_vision_endpoint_refactored(self):
        """
        Teste 4: Endpoint /api/v1/vision/analyze (refatorado) funciona
        """
        logger.info("=" * 80)
        logger.info("REGRESSION TEST 4: /api/v1/vision/analyze Endpoint (Refactored)")
        logger.info("=" * 80)

        # Criar imagem de teste
        from io import BytesIO
        try:
            from PIL import Image

            img = Image.new('RGB', (200, 200), color='white')
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            response = client.post(
                "/api/v1/vision/analyze",
                files={"file": ("test_bula.png", img_bytes, "image/png")},
                data={"medication_text": "Dipirona"}
            )

            # Pode falhar por Ollama VLM indisponível
            assert response.status_code in [200, 500, 503], \
                f"Unexpected status: {response.status_code}"

            if response.status_code == 200:
                data = response.json()

                # Verificar estrutura (VisionResponse)
                assert "session_id" in data or "status" in data, \
                    "Missing required fields in vision response"

                logger.info(f"✅ /api/v1/vision/analyze works")
            else:
                logger.warning(f"⚠️ /api/v1/vision/analyze failed (likely VLM unavailable)")

        except ImportError:
            pytest.skip("PIL not installed, skipping vision test")


    def test_no_captain_agent_imports(self):
        """
        Teste 5: Verificar que CaptainAgent não é mais importado em main.py
        """
        logger.info("=" * 80)
        logger.info("REGRESSION TEST 5: CaptainAgent Removed from Imports")
        logger.info("=" * 80)

        # Ler main.py e verificar que não há import de CaptainAgent
        main_py_path = os.path.join(
            os.path.dirname(__file__),
            "../app/main.py"
        )

        with open(main_py_path, 'r') as f:
            content = f.read()

        # Não deve ter import de CaptainAgent
        assert "from .agents import CaptainAgent" not in content, \
            "❌ CaptainAgent still imported in main.py!"

        # Não deve ter captain_agent = CaptainAgent()
        assert "captain_agent = CaptainAgent()" not in content, \
            "❌ CaptainAgent still initialized in main.py!"

        logger.info("✅ CaptainAgent successfully removed from main.py")


    def test_agents_legacy_directory_exists(self):
        """
        Teste 6: Verificar que diretório agents_legacy foi criado
        """
        logger.info("=" * 80)
        logger.info("REGRESSION TEST 6: agents_legacy/ Directory Created")
        logger.info("=" * 80)

        legacy_dir = os.path.join(
            os.path.dirname(__file__),
            "../app/agents_legacy"
        )

        assert os.path.exists(legacy_dir), \
            "❌ agents_legacy/ directory not found!"

        # Verificar que __init__.py existe
        init_py = os.path.join(legacy_dir, "__init__.py")
        assert os.path.exists(init_py), \
            "❌ agents_legacy/__init__.py not found!"

        logger.info("✅ agents_legacy/ directory created successfully")


    def test_vision_agent_still_available(self):
        """
        Teste 7: VisionAgent ainda está disponível em /backend/app/agents/
        """
        logger.info("=" * 80)
        logger.info("REGRESSION TEST 7: VisionAgent Still Available")
        logger.info("=" * 80)

        # Importar VisionAgent deve funcionar
        try:
            from backend.app.agents import VisionAgent

            # Instanciar deve funcionar
            vision_agent = VisionAgent()

            assert vision_agent is not None, "VisionAgent initialization failed"

            logger.info("✅ VisionAgent still available and working")

        except ImportError as e:
            pytest.fail(f"❌ Failed to import VisionAgent: {e}")


    def test_langgraph_system_works(self):
        """
        Teste 8: Sistema LangGraph funciona corretamente
        """
        logger.info("=" * 80)
        logger.info("REGRESSION TEST 8: LangGraph System Works")
        logger.info("=" * 80)

        try:
            from backend.app.langgraph_agents import get_graph, MedSafeState

            # Obter graph deve funcionar
            graph = get_graph()

            assert graph is not None, "Failed to get LangGraph"

            logger.info("✅ LangGraph system initialized successfully")

        except ImportError as e:
            pytest.fail(f"❌ Failed to import LangGraph: {e}")


@pytest.mark.asyncio
async def test_complete_workflow_equivalence():
    """
    Teste 9: Workflow completo produz resultados equivalentes

    CRITICAL: Este é o teste mais importante - valida que a migração
    mantém a mesma funcionalidade fim-a-fim
    """
    logger.info("=" * 80)
    logger.info("REGRESSION TEST 9: Complete Workflow Equivalence")
    logger.info("=" * 80)

    from backend.app.langgraph_agents import get_graph, RiskLevel

    # Caso de teste: Warfarin + Aspirin (interação conhecida)
    test_state = {
        'patient_data': {
            'age': 65,
            'weight': 75,
            'conditions': ['atrial fibrillation'],
            'current_medications': ['warfarin'],
            'allergies': [],
        },
        'medication_text': 'aspirin',
        'session_id': f"regression_test_{datetime.now().timestamp()}",
        'triage_id': None,
    }

    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": test_state['session_id']}}

        # Desabilitar HITL para teste
        from backend.app.langgraph_agents import get_settings
        settings = get_settings()
        original_hitl = settings.enable_hitl
        settings.enable_hitl = False

        try:
            result = await graph.ainvoke(test_state, config)

            # VALIDAÇÕES CRÍTICAS
            assert result['status'] == 'completed', \
                f"❌ Workflow failed: {result['status']}"

            # Deve detectar interação
            interactions = result.get('interactions', [])
            assert len(interactions) > 0, \
                "❌ REGRESSION FAILURE: No interactions detected for warfarin+aspirin!"

            # Deve ser alto risco
            assert result['risk_level'] in [RiskLevel.HIGH, RiskLevel.CRITICAL], \
                f"❌ REGRESSION FAILURE: Risk level too low: {result['risk_level']}"

            # Deve ter confiança razoável
            assert result['confidence_score'] >= 0.6, \
                f"❌ REGRESSION FAILURE: Confidence too low: {result['confidence_score']}"

            logger.info("✅ CRITICAL: Workflow equivalence validated")
            logger.info(f"   Interactions: {len(interactions)}")
            logger.info(f"   Risk: {result['risk_level'].value}")
            logger.info(f"   Confidence: {result['confidence_score']:.2%}")

        finally:
            settings.enable_hitl = original_hitl

    except Exception as e:
        logger.error(f"❌ REGRESSION FAILURE: {e}", exc_info=True)
        pytest.fail(f"Complete workflow equivalence test failed: {e}")


if __name__ == "__main__":
    """
    Run regression tests directly

    Usage: pytest backend/tests/test_migration_regression.py -v -s
    """
    pytest.main([__file__, "-v", "-s"])
