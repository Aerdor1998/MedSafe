"""Golden set do fluxo clínico (caminho determinístico, LLM indisponível).

Garante que trocas de regras/prompt/modelo não regridam os casos conhecidos.
Cada caso em golden/clinical_cases.json declara só o que é invariante.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

CASES = json.loads(
    (Path(__file__).parent / "golden" / "clinical_cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture(scope="module")
def agent():
    with patch(
        "backend.app.langgraph_agents.clinical_agent.get_vector_store",
        return_value=None,
    ), patch(
        "backend.app.langgraph_agents.base_agent.ChatOllama", return_value=MagicMock()
    ):
        from backend.app.langgraph_agents.clinical_agent import ClinicalAgent

        a = ClinicalAgent()
    a._run_openfda_sync = MagicMock(return_value=[])
    a._get_rag_evidence = MagicMock(return_value="")
    a._generate_recommendations = MagicMock(side_effect=ConnectionError("LLM offline"))
    return a


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_golden_case(agent, case):
    result = agent.process(
        {
            "medication_text": ", ".join(case["medications"]),
            "medications": case["medications"],
            "patient_data": case["patient"],
            "interactions": [],
            "contraindications": [],
            "analysis_metadata": {},
        }
    )
    exp = case["expect"]
    # Invariante global: sem LLM, nunca libera sem revisão humana.
    assert result["requires_human_review"] is True
    n_int = len(result.get("interactions") or [])
    if "risk_level" in exp:
        assert str(result["risk_level"]).split(".")[-1] == exp["risk_level"]
    if "min_interactions" in exp:
        assert n_int >= exp["min_interactions"]
    if "max_interactions" in exp:
        assert n_int <= exp["max_interactions"]
    if "reason_contains" in exp:
        assert any(exp["reason_contains"] in r for r in result["escalation_reasons"])
