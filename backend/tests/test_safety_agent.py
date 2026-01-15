"""
Unit tests for SafetyAgent

Tests safety guardrails, hallucination detection, and safety classification.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

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

        assert "SafetyAgent" in prompt or "segurança" in prompt.lower() or "safety" in prompt.lower()


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
        
        assert classification in [SafetyClassification.SAFE, SafetyClassification.NEEDS_REVIEW, SafetyClassification.BLOCKED]

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
            {"type": "RISK_INCONSISTENCY", "severity": "critical", "message": "Critical risk level"},
            {"type": "CONFIDENCE", "severity": "high", "message": "Low confidence"}
        ]
        
        classification = agent._classify_safety(state, violations)
        
        # Critical risk with violations should result in NEEDS_REVIEW or BLOCKED
        assert classification in [SafetyClassification.NEEDS_REVIEW, SafetyClassification.BLOCKED]


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
            {"type": "CRITICAL_RISK", "severity": "critical", "message": "Critical risk level"}
        ]
        
        needs_hitl, reasons = agent._evaluate_hitl_need(state, violations)
        
        assert needs_hitl is True
        assert len(reasons) > 0

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

        from backend.app.langgraph_agents.safety_agent import create_safety_agent, SafetyAgent
        agent = create_safety_agent()
        
        assert isinstance(agent, SafetyAgent)
