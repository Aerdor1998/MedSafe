"""
Unit tests for ClinicalAgent

Tests clinical analysis, drug interactions, risk calculation, and recommendations
without requiring actual LLM or database connections.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from backend.app.langgraph_agents.clinical_agent import ClinicalAgent, create_clinical_agent
from backend.app.langgraph_agents.state import RiskLevel


class TestClinicalAgentInit:
    """Tests for ClinicalAgent initialization"""

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_init_success(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test successful initialization"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = MagicMock()
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        
        assert agent.agent_name == "ClinicalAgent"
        assert agent.interaction_service is not None
        assert agent.rules_engine is not None

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_init_without_vector_store(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test initialization when vector store is unavailable"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.side_effect = Exception("Vector store unavailable")
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        
        assert agent.vector_store is None


class TestClinicalAgentSystemPrompt:
    """Tests for system prompt"""

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_get_system_prompt(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test system prompt contains required elements"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        prompt = agent.get_system_prompt()

        assert "ClinicalAgent" in prompt
        assert "MedSafe" in prompt
        assert "farmacologia" in prompt.lower() or "pharmacology" in prompt.lower()
        assert "PORTUGUÊS BRASILEIRO" in prompt


class TestEvidenceQualityAssessment:
    """Tests for evidence quality assessment"""

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_assess_evidence_quality_no_interactions(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test evidence quality with no interactions"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        quality = agent._assess_evidence_quality([], [])
        
        assert quality == "insufficient"

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_assess_evidence_quality_csv_only(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test evidence quality with CSV source only"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        interactions = [{"drug1": "A", "drug2": "B"}]
        quality = agent._assess_evidence_quality(interactions, ["csv"])
        
        assert quality == "sufficient"

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_assess_evidence_quality_multiple_sources(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test evidence quality with multiple sources"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        interactions = [{"drug1": "A", "drug2": "B"}]
        quality = agent._assess_evidence_quality(interactions, ["csv", "rag"])
        
        assert quality == "sufficient"

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_assess_evidence_quality_rules_only(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test evidence quality with clinical rules only"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        interactions = [{"drug1": "A", "drug2": "B"}]
        quality = agent._assess_evidence_quality(interactions, ["clinical_rules"])
        
        assert quality == "rules_only"


class TestHighRiskPatient:
    """Tests for high-risk patient detection"""

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_is_high_risk_elderly(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test high risk detection for elderly patients"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        
        assert agent._is_high_risk_patient({"age": 80}) is True
        assert agent._is_high_risk_patient({"age": 50}) is False

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_is_high_risk_pediatric(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test high risk detection for pediatric patients"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        
        assert agent._is_high_risk_patient({"age": 1}) is True
        assert agent._is_high_risk_patient({"age": 5}) is False

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_is_high_risk_pregnant(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test high risk detection for pregnant patients"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        
        # Note: age=0 (default when missing) is <= 2, so it's high risk
        # We need to provide a valid age to test pregnancy only
        assert agent._is_high_risk_patient({"age": 30, "pregnant": True}) is True
        assert agent._is_high_risk_patient({"age": 30, "pregnant": False}) is False

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_is_high_risk_renal_impairment(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test high risk detection for renal impairment"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        
        # Provide valid age to avoid age-based risk
        assert agent._is_high_risk_patient({"age": 40, "renal_function": "severe"}) is True
        assert agent._is_high_risk_patient({"age": 40, "renal_function": "dialysis"}) is True
        assert agent._is_high_risk_patient({"age": 40, "renal_function": "mild"}) is False

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_is_high_risk_polypharmacy(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test high risk detection for polypharmacy"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        
        # Provide valid age to avoid age-based risk
        many_meds = {"age": 40, "current_medications": ["A", "B", "C", "D", "E"]}
        few_meds = {"age": 40, "current_medications": ["A", "B"]}
        
        assert agent._is_high_risk_patient(many_meds) is True
        assert agent._is_high_risk_patient(few_meds) is False


class TestDeduplicateInteractions:
    """Tests for interaction deduplication"""

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_deduplicate_empty(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test deduplication with empty list"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        result = agent._deduplicate_interactions([])
        
        assert result == []

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_deduplicate_merges_sources(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test deduplication merges sources from duplicates"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        interactions = [
            {"drug1": "Aspirin", "drug2": "Warfarin", "severity": "high", "source": "csv", "description": "Bleeding risk"},
            {"drug1": "Warfarin", "drug2": "Aspirin", "severity": "medium", "source": "openfda", "description": "Bleeding risk"},
        ]
        
        result = agent._deduplicate_interactions(interactions)
        
        assert len(result) == 1
        assert "csv" in result[0]["sources"]
        assert "openfda" in result[0]["sources"]
        # Higher severity should be preserved
        assert result[0]["severity"] == "high"

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_deduplicate_keeps_unique(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test deduplication keeps unique interactions"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        interactions = [
            {"drug1": "Aspirin", "drug2": "Warfarin", "severity": "high", "source": "csv", "description": "Bleeding"},
            {"drug1": "Ibuprofen", "drug2": "Methotrexate", "severity": "critical", "source": "csv", "description": "Toxicity"},
        ]
        
        result = agent._deduplicate_interactions(interactions)
        
        assert len(result) == 2


class TestFallbackRecommendations:
    """Tests for fallback recommendation generation"""

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_fallback_critical_risk(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test fallback recommendations for critical risk"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        result = agent._generate_fallback_recommendations([], [], RiskLevel.CRITICAL)

        assert "RISCO CRITICO" in result["recommendations_text"]
        assert len(result["dosage_adjustments"]) > 0

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_fallback_high_risk(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test fallback recommendations for high risk"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        result = agent._generate_fallback_recommendations([], [], RiskLevel.HIGH)

        assert "Risco alto" in result["recommendations_text"]

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_fallback_with_interactions(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test fallback recommendations include interaction details"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        interactions = [
            {"drug1": "Aspirin", "drug2": "Warfarin", "severity": "critical", "description": "Increased bleeding risk"}
        ]
        result = agent._generate_fallback_recommendations(interactions, [], RiskLevel.HIGH)

        assert len(result["adverse_reactions"]) > 0
        assert "Aspirin" in str(result["adverse_reactions"])


class TestExtractDosageAdjustments:
    """Tests for dosage adjustment extraction"""

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_extract_dosage_keywords(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test extraction of dosage adjustments from text"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        text = """
        - Reduzir dosagem de metformina para 500mg
        - Ajustar intervalo de administração para 12h
        - Monitorar níveis séricos
        """
        
        result = agent._extract_dosage_adjustments(text)
        
        assert len(result) >= 2
        assert any("dosagem" in r["recommendation"].lower() or "mg" in r["recommendation"].lower() for r in result)


class TestExtractAdverseReactions:
    """Tests for adverse reaction extraction"""

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_extract_reaction_keywords(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test extraction of adverse reactions from text"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        text = """
        - Monitorar sinais de sangramento
        - Observar reação alérgica cutânea
        - Verificar função renal semanalmente
        """
        
        result = agent._extract_adverse_reactions(text)
        
        assert len(result) >= 2
        assert any("monitorar" in r["description"].lower() for r in result)


class TestPrimaryCategory:
    """Tests for primary category determination"""

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_get_primary_category_cardiovascular(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test cardiovascular category detection"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        interactions = [{"category": "Cardiovascular"}]
        
        result = agent._get_primary_category(interactions, [])
        
        assert result == "Cardiovascular"

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_get_primary_category_default(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test default category when none match"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = ClinicalAgent()
        
        result = agent._get_primary_category([], [])
        
        assert result == "Farmacologica"


class TestFactoryFunction:
    """Tests for factory function"""

    @patch("backend.app.langgraph_agents.clinical_agent.get_interaction_service")
    @patch("backend.app.langgraph_agents.clinical_agent.get_rules_engine")
    @patch("backend.app.langgraph_agents.clinical_agent.get_vector_store")
    # Removed: optimization mock
    @patch("backend.app.langgraph_agents.base_agent.ChatOllama")
    def test_create_clinical_agent(
        self, mock_ollama, mock_vs, mock_rules, mock_interaction
    ):
        """Test factory function creates agent"""
        mock_interaction.return_value = MagicMock()
        mock_rules.return_value = MagicMock()
        mock_vs.return_value = None
        # Removed: optimization mock
        mock_ollama.return_value = MagicMock()

        agent = create_clinical_agent()
        
        assert isinstance(agent, ClinicalAgent)
