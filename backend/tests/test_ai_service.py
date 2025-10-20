"""
Testes para o serviço de IA
"""

import pytest
import pytest_asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock, AsyncMock
from services.ai_service import AIService
from models.schemas import PatientData, MedicationInfo, RiskLevel, Gender, Contraindication, DrugInteraction

class TestAIService:
    """Testes para o serviço de IA"""

    def setup_method(self):
        """Setup para cada teste"""
        self.ai_service = AIService()

        # Dados de teste
        self.test_patient = PatientData(
            age=30,
            gender=Gender.MALE,
            weight=70.0,
            conditions=["hipertensão"],
            allergies=["penicilina"],
            current_medications=["losartana"],
            supplements=[],
            alcohol_use=False,
            smoking=False,
            pregnancy=None,
            breastfeeding=None,
            kidney_function=None,
            liver_function=None,
            additional_info=""
        )

        self.test_medication = MedicationInfo(
            name="Dipirona",
            active_ingredient="dipirona sódica",
            dosage="500mg",
            route="oral",
            manufacturer="Genérico",
            therapeutic_class="Analgésico",
            anvisa_registry="1234567890"
        )

    def test_build_analysis_prompt(self):
        """Testa construção do prompt de análise"""
        prompt = self.ai_service._build_analysis_prompt(self.test_patient, self.test_medication)

        assert "dipirona" in prompt.lower()
        assert "30 anos" in prompt
        assert "hipertensão" in prompt
        assert "penicilina" in prompt
        assert "losartana" in prompt

    def test_map_severity_to_risk_level(self):
        """Testa mapeamento de severidade para nível de risco"""
        assert self.ai_service._map_severity_to_risk_level("crítica") == RiskLevel.CRITICAL
        assert self.ai_service._map_severity_to_risk_level("grave") == RiskLevel.HIGH
        assert self.ai_service._map_severity_to_risk_level("moderada") == RiskLevel.MEDIUM
        assert self.ai_service._map_severity_to_risk_level("leve") == RiskLevel.LOW
        assert self.ai_service._map_severity_to_risk_level("desconhecida") == RiskLevel.MEDIUM

    def test_map_frequency_to_severity(self):
        """Testa mapeamento de frequência para severidade"""
        assert self.ai_service._map_frequency_to_severity("muito comum") == "leve"
        assert self.ai_service._map_frequency_to_severity("comum") == "leve"
        assert self.ai_service._map_frequency_to_severity("incomum") == "moderada"
        assert self.ai_service._map_frequency_to_severity("rara") == "grave"
        assert self.ai_service._map_frequency_to_severity("muito rara") == "grave"
        assert self.ai_service._map_frequency_to_severity("desconhecida") == "moderada"

    def test_parse_ai_response_valid_json(self):
        """Testa parsing de resposta válida da IA"""
        valid_response = """
        {
            "contraindications": [
                {
                    "type": "alergia",
                    "description": "Hipersensibilidade ao princípio ativo",
                    "severity": "crítica"
                }
            ],
            "interactions": [
                {
                    "drug": "varfarina",
                    "type": "farmacocinética",
                    "effect": "potencialização do efeito anticoagulante",
                    "severity": "alta"
                }
            ],
            "adverse_reactions": [
                {
                    "reaction": "agranulocitose",
                    "frequency": "rara",
                    "description": "Redução de glóbulos brancos"
                }
            ]
        }
        """

        result = self.ai_service._parse_ai_response(valid_response)

        assert "contraindications" in result
        assert "interactions" in result
        assert "adverse_reactions" in result
        assert len(result["contraindications"]) == 1
        assert result["contraindications"][0]["type"] == "alergia"

    def test_parse_ai_response_invalid_json(self):
        """Testa parsing de resposta inválida da IA"""
        invalid_response = "Esta é uma resposta em texto livre sem JSON válido"

        result = self.ai_service._parse_ai_response(invalid_response)

        # Deve retornar estrutura vazia mas válida
        assert isinstance(result, dict)
        assert result == {}  # Retorna dict vazio quando não encontra JSON

    def test_calculate_overall_risk_critical(self):
        """Testa cálculo de risco geral - crítico"""
        analysis = {
            "contraindications": [Contraindication(
                type="alergia",
                description="alergia grave",
                risk_level=RiskLevel.CRITICAL,
                source="teste",
                recommendation="evitar"
            )],
            "interactions": [],
            "adverse_reactions": []
        }

        risk = self.ai_service._calculate_overall_risk(analysis)
        assert risk == RiskLevel.CRITICAL

    def test_calculate_overall_risk_high(self):
        """Testa cálculo de risco geral - alto"""
        analysis = {
            "contraindications": [Contraindication(
                type="condição",
                description="condição de risco",
                risk_level=RiskLevel.HIGH,
                source="teste",
                recommendation="cuidado"
            )],
            "interactions": [],
            "adverse_reactions": []
        }

        risk = self.ai_service._calculate_overall_risk(analysis)
        assert risk == RiskLevel.HIGH

    def test_calculate_overall_risk_medium(self):
        """Testa cálculo de risco geral - médio"""
        analysis = {
            "contraindications": [Contraindication(
                type="condição",
                description="condição moderada",
                risk_level=RiskLevel.MEDIUM,
                source="teste",
                recommendation="monitorar"
            )],
            "interactions": [],
            "adverse_reactions": []
        }

        risk = self.ai_service._calculate_overall_risk(analysis)
        assert risk == RiskLevel.MEDIUM

    def test_calculate_overall_risk_low(self):
        """Testa cálculo de risco geral - baixo"""
        analysis = {
            "contraindications": [],
            "interactions": [DrugInteraction(
                interacting_drug="medicamento",
                interaction_type="farmacocinética",
                effect="efeito leve",
                risk_level=RiskLevel.LOW,
                mechanism="mecanismo",
                recommendation="monitorar"
            )],
            "adverse_reactions": []
        }

        risk = self.ai_service._calculate_overall_risk(analysis)
        assert risk == RiskLevel.LOW

    def test_generate_recommendations_critical(self):
        """Testa geração de recomendações para risco crítico"""
        analysis = {
            "contraindications": [Contraindication(
                type="alergia",
                description="Alergia grave",
                risk_level=RiskLevel.CRITICAL,
                source="teste",
                recommendation="evitar"
            )],
            "interactions": [],
            "adverse_reactions": []
        }

        recommendations = self.ai_service._generate_recommendations(analysis, RiskLevel.CRITICAL)

        assert len(recommendations) > 0
        assert any(rec.priority == RiskLevel.CRITICAL for rec in recommendations)
        assert any("não usar" in rec.action.lower() for rec in recommendations)

    def test_generate_recommendations_low(self):
        """Testa geração de recomendações para risco baixo"""
        analysis = {
            "contraindications": [],
            "interactions": [],
            "adverse_reactions": []
        }

        recommendations = self.ai_service._generate_recommendations(analysis, RiskLevel.LOW)

        assert len(recommendations) > 0
        # Sempre inclui recomendação geral de consultar médico
        assert any("consulte" in rec.action.lower() for rec in recommendations)

    def test_generate_patient_summary(self):
        """Testa geração de resumo para o paciente"""
        analysis = {
            "contraindications": [Contraindication(
                type="hipertensão",
                description="Cuidado com hipertensão",
                risk_level=RiskLevel.MEDIUM,
                source="teste",
                recommendation="monitorar"
            )],
            "interactions": [DrugInteraction(
                interacting_drug="losartana",
                interaction_type="farmacodinâmica",
                effect="potencialização",
                risk_level=RiskLevel.MEDIUM,
                mechanism="mecanismo",
                recommendation="monitorar"
            )],
            "adverse_reactions": []
        }

        summary = self.ai_service._generate_patient_summary(
            analysis, self.test_patient, self.test_medication
        )

        assert isinstance(summary, str)
        assert len(summary) > 50  # Deve ser um resumo substancial
        assert "dipirona" in summary.lower()

    @pytest.mark.asyncio
    @patch('services.ai_service.requests.post')
    async def test_query_ollama_success(self, mock_post):
        """Testa consulta bem-sucedida ao Ollama"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Resposta da IA"}}]
        }
        mock_post.return_value = mock_response

        result = await self.ai_service._query_ollama("Teste prompt")

        assert result == "Resposta da IA"
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    @patch('services.ai_service.requests.post')
    async def test_query_ollama_failure(self, mock_post):
        """Testa falha na consulta ao Ollama"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = await self.ai_service._query_ollama("Teste prompt")

        assert result == ""  # Retorna string vazia em caso de erro

    @pytest.mark.asyncio
    @patch('services.ai_service.DrugService')
    async def test_analyze_contraindications_success(self, mock_drug_service_class):
        """Testa análise bem-sucedida de contraindicações"""
        # Mock do drug service
        mock_drug_service = MagicMock()
        mock_drug_service_class.return_value = mock_drug_service
        mock_drug_service.get_contraindications = AsyncMock(return_value=[])
        mock_drug_service.get_drug_interactions = AsyncMock(return_value=[])

        # Mock da consulta à IA
        with patch.object(self.ai_service, '_query_ollama', return_value='{"contraindications": []}'):
            result = await self.ai_service.analyze_contraindications(
                self.test_patient, self.test_medication, "test-session"
            )

        assert result is not None
        assert result.session_id == "test-session"
        assert result.patient == self.test_patient
        assert result.medication == self.test_medication

    @pytest.mark.asyncio
    @patch('services.ai_service.DrugService')
    async def test_analyze_contraindications_fallback(self, mock_drug_service_class):
        """Testa fallback quando análise de IA falha"""
        # Mock do drug service
        mock_drug_service = MagicMock()
        mock_drug_service_class.return_value = mock_drug_service
        mock_drug_service.get_contraindications = AsyncMock(return_value=[])
        mock_drug_service.get_drug_interactions = AsyncMock(return_value=[])

        # Mock da consulta à IA falhando
        with patch.object(self.ai_service, '_query_ollama', side_effect=Exception("IA failed")):
            result = await self.ai_service.analyze_contraindications(
                self.test_patient, self.test_medication, "test-session"
            )

        assert result is not None
        assert result.session_id == "test-session"
        # Deve usar análise de fallback
        assert "sistema temporariamente indisponível" in result.summary.lower()
