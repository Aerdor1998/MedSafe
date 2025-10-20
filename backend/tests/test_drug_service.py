"""
Testes para o serviço de medicamentos
"""

import pytest
import pytest_asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock, AsyncMock
from services.drug_service import DrugService
from models.schemas import MedicationInfo, Contraindication, DrugInteraction, RiskLevel

class TestDrugService:
    """Testes para o serviço de medicamentos"""
    
    def setup_method(self):
        """Setup para cada teste"""
        self.drug_service = DrugService()
    
    def test_load_medication_alternatives(self):
        """Testa carregamento de alternativas de medicamentos"""
        alternatives = self.drug_service._load_medication_alternatives()
        
        assert isinstance(alternatives, dict)
        assert "dipirona" in alternatives
        assert "paracetamol" in alternatives
        assert "novalgina" in alternatives["dipirona"]
        assert "tylenol" in alternatives["paracetamol"]
    
    def test_normalize_medication_name(self):
        """Testa normalização de nomes de medicamentos"""
        assert self.drug_service._normalize_medication_name("DIPIRONA SÓDICA") == "dipirona sódica"
        # Agora remove dosagens
        assert self.drug_service._normalize_medication_name("Paracetamol 500mg") == "paracetamol"
        assert self.drug_service._normalize_medication_name("  Ibuprofeno  ") == "ibuprofeno"
    
    def test_find_active_ingredient(self):
        """Testa identificação de princípio ativo"""
        # Teste com alternativas conhecidas
        ingredient = self.drug_service._find_active_ingredient("Novalgina")
        assert ingredient == "dipirona"
        
        ingredient = self.drug_service._find_active_ingredient("Tylenol")
        assert ingredient == "paracetamol"
        
        # Teste com nome desconhecido
        ingredient = self.drug_service._find_active_ingredient("Medicamento Desconhecido")
        assert ingredient is None
    
    def test_map_severity_to_risk(self):
        """Testa mapeamento de severidade para risco"""
        assert self.drug_service._map_severity_to_risk("crítica") == RiskLevel.CRITICAL
        assert self.drug_service._map_severity_to_risk("alta") == RiskLevel.HIGH
        assert self.drug_service._map_severity_to_risk("média") == RiskLevel.MEDIUM
        assert self.drug_service._map_severity_to_risk("baixa") == RiskLevel.LOW
        assert self.drug_service._map_severity_to_risk("desconhecida") == RiskLevel.MEDIUM
    
    @pytest.mark.asyncio
    @patch('services.drug_service.get_db_connection')
    async def test_get_medication_info_found(self, mock_get_conn):
        """Testa busca de medicamento encontrado"""
        # Mock da conexão e cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock do resultado da query
        mock_row = {
            "name": "Dipirona Sódica",
            "active_ingredient": "dipirona sódica",
            "therapeutic_class": "Analgésico",
            "anvisa_registry": "1234567890",
            "dosage": "500mg",
            "route": "oral",
            "manufacturer": "Genérico"
        }
        mock_cursor.fetchone.return_value = mock_row
        
        result = await self.drug_service.get_medication_info("dipirona")
        
        assert isinstance(result, MedicationInfo)
        assert result.name == "Dipirona Sódica"
        assert result.active_ingredient == "dipirona sódica"
        assert result.therapeutic_class == "Analgésico"
        
        mock_conn.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('services.drug_service.get_db_connection')
    async def test_get_medication_info_not_found(self, mock_get_conn):
        """Testa busca de medicamento não encontrado"""
        # Mock da conexão e cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock do resultado vazio
        mock_cursor.fetchone.return_value = None
        
        result = await self.drug_service.get_medication_info("medicamento inexistente")
        
        assert isinstance(result, MedicationInfo)
        assert result.name == "Medicamento Inexistente"  # .title() é aplicado
        assert result.active_ingredient == "medicamento inexistente"
        
        mock_conn.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('services.drug_service.get_db_connection')
    async def test_search_medications(self, mock_get_conn):
        """Testa busca de medicamentos"""
        # Mock da conexão e cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock dos resultados
        mock_rows = [
            {"name": "Dipirona Sódica", "active_ingredient": "dipirona sódica", "therapeutic_class": "Analgésico"},
            {"name": "Dipirona Genérica", "active_ingredient": "dipirona sódica", "therapeutic_class": "Analgésico"}
        ]
        mock_cursor.fetchall.return_value = mock_rows
        
        results = await self.drug_service.search_medications("dipirona")
        
        assert len(results) == 2
        assert results[0]["name"] == "Dipirona Sódica"
        assert results[1]["name"] == "Dipirona Genérica"
        
        mock_conn.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('services.drug_service.get_db_connection')
    async def test_get_contraindications(self, mock_get_conn):
        """Testa busca de contraindicações"""
        # Mock da conexão e cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock dos resultados
        mock_rows = [
            {
                "condition_type": "alergia",
                "severity": "crítica",
                "description": "Hipersensibilidade ao princípio ativo",
                "recommendation": "Não usar",
                "source": "ANVISA"
            }
        ]
        mock_cursor.fetchall.return_value = mock_rows
        
        # Mock da segunda consulta (medicamentos)
        mock_cursor.fetchone.return_value = None
        
        contraindications = await self.drug_service.get_contraindications("dipirona", ["alergia"])
        
        assert len(contraindications) == 1
        assert isinstance(contraindications[0], Contraindication)
        assert contraindications[0].type == "alergia"
        assert contraindications[0].risk_level == RiskLevel.CRITICAL
        assert contraindications[0].description == "Hipersensibilidade ao princípio ativo"
        
        mock_conn.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('services.drug_service.get_db_connection')
    async def test_get_drug_interactions(self, mock_get_conn):
        """Testa busca de interações medicamentosas"""
        # Mock da conexão e cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock dos resultados
        mock_rows = [
            {
                "drug_b": "varfarina",
                "interaction_type": "farmacocinética",
                "severity": "alta",
                "clinical_effect": "potencialização do efeito anticoagulante",
                "mechanism": "competição por metabolismo",
                "recommendation": "Monitorar INR",
                "source": "DrugCentral"
            }
        ]
        mock_cursor.fetchall.return_value = mock_rows
        
        interactions = await self.drug_service.get_drug_interactions("dipirona", ["varfarina"])
        
        assert len(interactions) == 1
        assert isinstance(interactions[0], DrugInteraction)
        assert interactions[0].interacting_drug == "varfarina"
        assert interactions[0].risk_level == RiskLevel.HIGH
        assert interactions[0].effect == "potencialização do efeito anticoagulante"
        
        mock_conn.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('services.drug_service.get_db_connection')
    async def test_get_medication_by_therapeutic_class(self, mock_get_conn):
        """Testa busca por classe terapêutica"""
        # Mock da conexão e cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock dos resultados
        mock_rows = [
            {
                "name": "Dipirona Sódica",
                "active_ingredient": "dipirona sódica",
                "therapeutic_class": "Analgésico",
                "anvisa_registry": "1234567890",
                "dosage": "500mg",
                "route": "oral",
                "manufacturer": "Genérico"
            }
        ]
        mock_cursor.fetchall.return_value = mock_rows
        
        medications = await self.drug_service.get_medication_by_therapeutic_class("Analgésico")
        
        assert len(medications) == 1
        assert isinstance(medications[0], MedicationInfo)
        assert medications[0].name == "Dipirona Sódica"
        assert medications[0].therapeutic_class == "Analgésico"
        
        mock_conn.close.assert_called_once()
    
    def test_known_alternatives_access(self):
        """Testa acesso às alternativas conhecidas"""
        alternatives = self.drug_service.known_alternatives
        
        assert isinstance(alternatives, dict)
        assert "dipirona" in alternatives
        assert "paracetamol" in alternatives
        assert "ibuprofeno" in alternatives
        
        # Verificar se as listas não estão vazias
        assert len(alternatives["dipirona"]) > 0
        assert len(alternatives["paracetamol"]) > 0
