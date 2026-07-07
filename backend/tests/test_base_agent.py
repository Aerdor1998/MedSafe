"""
Unit tests for BaseAgent

Tests the abstract base class functionality for all MedSafe agents.
"""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.app.langgraph_agents.base_agent import BaseAgent
from backend.app.langgraph_agents.state import MedSafeState


class ConcreteAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing"""

    def get_system_prompt(self) -> str:
        return "Test system prompt for ConcreteAgent"

    def process(self, state: MedSafeState) -> dict:
        return {"processed": True}


class TestBaseAgentInit:
    """Tests for BaseAgent initialization"""

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_init_local_model(self, mock_logger, mock_settings, mock_ollama):
        """Test initialization with local model"""
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

        agent = ConcreteAgent("TestAgent")

        assert agent.agent_name == "TestAgent"
        assert agent.use_cloud is False
        mock_ollama.assert_called()

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_init_local_model_configures_client_timeout(
        self, mock_logger, mock_settings, mock_ollama
    ):
        """
        Fix 1 regression: ollama_timeout must actually reach ChatOllama, via
        client_kwargs={"timeout": ...} forwarded to the underlying
        ollama.Client/AsyncClient (httpx), since ChatOllama itself has no
        top-level timeout kwarg.
        """
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        settings.ollama_timeout = 42
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()

        ConcreteAgent("TestAgent")

        _, kwargs = mock_ollama.call_args
        assert kwargs.get("client_kwargs") == {"timeout": 42}

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_init_cloud_model(self, mock_logger, mock_settings, mock_ollama):
        """Test initialization with cloud model"""
        settings = MagicMock()
        settings.is_cloud_model = True
        settings.ollama_api_key = "test-api-key"
        settings.effective_ollama_url = "https://api.ollama.com"
        settings.effective_model_name = "gpt-oss:120b-cloud"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()

        agent = ConcreteAgent("TestAgent")

        assert agent.agent_name == "TestAgent"
        # use_cloud is True when is_cloud_model AND ollama_api_key are truthy
        # The agent stores the api key string in use_cloud, so just check it's truthy
        assert agent.use_cloud  # Should be truthy
        assert hasattr(agent, "fallback_llm")

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_init_cloud_model_configures_client_timeout_on_both_llms(
        self, mock_logger, mock_settings, mock_ollama
    ):
        """Fix 1: both the primary (cloud) and fallback (local) ChatOllama
        instances must receive the configured client timeout."""
        settings = MagicMock()
        settings.is_cloud_model = True
        settings.ollama_api_key = "test-api-key"
        settings.effective_ollama_url = "https://api.ollama.com"
        settings.effective_model_name = "gpt-oss:120b-cloud"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.ollama_timeout = 17
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()
        mock_ollama.return_value = MagicMock()

        ConcreteAgent("TestAgent")

        assert mock_ollama.call_count == 2
        for call in mock_ollama.call_args_list:
            assert call.kwargs.get("client_kwargs") == {"timeout": 17}


class TestBaseAgentAbstractMethods:
    """Tests for abstract method implementations"""

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_get_system_prompt(self, mock_logger, mock_settings, mock_ollama):
        """Test get_system_prompt returns expected value"""
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

        agent = ConcreteAgent("TestAgent")
        prompt = agent.get_system_prompt()

        assert "Test system prompt" in prompt

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_process(self, mock_logger, mock_settings, mock_ollama):
        """Test process method"""
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

        agent = ConcreteAgent("TestAgent")
        state = {"medication_text": "aspirin", "patient_data": {}}
        result = agent.process(state)

        assert result == {"processed": True}


class TestInvokeLLM:
    """Tests for invoke_llm method"""

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_invoke_llm_success(self, mock_logger, mock_settings, mock_ollama):
        """Test successful LLM invocation"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        settings.warning_execution_time = 30
        mock_settings.return_value = settings

        mock_agent_logger = MagicMock()
        mock_logger.return_value = mock_agent_logger

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Test response from LLM"
        mock_llm.invoke.return_value = mock_response
        mock_ollama.return_value = mock_llm

        agent = ConcreteAgent("TestAgent")
        result = agent.invoke_llm("Test message")

        assert result == "Test response from LLM"
        mock_agent_logger.llm_call.assert_called()
        mock_agent_logger.llm_response.assert_called()

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_invoke_llm_with_context(self, mock_logger, mock_settings, mock_ollama):
        """Test LLM invocation with context"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        settings.warning_execution_time = 30
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Response with context"
        mock_llm.invoke.return_value = mock_response
        mock_ollama.return_value = mock_llm

        agent = ConcreteAgent("TestAgent")
        context = {"patient_age": 65, "medication": "aspirin"}
        result = agent.invoke_llm("Analyze this patient", context=context)

        assert result == "Response with context"

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_invoke_llm_cloud_fallback(self, mock_logger, mock_settings, mock_ollama):
        """Test LLM fallback when cloud model fails"""
        settings = MagicMock()
        settings.is_cloud_model = True
        settings.ollama_api_key = "test-key"
        settings.effective_ollama_url = "https://api.ollama.com"
        settings.effective_model_name = "gpt-oss:120b"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.warning_execution_time = 30
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()

        # Cloud LLM fails with 403
        mock_cloud_llm = MagicMock()
        mock_cloud_llm.invoke.side_effect = Exception(
            "403 Forbidden - rate limit exceeded"
        )

        # Fallback LLM succeeds
        mock_fallback_llm = MagicMock()
        mock_fallback_response = MagicMock()
        mock_fallback_response.content = "Fallback response"
        mock_fallback_llm.invoke.return_value = mock_fallback_response

        mock_ollama.side_effect = [mock_cloud_llm, mock_fallback_llm]

        agent = ConcreteAgent("TestAgent")
        result = agent.invoke_llm("Test message")

        assert result == "Fallback response"
        assert agent.cloud_failed is True

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_invoke_llm_error_propagation(
        self, mock_logger, mock_settings, mock_ollama
    ):
        """Test LLM error is propagated when not a fallback case"""
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        settings.warning_execution_time = 30
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("Connection error")
        mock_ollama.return_value = mock_llm

        agent = ConcreteAgent("TestAgent")

        with pytest.raises(Exception, match="Connection error"):
            agent.invoke_llm("Test message")

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_invoke_llm_timeout_raises_and_does_not_hang(
        self, mock_logger, mock_settings, mock_ollama
    ):
        """
        Fix 1 regression: when the Ollama call exceeds the configured
        timeout (simulated here as the httpx timeout error the ollama
        client raises), invoke_llm must surface the failure as a normal
        exception -- not hang -- so callers can route it through
        handle_error like any other LLM failure.
        """
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        settings.warning_execution_time = 30
        settings.ollama_timeout = 0.2  # small timeout for a fast test
        mock_settings.return_value = settings
        mock_logger.return_value = MagicMock()

        mock_llm = MagicMock()

        def _simulate_timeout(*args, **kwargs):
            # Stand-in for the real httpx.ReadTimeout the ollama client
            # raises once client_kwargs={"timeout": ...} actually fires.
            time.sleep(0.05)
            raise httpx.ReadTimeout("Request timed out")

        mock_llm.invoke.side_effect = _simulate_timeout
        mock_ollama.return_value = mock_llm

        agent = ConcreteAgent("TestAgent")

        start = time.monotonic()
        with pytest.raises(httpx.ReadTimeout):
            agent.invoke_llm("Test message")
        elapsed = time.monotonic() - start

        # Generous bound to keep the test robust while still proving the
        # call fails fast instead of hanging indefinitely.
        assert elapsed < 5.0

        # Existing subclasses wrap invoke_llm calls and route failures to
        # handle_error -- confirm that hand-off still works for this error.
        state = {}
        result = agent.handle_error(state, httpx.ReadTimeout("Request timed out"))
        assert result["status"] == "error"
        assert "TestAgent" in result["error"]


class TestLogStep:
    """Tests for log_step method"""

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_log_step_adds_to_state(self, mock_logger, mock_settings, mock_ollama):
        """Test log_step adds entry to state's agent_steps"""
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

        agent = ConcreteAgent("TestAgent")
        state = {"agent_steps": []}

        agent.log_step(state, "Processing started")

        assert len(state["agent_steps"]) == 1
        assert "TestAgent" in state["agent_steps"][0]
        assert "Processing started" in state["agent_steps"][0]


class TestHandleError:
    """Tests for handle_error method"""

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_handle_error_returns_error_state(
        self, mock_logger, mock_settings, mock_ollama
    ):
        """Test handle_error returns proper error state"""
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

        agent = ConcreteAgent("TestAgent")
        state = {}
        error = Exception("Test error")

        result = agent.handle_error(state, error, "During processing")

        assert "error" in result
        assert "TestAgent" in result["error"]
        assert "Test error" in result["error"]
        assert result["status"] == "error"

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_handle_error_includes_context(
        self, mock_logger, mock_settings, mock_ollama
    ):
        """Test handle_error includes context in message"""
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

        agent = ConcreteAgent("TestAgent")
        state = {}
        error = Exception("Test error")

        result = agent.handle_error(state, error, "Drug interaction check")

        assert "Drug interaction check" in result["error"]


class TestValidateState:
    """Tests for validate_state method"""

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_validate_state_valid(self, mock_logger, mock_settings, mock_ollama):
        """Test validate_state with valid state"""
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

        agent = ConcreteAgent("TestAgent")
        state = {"medication_text": "aspirin", "patient_data": {}}

        result = agent.validate_state(state, ["medication_text", "patient_data"])

        assert result is True

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_validate_state_invalid(self, mock_logger, mock_settings, mock_ollama):
        """Test validate_state with missing fields"""
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

        agent = ConcreteAgent("TestAgent")
        state = {"medication_text": "aspirin"}

        result = agent.validate_state(state, ["medication_text", "patient_data"])

        assert result is False


class TestRepr:
    """Tests for __repr__ method"""

    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    @patch("backend.app.langgraph_agents.base_agent.get_settings")
    @patch("backend.app.langgraph_agents.base_agent.get_agent_logger")
    def test_repr(self, mock_logger, mock_settings, mock_ollama):
        """Test string representation"""
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

        agent = ConcreteAgent("TestAgent")

        repr_str = repr(agent)

        assert "TestAgent" in repr_str
        assert "qwen3:8b" in repr_str
