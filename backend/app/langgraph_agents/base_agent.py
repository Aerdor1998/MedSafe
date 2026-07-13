"""
Base Agent Class for MedSafe Multi-Agent System

PATTERN: Abstract base class with shared LLM integration (PDF pg 14-16)
SKILLS: @ultrathink, @code-review-excellence, @api-design-principles

All specialized agents inherit from this base to ensure:
- Consistent LLM interaction (Ollama medgemma:latest)
- Structured logging and observability
- Error handling and retry logic
- Prompt engineering best practices
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from ..utils.logging_config import get_agent_logger
from .config import get_settings
from .state import MedSafeState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all MedSafe agents

    ARCHITECTURE: Single Responsibility Principle (PDF pg 14-16)
    PATTERN: Each agent is a specialist with a clear, focused task

    SKILLS APPLIED:
    - @ultrathink: Clean, elegant agent abstraction
    - @code-review-excellence: Self-documenting with type hints
    - @api-design-principles: Consistent interface across agents
    """

    def __init__(self, agent_name: str):
        """
        Initialize base agent with Ollama LLM

        Args:
            agent_name: Unique identifier for this agent (e.g., "TriageAgent")
        """
        self.agent_name = agent_name
        self.settings = get_settings()

        # Get specialized agent logger
        self.agent_logger = get_agent_logger(agent_name)

        # Initialize Ollama ChatModel with fallback support
        # Primary: Cloud model via https://ollama.com
        # Fallback: Local model via http://ollama:11434
        self.use_cloud = self.settings.is_cloud_model and self.settings.ollama_api_key
        self.cloud_failed = False

        # Timeout is enforced at the underlying ollama.Client/AsyncClient (httpx)
        # level via client_kwargs, since ChatOllama itself has no timeout kwarg.
        client_kwargs = {"timeout": self.settings.ollama_timeout}

        if self.use_cloud:
            llm_kwargs = {
                "base_url": self.settings.effective_ollama_url,
                "model": self.settings.effective_model_name,
                "temperature": self.settings.ollama_temperature,
                "num_predict": self.settings.ollama_max_tokens,
                "headers": {"Authorization": f"Bearer {self.settings.ollama_api_key}"},
                "client_kwargs": client_kwargs,
            }
            logger.info(
                f"🌐 Primary: cloud model {self.settings.effective_model_name} "
                f"| Fallback: local model {self.settings.ollama_local_model}"
            )
        else:
            llm_kwargs = {
                "base_url": self.settings.ollama_base_url,
                "model": self.settings.ollama_local_model,
                "temperature": self.settings.ollama_temperature,
                "num_predict": self.settings.ollama_max_tokens,
                "client_kwargs": client_kwargs,
            }
            logger.info(
                f"🖥️ Using local model: {self.settings.ollama_local_model} "
                f"via {self.settings.ollama_base_url}"
            )

        self.llm = ChatOllama(**llm_kwargs)

        # Pre-create fallback LLM for cloud models
        if self.use_cloud:
            self.fallback_llm = ChatOllama(
                base_url=self.settings.ollama_base_url,
                model=self.settings.ollama_local_model,
                temperature=self.settings.ollama_temperature,
                num_predict=self.settings.ollama_max_tokens,
                client_kwargs=client_kwargs,
            )

        logger.info(
            f"🤖 {self.agent_name} initialized with "
            f"model={self.settings.effective_model_name}, "
            f"temp={self.settings.ollama_temperature}"
        )

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Return the system prompt defining this agent's role and behavior

        PATTERN: Prompt Engineering (PDF pg 14-16, 39-42)
        Each agent has a specialized system prompt that:
        - Defines its role and expertise
        - Sets behavioral guidelines (medical accuracy, safety-first)
        - Provides domain-specific instructions

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    def process(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Main processing method - each agent implements its logic here

        PATTERN: Think → Act → Observe (PDF pg 10-13)
        This method should:
        1. Read relevant fields from state
        2. Perform agent-specific analysis/task
        3. Return dict of state updates

        Args:
            state: Current MedSafeState

        Returns:
            Dictionary of state updates to merge
        """
        pass

    def invoke_llm(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Invoke Ollama LLM with proper prompt structure

        PATTERN: Structured prompting with context injection
        SKILL: @ultrathink - Clean LLM interaction abstraction

        Args:
            user_message: The main user/task message
            context: Optional context dict to inject into prompt
            system_prompt: Override default system prompt

        Returns:
            LLM response string
        """
        try:
            # Use agent's system prompt if not overridden
            if system_prompt is None:
                system_prompt = self.get_system_prompt()

            # Build context string if provided
            context_str = ""
            if context:
                context_str = "\n\n### CONTEXT ###\n"
                for key, value in context.items():
                    context_str += f"{key}: {value}\n"

            # Log LLM call
            self.agent_logger.llm_call(
                user_message,
                model=self.settings.effective_model_name,
                temperature=self.settings.ollama_temperature,
            )

            # Construct messages
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"{context_str}\n\n{user_message}"),
            ]

            # Invoke LLM with fallback support
            start_time = datetime.now()
            try:
                response = self.llm.invoke(messages)
            except Exception as cloud_error:
                # Check if this is a cloud limit/auth error and we have fallback
                error_msg = str(cloud_error).lower()
                if (
                    self.use_cloud
                    and hasattr(self, "fallback_llm")
                    and (
                        "403" in error_msg
                        or "401" in error_msg
                        or "limit" in error_msg
                        or "unauthorized" in error_msg
                    )
                ):
                    if not self.cloud_failed:
                        logger.warning(
                            f"Cloud model failed ({cloud_error}), switching to local fallback"
                        )
                        self.cloud_failed = True
                    response = self.fallback_llm.invoke(messages)
                else:
                    raise
            duration = (datetime.now() - start_time).total_seconds()

            # Extract content
            if hasattr(response, "content"):
                result = response.content
            else:
                result = str(response)

            # Log LLM response
            self.agent_logger.llm_response(
                result, duration, tokens=len(result.split()), chars=len(result)
            )

            # Warning if slow
            if duration > self.settings.warning_execution_time:
                logger.warning(
                    f" {self.agent_name} LLM call took {duration:.2f}s "
                    f"(threshold: {self.settings.warning_execution_time}s)"
                )

            return result

        except Exception as e:
            self.agent_logger.error(f"LLM call failed: {e}", exc_info=True)
            raise

    def log_step(self, state: MedSafeState, message: str):
        """
        Log agent execution step for observability

        PATTERN: Agent Ops - Execution Tracing (PDF pg 27-31)
        SKILL: @debugging-strategies - Comprehensive logging

        Args:
            state: Current state to update
            message: Log message
        """
        timestamp = datetime.now()
        step_entry = f"[{timestamp.isoformat()}] {self.agent_name}: {message}"

        logger.info(f"{step_entry}")

        # Add to state's agent_steps for traceability
        if "agent_steps" in state:
            state["agent_steps"].append(step_entry)

    def handle_error(
        self, state: MedSafeState, error: Exception, context: str = ""
    ) -> Dict[str, Any]:
        """
        Centralized error handling for agents

        PATTERN: Fail-safe error handling (PDF pg 34-38)
        SKILL: @debugging-strategies - Root cause analysis

        Args:
            state: Current state
            error: Exception that occurred
            context: Additional context about the error

        Returns:
            State updates with error information
        """
        error_message = f"{self.agent_name} error: {str(error)}"
        if context:
            error_message += f" | Context: {context}"

        logger.error(f"{error_message}", exc_info=True)

        return {
            "error": error_message,
            "status": "error",
            "agent_steps": [
                f"[{datetime.now().isoformat()}] ERROR in {self.agent_name}: {error}"
            ],
        }

    def validate_state(self, state: MedSafeState, required_fields: List[str]) -> bool:
        """
        Validate that required state fields are present

        PATTERN: Defensive programming (PDF pg 34-38)
        SKILL: @code-review-excellence - Input validation

        Args:
            state: State to validate
            required_fields: List of required field names

        Returns:
            True if valid, False otherwise
        """
        missing_fields = [field for field in required_fields if field not in state]

        if missing_fields:
            logger.error(
                f"{self.agent_name} validation failed: "
                f"missing fields {missing_fields}"
            )
            return False

        return True

    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"{self.agent_name}(model={self.settings.effective_model_name}, temp={self.settings.ollama_temperature})"
