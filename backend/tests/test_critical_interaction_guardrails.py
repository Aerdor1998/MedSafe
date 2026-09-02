"""
Regression: interações críticas conhecidas nunca podem sair com risco rebaixado.

Bug original (task #4): varfarina+aspirina retornava risco "low" porque as
regras clínicas determinísticas só rodavam como fallback e evidência fraca de
RAG/OpenFDA as suprimia; o SafetyAgent registrava RISK_INCONSISTENCY mas não
corrigia o laudo final.

Cobre as 3 camadas da correção:
1. DrugInteractionService._check_known_clinical_rules — matching canônico
   bilateral (PT/EN/marcas) + expansão de classes, sempre disponível.
2. ClinicalAgent._analyze_interactions — regras determinísticas SEMPRE
   executam e a deduplicação preserva a maior severidade por par.
3. SafetyAgent.process — hard guardrail: o risco final nunca fica abaixo da
   maior severidade encontrada nos achados (floor + escalação HITL).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Env mínimo ANTES de qualquer import de backend.app (config valida no import)
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-minimum-32-characters-long")
os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://medsafe:test_password@localhost:5432/medsafe"
)


@pytest.fixture(scope="module")
def service():
    """Service real (sem LLM): camada determinística não depende de rede."""
    from backend.app.services.drug_interactions import DrugInteractionService

    return DrugInteractionService()


# ---------------------------------------------------------------------------
# Camada 1: regras clínicas determinísticas
# ---------------------------------------------------------------------------


class TestKnownClinicalRules:
    def test_pt_pair_is_critical(self, service):
        results = service._check_known_clinical_rules("aspirina", ["varfarina"])
        assert results, "varfarina+aspirina deve casar com regra crítica"
        assert results[0]["severity"] == "critical"

    def test_bilateral_matching(self, service):
        results = service._check_known_clinical_rules("varfarina", ["aspirina"])
        assert results, "matching deve ser bilateral (ordem não importa)"
        assert results[0]["severity"] == "critical"

    @pytest.mark.parametrize(
        ("drug", "other"),
        [
            ("AAS", "varfarina"),
            ("aspirina", "Marevan"),
            ("aspirin", "warfarin"),
            ("AAS", "Coumadin"),
            ("ácido acetilsalicílico", "varfarina"),
        ],
    )
    def test_synonyms_and_brands_match(self, service, drug, other):
        results = service._check_known_clinical_rules(drug, [other])
        assert results, f"{drug}+{other} deveria casar com a regra canônica"
        assert results[0]["severity"] == "critical"

    def test_class_expansion_nsaids(self, service):
        results = service._check_known_clinical_rules("ibuprofeno", ["varfarina"])
        assert results, "expansão de classe (AINEs) deveria casar com varfarina"
        assert results[0]["severity"] in {"critical", "high"}

    def test_negative_control_stays_silent(self, service):
        assert service._check_known_clinical_rules("paracetamol", ["metformina"]) == []

    def test_every_canonical_rule_is_reachable(self, service):
        """Cada regra da base deve ser alcançável pelo matching bilateral."""
        rules = service._get_canonical_critical_rules()
        assert rules, "base de regras críticas não pode estar vazia"
        for pair in rules:
            drugs = sorted(pair)
            assert len(drugs) == 2, f"par inválido na base: {pair}"
            a, b = drugs
            results = service._check_known_clinical_rules(a, [b])
            assert results, f"regra {a}+{b} inalcançável pelo matching canônico"


class TestCalculateOverallRisk:
    def test_single_critical_dominates(self, service):
        risk = service.calculate_overall_risk(
            [{"severity": "critical"}, {"severity": "low"}], []
        )
        assert risk == "critical"

    def test_critical_contraindication_dominates(self, service):
        risk = service.calculate_overall_risk([], [{"severity": "critical"}])
        assert risk == "critical"

    def test_high_without_critical(self, service):
        assert service.calculate_overall_risk([{"severity": "high"}], []) == "high"

    def test_empty_is_low(self, service):
        assert service.calculate_overall_risk([], []) == "low"


# ---------------------------------------------------------------------------
# Camada 2: ClinicalAgent — regras sempre executam; dedup preserva severidade
# ---------------------------------------------------------------------------


def _weak_hit(source: str) -> dict:
    return {
        "drug1": "varfarina",
        "drug2": "aspirina",
        "severity": "low",
        "description": f"evidência fraca ({source})",
        "source": source,
    }


class TestClinicalAgentAlwaysRunsRules:
    @pytest.fixture()
    def agent(self, service):
        from backend.app.langgraph_agents.clinical_agent import ClinicalAgent

        agent = ClinicalAgent.__new__(ClinicalAgent)  # sem __init__ (sem LLM)
        agent.interaction_service = service
        agent.vector_store = None
        return agent

    def test_weak_external_evidence_does_not_suppress_rules(self, agent, monkeypatch):
        """Regressão do bug original: CSV/OpenFDA fracos suprimiam as regras."""
        monkeypatch.setattr(
            agent.interaction_service,
            "find_interactions",
            lambda drug_name, other_drugs: [_weak_hit("csv")],
        )
        agent._run_openfda_sync = lambda *_a, **_k: [_weak_hit("openfda")]

        interactions, sources = agent._analyze_interactions(
            "aspirina", {"current_medications": ["varfarina"]}
        )

        assert "clinical_rules" in sources
        criticals = [i for i in interactions if i.get("severity") == "critical"]
        assert (
            criticals
        ), "regra crítica varfarina+aspirina foi suprimida por evidência fraca"

    def test_dedup_keeps_highest_severity_per_pair(self, agent, monkeypatch):
        monkeypatch.setattr(
            agent.interaction_service,
            "find_interactions",
            lambda drug_name, other_drugs: [_weak_hit("csv")],
        )
        agent._run_openfda_sync = lambda *_a, **_k: [_weak_hit("openfda")]

        interactions, _ = agent._analyze_interactions(
            "aspirina", {"current_medications": ["varfarina"]}
        )

        assert (
            len(interactions) == 1
        ), "dedup deveria fundir o mesmo par em uma única entrada"
        assert interactions[0]["severity"] == "critical"

    def test_rules_run_even_without_other_sources(self, agent, monkeypatch):
        monkeypatch.setattr(
            agent.interaction_service,
            "find_interactions",
            lambda drug_name, other_drugs: [],
        )
        agent._run_openfda_sync = lambda *_a, **_k: []

        interactions, sources = agent._analyze_interactions(
            "aspirina", {"current_medications": ["varfarina"]}
        )

        assert sources == ["clinical_rules"]
        assert interactions and interactions[0]["severity"] == "critical"


# ---------------------------------------------------------------------------
# Camada 3: SafetyAgent — hard guardrail de floor de risco
# ---------------------------------------------------------------------------


def _build_safety_agent():
    with patch("backend.app.langgraph_agents.base_agent.ChatOllama"), patch(
        "backend.app.langgraph_agents.base_agent.get_settings"
    ) as mock_settings, patch(
        "backend.app.langgraph_agents.base_agent.get_agent_logger"
    ):
        settings = MagicMock()
        settings.is_cloud_model = False
        settings.ollama_api_key = None
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_local_model = "qwen3:8b"
        settings.ollama_temperature = 0.7
        settings.ollama_max_tokens = 4096
        settings.effective_model_name = "qwen3:8b"
        mock_settings.return_value = settings

        from backend.app.langgraph_agents.safety_agent import SafetyAgent

        return SafetyAgent()


def _state(risk, interactions):
    return {
        "messages": [],
        "timestamps": {},
        "risk_level": risk,
        "interactions": interactions,
        "contraindications": [],
        "confidence": 0.95,
        "analysis": "análise de teste descrevendo risco de sangramento grave",
        "recommendations": ["monitorar INR"],
        "warnings": [],
    }


class TestSafetyAgentRiskFloor:
    def test_low_risk_with_critical_finding_is_floored_to_critical(self):
        from backend.app.langgraph_agents.state import RiskLevel

        agent = _build_safety_agent()
        state = _state(
            RiskLevel.LOW,
            [
                {
                    "drug1": "varfarina",
                    "drug2": "aspirina",
                    "severity": "critical",
                    "description": "Risco grave de sangramento",
                }
            ],
        )

        updates = agent.process(state)

        assert updates["risk_level"] == RiskLevel.CRITICAL
        assert updates["requires_human_review"] is True
        assert any(
            "Guardrail" in reason for reason in updates.get("escalation_reasons", [])
        ), "escalação deve registrar o motivo do guardrail"

    def test_string_risk_level_is_normalized_and_floored(self):
        """Regressão de fronteira: risk_level pode chegar como str da API."""
        from backend.app.langgraph_agents.state import RiskLevel

        agent = _build_safety_agent()
        state = _state("low", [{"severity": "critical", "description": "x"}])

        updates = agent.process(state)

        assert updates["risk_level"] == RiskLevel.CRITICAL

    def test_high_finding_floors_to_high(self):
        from backend.app.langgraph_agents.state import RiskLevel

        agent = _build_safety_agent()
        state = _state(RiskLevel.LOW, [{"severity": "high", "description": "x"}])

        updates = agent.process(state)

        assert updates["risk_level"] == RiskLevel.HIGH
        # AC-08.1: risco alto TAMBÉM entra na fila HITL (não só critical)
        assert updates["requires_human_review"] is True

    def test_no_findings_keeps_low(self):
        from backend.app.langgraph_agents.state import RiskLevel

        agent = _build_safety_agent()
        state = _state(RiskLevel.LOW, [])

        updates = agent.process(state)

        assert updates.get("risk_level") in (None, RiskLevel.LOW)

    def test_floor_never_downgrades(self):
        """Floor só eleva: CRITICAL com achado medium permanece CRITICAL."""
        from backend.app.langgraph_agents.state import RiskLevel

        agent = _build_safety_agent()
        state = _state(RiskLevel.CRITICAL, [{"severity": "medium", "description": "x"}])

        updates = agent.process(state)

        assert updates.get("risk_level") in (None, RiskLevel.CRITICAL)
