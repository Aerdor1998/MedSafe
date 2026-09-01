"""Regressão: LLM indisponível nunca pode liberar prescrição sem revisão humana."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from backend.app.utils.logging_config import AgentLogger


def test_agent_logger_error_accepts_exc_info_true():
    log = AgentLogger("test", logging.getLogger("t"))
    log.logger.handle = MagicMock()
    try:
        raise ValueError("boom")
    except ValueError:
        log.error("falhou", exc_info=True)  # antes: TypeError em makeRecord
    record = log.logger.handle.call_args[0][0]
    assert record.exc_info is not None and record.exc_info[0] is ValueError


def test_agent_logger_error_exc_info_true_without_exception():
    log = AgentLogger("test", logging.getLogger("t"))
    log.logger.handle = MagicMock()
    log.error("sem exceção ativa", exc_info=True)
    assert log.logger.handle.call_args[0][0].exc_info is None


@patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
@patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
@patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
@patch("backend.app.langgraph_agents.base_agent.ChatOllama")
def test_llm_failure_forces_human_review(mock_ollama, mock_vs, mock_rules, mock_int):
    from backend.app.langgraph_agents.clinical_agent import ClinicalAgent

    mock_ollama.return_value = MagicMock()
    mock_vs.return_value = None
    mock_rules.return_value = MagicMock()
    mock_int.return_value = MagicMock()
    agent = ClinicalAgent()
    agent._run_openfda_sync = MagicMock(return_value=[])
    agent._get_rag_evidence = MagicMock(return_value="")
    # Sem interações conhecidas: cenário onde o fallback dizia "baixo risco"
    agent.interaction_service.check_interactions = MagicMock(return_value=[])
    agent.rules_engine.evaluate = MagicMock(return_value=[])
    agent.rules_engine.check_escalation_needed = MagicMock(return_value=(False, []))
    agent._generate_recommendations = MagicMock(
        side_effect=ConnectionError("Ollama down")
    )

    state = {
        "medication_text": "varfarina, amiodarona",
        "medications": ["varfarina", "amiodarona"],
        "patient_data": {"age": 70},
        "interactions": [],
        "contraindications": [],
        "analysis_metadata": {},
    }
    result = agent.process(state)

    assert result["requires_human_review"] is True
    assert result["status"] == "analyzed_partial"
    assert any("LLM indisponível" in r for r in result["escalation_reasons"])
    meta = result.get("analysis_metadata", {})
    assert meta.get("fallback_triggered") is True
    assert meta.get("partial_analysis") is True
