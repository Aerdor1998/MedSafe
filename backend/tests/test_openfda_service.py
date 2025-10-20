"""
Testes para o serviço OpenFDA
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.openfda_service import OpenFDAService

@pytest.mark.asyncio
async def test_openfda_adverse_events():
    """Testar busca de eventos adversos"""
    service = OpenFDAService()

    events = await service.get_adverse_events("aspirin", limit=5)

    # OpenFDA pode retornar lista vazia se não encontrar
    assert isinstance(events, list)

    if len(events) > 0:
        # Verificar estrutura
        event = events[0]
        assert isinstance(event, dict)

@pytest.mark.asyncio
async def test_openfda_drug_label():
    """Testar busca de bula/rótulo"""
    service = OpenFDAService()

    label = await service.get_drug_label("aspirin")

    # Pode retornar None se não encontrar
    assert label is None or isinstance(label, dict)

@pytest.mark.asyncio
async def test_openfda_without_api_key():
    """Testar que API funciona sem chave"""
    service = OpenFDAService()

    # Deve funcionar mesmo sem API key
    events = await service.get_adverse_events("ibuprofen", limit=2)

    # Pode retornar vazio mas não deve dar erro
    assert isinstance(events, list)

@pytest.mark.asyncio
async def test_openfda_enriched_info():
    """Testar informações enriquecidas"""
    service = OpenFDAService()

    info = await service.get_drug_info_enriched("metformin")

    assert isinstance(info, dict)
    assert "drug_name" in info
    assert "timestamp" in info

@pytest.mark.asyncio
async def test_openfda_invalid_drug():
    """Testar com medicamento inexistente"""
    service = OpenFDAService()

    events = await service.get_adverse_events("medicamento_inexistente_xyz123", limit=1)

    # Deve retornar lista vazia sem erro
    assert isinstance(events, list)
    assert len(events) == 0

def test_openfda_initialization():
    """Testar inicialização do serviço"""
    service = OpenFDAService()

    assert service.base_url == "https://api.fda.gov/drug"
    assert service.timeout == 30
    assert hasattr(service, 'session')
