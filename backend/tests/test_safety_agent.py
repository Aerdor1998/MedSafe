"""
Unit tests for SafetyAgent

Tests safety guardrails, hallucination detection, and safety classification.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.app.langgraph_agents.state import RiskLevel


class TestSafetyAgentInit:
    """Tests for SafetyAgent initialization"""

    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_init_success(self, mock_logger, mock_settings, mock_ollama):
        """Test successful initialization"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()
        # Removed: optimization mock

        from backend.app.langgraph_agents.safety_agent import SafetyAgent

        agent = SafetyAgent()

        assert agent.agent_name == "SafetyAgent"


class TestSafetyAgentSystemPrompt:
    """Tests for system prompt"""

    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_get_system_prompt(self, mock_logger, mock_settings, mock_ollama):
        """Test system prompt contains required elements"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()
        # Removed: optimization mock

        from backend.app.langgraph_agents.safety_agent import SafetyAgent

        agent = SafetyAgent()
        prompt = agent.get_system_prompt()

        assert (
            "SafetyAgent" in prompt
            or "segurança" in prompt.lower()
            or "safety" in prompt.lower()
        )


class TestSafetyClassification:
    """Tests for safety classification logic"""

    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_classify_safe(self, mock_logger, mock_settings, mock_ollama):
        """Test classification with no violations"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()
        # Removed: optimization mock

        from backend.app.langgraph_agents.safety_agent import SafetyAgent
        from backend.app.langgraph_agents.state import SafetyClassification

        agent = SafetyAgent()

        state = {
            "risk_level": RiskLevel.LOW,
            "confidence_score": 0.9,
            "interactions": [],
            "contraindications": [],
        }
        violations = []

        classification = agent._classify_safety(state, violations)

        assert classification in [
            SafetyClassification.SAFE,
            SafetyClassification.NEEDS_REVIEW,
            SafetyClassification.BLOCKED,
        ]

    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_classify_with_violations(self, mock_logger, mock_settings, mock_ollama):
        """Test classification with safety violations"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()
        # Removed: optimization mock

        from backend.app.langgraph_agents.safety_agent import SafetyAgent
        from backend.app.langgraph_agents.state import SafetyClassification

        agent = SafetyAgent()

        state = {
            "risk_level": RiskLevel.CRITICAL,
            "confidence_score": 0.5,
            "interactions": [{"severity": "critical", "drug1": "A", "drug2": "B"}],
            "contraindications": [],
        }
        # Violations should be list of dicts
        violations = [
            {
                "type": "RISK_INCONSISTENCY",
                "severity": "critical",
                "message": "Critical risk level",
            },
            {"type": "CONFIDENCE", "severity": "high", "message": "Low confidence"},
        ]

        classification = agent._classify_safety(state, violations)

        # Critical risk with violations should result in NEEDS_REVIEW or BLOCKED
        assert classification in [
            SafetyClassification.NEEDS_REVIEW,
            SafetyClassification.BLOCKED,
        ]


class TestSafetyChecks:
    """Tests for safety check methods"""

    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_run_safety_checks(self, mock_logger, mock_settings, mock_ollama):
        """Test running safety checks on state"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()
        # Removed: optimization mock

        from backend.app.langgraph_agents.safety_agent import SafetyAgent

        agent = SafetyAgent()

        state = {
            "risk_level": RiskLevel.HIGH,
            "confidence_score": 0.6,
            "interactions": [{"severity": "high", "drug1": "A", "drug2": "B"}],
            "contraindications": [],
        }

        violations = agent._run_safety_checks(state)

        assert isinstance(violations, list)


class TestHITLEvaluation:
    """Tests for HITL need evaluation"""

    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_evaluate_hitl_need_critical(self, mock_logger, mock_settings, mock_ollama):
        """Test HITL evaluation for critical cases"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        # Add HITL-specific settings
        settings.enable_hitl = True
        settings.auto_escalate_critical = True
        settings.block_on_critical_violations = True
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()
        # Removed: optimization mock

        from backend.app.langgraph_agents.safety_agent import SafetyAgent

        agent = SafetyAgent()
        # Also set settings on the agent instance
        agent.settings = settings

        state = {
            "risk_level": RiskLevel.CRITICAL,
            "confidence_score": 0.9,
            "interactions": [],
            "contraindications": [],
        }
        # Violations should be list of dicts
        violations = [
            {
                "type": "CRITICAL_RISK",
                "severity": "critical",
                "message": "Critical risk level",
            }
        ]

        needs_hitl, reasons = agent._evaluate_hitl_need(state, violations)

        assert needs_hitl is True
        assert len(reasons) > 0

    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_critical_requires_review_even_with_hitl_disabled(
        self, mock_logger, mock_settings, mock_ollama
    ):
        """
        Regressão (pega pelo golden set eval): requires_human_review é
        informação CLÍNICA ("este caso precisa de um humano") e não pode
        ser zerada por enable_hitl=False, que é toggle de WORKFLOW — o
        gate de workflow já existe no worker (analysis_worker) e no grafo
        (should_escalate_to_hitl). Risco crítico deve reportar review=True
        mesmo com o HITL desligado.
        """
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        settings.enable_hitl = False  # workflow DESLIGADO
        settings.auto_escalate_critical = True
        settings.block_on_critical_violations = True
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()

        from backend.app.langgraph_agents.safety_agent import SafetyAgent

        agent = SafetyAgent()
        agent.settings = settings

        state = {
            "risk_level": RiskLevel.CRITICAL,
            "confidence_score": 0.9,
            "interactions": [],
            "contraindications": [],
        }

        needs_hitl, reasons = agent._evaluate_hitl_need(state, [])

        assert needs_hitl is True
        assert any("CRITICAL" in r for r in reasons)

    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_evaluate_hitl_need_safe(self, mock_logger, mock_settings, mock_ollama):
        """Test HITL evaluation for safe cases"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()
        # Removed: optimization mock

        from backend.app.langgraph_agents.safety_agent import SafetyAgent

        agent = SafetyAgent()

        state = {
            "risk_level": RiskLevel.LOW,
            "confidence_score": 0.95,
            "interactions": [],
            "contraindications": [],
        }
        violations = []

        needs_hitl, reasons = agent._evaluate_hitl_need(state, violations)

        # Low risk, high confidence, no violations - likely no HITL needed
        assert isinstance(needs_hitl, bool)


def _build_agent():
    """Helper: build a SafetyAgent with fully mocked base dependencies."""
    settings = MagicMock()
    settings.is_cloud_model = False
    settings.ollama_api_key = None
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_local_model = "qwen3:8b"
    settings.ollama_temperature = 0.7
    settings.ollama_max_tokens = 4096
    settings.effective_model_name = "qwen3:8b"
    settings.enable_hitl = True
    settings.auto_escalate_critical = True
    settings.block_on_critical_violations = True

    with (
        patch("backend.app.langgraph_agents.base_agent.ChatOllama"),
        patch(
            "backend.app.langgraph_agents.base_agent.get_settings",
            return_value=settings,
        ),
        patch(
            "backend.app.langgraph_agents.base_agent.get_agent_logger",
            return_value=MagicMock(),
        ),
    ):
        from backend.app.langgraph_agents.safety_agent import SafetyAgent

        agent = SafetyAgent()
        agent.settings = settings
        return agent


class TestRule4Recalibration:
    """
    Regressões da recalibração da Rule 4 (falsos alarmes estruturais).

    Contrato novo: escalar por confiança APENAS se confidence < 0.5 E houver
    sinal clínico (interações, contraindicações, ou risco >= MEDIUM).
    Análise vazia e benigna com confiança estruturalmente baixa NÃO deve
    pagear humano (alert fatigue). Calibrado contra o baseline real do
    golden set (evals/results/20260707T115030Z_qwen3_8b.json).
    """

    def test_moderate_confidence_low_risk_no_findings_no_review(self):
        """conf 0.62, risk low, sem achados → review False (Rule 4 antiga escalava)"""
        agent = _build_agent()
        state = {
            "risk_level": RiskLevel.LOW,
            "confidence_score": 0.62,
            "interactions": [],
            "contraindications": [],
        }

        needs_hitl, reasons = agent._evaluate_hitl_need(state, [])

        assert needs_hitl is False
        assert reasons == []

    def test_negative_control_medium_risk_one_interaction_no_review(self):
        """Controle negativo do golden set: conf 0.655, risk medium,
        1 interação → review False (conf >= 0.5, Rule 4 não dispara)"""
        agent = _build_agent()
        state = {
            "risk_level": RiskLevel.MEDIUM,
            "confidence_score": 0.655,
            "interactions": [{"severity": "low", "drug1": "A", "drug2": "B"}],
            "contraindications": [],
        }

        needs_hitl, reasons = agent._evaluate_hitl_need(state, [])

        assert needs_hitl is False
        assert reasons == []

    def test_very_low_confidence_with_interaction_escalates(self):
        """conf 0.45 (< 0.5) com 1 interação (sinal clínico) → review True"""
        agent = _build_agent()
        state = {
            "risk_level": RiskLevel.LOW,
            "confidence_score": 0.45,
            "interactions": [{"severity": "low", "drug1": "A", "drug2": "B"}],
            "contraindications": [],
        }

        needs_hitl, reasons = agent._evaluate_hitl_need(state, [])

        assert needs_hitl is True
        assert any("confidence" in r.lower() for r in reasons)

    def test_very_low_confidence_empty_benign_no_review(self):
        """Controle negativo do golden set: conf 0.425, sem achados,
        risk low → review False (sem sinal clínico, não pagear humano)"""
        agent = _build_agent()
        state = {
            "risk_level": RiskLevel.LOW,
            "confidence_score": 0.425,
            "interactions": [],
            "contraindications": [],
        }

        needs_hitl, reasons = agent._evaluate_hitl_need(state, [])

        assert needs_hitl is False
        assert reasons == []

    def test_very_low_confidence_medium_risk_no_findings_escalates(self):
        """conf < 0.5 com risco >= MEDIUM conta como sinal clínico"""
        agent = _build_agent()
        state = {
            "risk_level": RiskLevel.MEDIUM,
            "confidence_score": 0.45,
            "interactions": [],
            "contraindications": [],
        }

        needs_hitl, reasons = agent._evaluate_hitl_need(state, [])

        assert needs_hitl is True
        assert any("confidence" in r.lower() for r in reasons)

    def test_boundary_confidence_exactly_half_no_review(self):
        """Fronteira: conf == 0.5 exato, mesmo com sinal clínico (risk MEDIUM
        + 1 interação), NÃO escala — contrato é estritamente < 0.5.
        (Achado do painel adversarial: off-by-one no comparador.)"""
        agent = _build_agent()
        state = {
            "risk_level": RiskLevel.MEDIUM,
            "confidence_score": 0.5,
            "interactions": [{"severity": "low", "drug1": "A", "drug2": "B"}],
            "contraindications": [],
        }

        needs_hitl, reasons = agent._evaluate_hitl_need(state, [])

        assert needs_hitl is False
        assert not any("confidence" in r.lower() for r in reasons)


class TestRule5PregnancyField:
    """Regressão: patient_data['pregnant'] booleano (não condition string)
    deve contar como população vulnerável (golden set gestante-teratogenico)."""

    def test_pregnant_boolean_field_escalates(self):
        agent = _build_agent()
        state = {
            "risk_level": RiskLevel.LOW,
            "confidence_score": 0.9,
            "interactions": [],
            "contraindications": [],
            "patient_data": {"pregnant": True},
        }

        needs_hitl, reasons = agent._evaluate_hitl_need(state, [])

        assert needs_hitl is True
        assert any("pregnancy" in r.lower() for r in reasons)

    def test_pregnancy_condition_string_still_escalates(self):
        """Não pode regredir: condition string continua funcionando"""
        agent = _build_agent()
        state = {
            "risk_level": RiskLevel.LOW,
            "confidence_score": 0.9,
            "interactions": [],
            "contraindications": [],
            "patient_data": {"conditions": ["pregnancy"]},
        }

        needs_hitl, reasons = agent._evaluate_hitl_need(state, [])

        assert needs_hitl is True
        assert any("pregnancy" in r.lower() for r in reasons)


class TestFactoryFunction:
    """Tests for factory function"""

    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_create_safety_agent(self, mock_logger, mock_settings, mock_ollama):
        """Test factory function creates agent"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()
        # Removed: optimization mock

        from backend.app.langgraph_agents.safety_agent import (
            SafetyAgent,
            create_safety_agent,
        )

        agent = create_safety_agent()

        assert isinstance(agent, SafetyAgent)
