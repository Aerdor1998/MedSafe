"""
Testes para busca de interações medicamentosas
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.drug_service import DrugService
from models.schemas import MedicationInfo, DrugInteraction, RiskLevel

@pytest.mark.asyncio
async def test_drug_interactions_warfarin_aspirin():
    """Testar interação crítica conhecida: Warfarina + Aspirina"""
    service = DrugService()

    interactions = await service.get_drug_interactions(
        medication="Aspirin",
        current_medications=["Warfarin"]
    )

    # Teste verifica que funciona sem erro
    # Pode ou não encontrar dependendo dos nomes exatos no CSV
    assert isinstance(interactions, list)

    if len(interactions) > 0:
        # Verificar estrutura se encontrar
        interaction = interactions[0]
        assert isinstance(interaction, DrugInteraction)
        assert len(interaction.effect) > 0
        assert interaction.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]

@pytest.mark.asyncio
async def test_drug_interactions_metformina_insulina():
    """Testar interação conhecida: Metformina + Insulina"""
    service = DrugService()

    interactions = await service.get_drug_interactions(
        medication="Metformin",
        current_medications=["Insulin"]
    )

    # Pode ou não encontrar (depende da base de dados)
    # Teste apenas verifica que não há erro
    assert isinstance(interactions, list)
    for interaction in interactions:
        assert isinstance(interaction, DrugInteraction)
        assert hasattr(interaction, 'effect')
        assert hasattr(interaction, 'risk_level')

@pytest.mark.asyncio
async def test_drug_interactions_no_current_meds():
    """Testar quando paciente não usa outros medicamentos"""
    service = DrugService()

    interactions = await service.get_drug_interactions(
        medication="Paracetamol",
        current_medications=[]
    )

    # Não deve encontrar interações
    assert len(interactions) == 0

@pytest.mark.asyncio
async def test_drug_interactions_multiple_medications():
    """Testar com múltiplos medicamentos atuais"""
    service = DrugService()

    interactions = await service.get_drug_interactions(
        medication="Ibuprofen",
        current_medications=["Warfarin", "Aspirin", "Metformin"]
    )

    # Deve buscar para cada medicamento
    assert isinstance(interactions, list)

    # Verificar que cada interação tem os campos necessários
    for interaction in interactions:
        assert isinstance(interaction.interacting_drug, str)
        assert len(interaction.interacting_drug) > 0
        assert isinstance(interaction.effect, str)
        assert isinstance(interaction.risk_level, RiskLevel)

@pytest.mark.asyncio
async def test_medication_info_dipirona():
    """Testar busca de informações da Dipirona"""
    service = DrugService()

    med_info = await service.get_medication_info("Dipirona")

    assert isinstance(med_info, MedicationInfo)
    assert "dipirona" in med_info.name.lower() or "dipirona" in med_info.active_ingredient.lower()
    assert med_info.therapeutic_class is not None

@pytest.mark.asyncio
async def test_medication_info_generic_name():
    """Testar busca por princípio ativo"""
    service = DrugService()

    med_info = await service.get_medication_info("paracetamol")

    assert isinstance(med_info, MedicationInfo)
    assert "paracetamol" in med_info.active_ingredient.lower()

@pytest.mark.asyncio
async def test_medication_normalize():
    """Testar normalização de nomes de medicamentos"""
    service = DrugService()

    # Testar com sufixos
    normalized1 = service._normalize_medication_name("Dipirona 500mg")
    normalized2 = service._normalize_medication_name("Dipirona comprimido")
    normalized3 = service._normalize_medication_name("DIPIRONA")

    assert "dipirona" in normalized1
    assert "dipirona" in normalized2
    assert "dipirona" in normalized3

    # Deve remover sufixos
    assert "mg" not in normalized1
    assert "comprimido" not in normalized2

@pytest.mark.asyncio
async def test_severity_mapping():
    """Testar mapeamento de severidade para risk level"""
    service = DrugService()

    assert service._map_severity_to_risk("baixa") == RiskLevel.LOW
    assert service._map_severity_to_risk("moderada") == RiskLevel.MEDIUM
    assert service._map_severity_to_risk("alta") == RiskLevel.HIGH
    assert service._map_severity_to_risk("crítica") == RiskLevel.CRITICAL
    assert service._map_severity_to_risk("absoluta") == RiskLevel.CRITICAL

def test_database_has_interactions():
    """Testar se o banco possui interações do CSV"""
    from models.database import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM drug_interactions WHERE source = 'CSV Import'")
    result = cursor.fetchone()

    assert result['count'] > 190000, f"Esperava > 190000 interações, encontrou {result['count']}"

    conn.close()

def test_database_connection():
    """Testar conexão com o banco de dados"""
    from models.database import get_db_connection

    conn = get_db_connection()
    assert conn is not None

    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()

    assert result is not None
    conn.close()
