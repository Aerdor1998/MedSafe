"""
Testes para o serviço OpenFDA
"""

import pytest
import respx
import httpx

from backend.app.services.openfda_service import OpenFDAService


@pytest.mark.asyncio
async def test_openfda_adverse_events():
    """Testar busca de eventos adversos"""
    service = OpenFDAService()

    with respx.mock:
        respx.get("https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"patient": {"reaction": [{"reactionmeddrapt": "Nausea"}]}}]},
            )
        )
        events = await service.get_adverse_events("aspirin", limit=5)

    assert isinstance(events, list)
    assert len(events) == 1
    assert isinstance(events[0], dict)


@pytest.mark.asyncio
async def test_openfda_drug_label():
    """Testar busca de bula/rótulo"""
    service = OpenFDAService()

    with respx.mock:
        respx.get("https://api.fda.gov/drug/label.json").mock(
            return_value=httpx.Response(200, json={"results": [{"openfda": {"brand_name": ["Aspirin"]}}]})
        )
        label = await service.get_drug_label("aspirin")

    assert isinstance(label, dict)


@pytest.mark.asyncio
async def test_openfda_without_api_key():
    """Testar que API funciona sem chave"""
    service = OpenFDAService()

    with respx.mock:
        respx.get("https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        events = await service.get_adverse_events("ibuprofen", limit=2)

    assert isinstance(events, list)


@pytest.mark.asyncio
async def test_openfda_enriched_info():
    """Testar informações enriquecidas"""
    service = OpenFDAService()

    with respx.mock:
        respx.get("https://api.fda.gov/drug/label.json").mock(
            return_value=httpx.Response(200, json={"results": [{"openfda": {"generic_name": ["Metformin"]}}]})
        )
        respx.get("https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        info = await service.get_drug_info_enriched("metformin")

    assert isinstance(info, dict)
    assert "drug_name" in info
    assert "timestamp" in info


@pytest.mark.asyncio
async def test_openfda_invalid_drug():
    """Testar com medicamento inexistente"""
    service = OpenFDAService()

    with respx.mock:
        # Simular 404/sem resultados: serviço deve retornar lista vazia sem explodir
        respx.get("https://api.fda.gov/drug/event.json").mock(
            return_value=httpx.Response(404, json={"error": {"message": "Not found"}})
        )
        events = await service.get_adverse_events("medicamento_inexistente_xyz123", limit=1)

    assert isinstance(events, list)
    assert len(events) == 0


def test_openfda_initialization():
    """Testar inicialização do serviço"""
    service = OpenFDAService()

    assert service.base_url == "https://api.fda.gov/drug"
    assert service.timeout == 30
    assert hasattr(service, "session")
