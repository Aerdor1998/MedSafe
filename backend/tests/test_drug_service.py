"""
Smoke test alinhado ao DrugInteractionService atual.
"""

from backend.app.services.drug_interactions import (
    DrugInteractionService,
    normalize_drug_name,
)


def test_synonym_lookup_returns_scientific_name():
    service = DrugInteractionService()
    # normalize_drug_name gera chave de lookup, e o service expõe DRUG_SYNONYMS
    key = normalize_drug_name("Aspirina")
    assert service.DRUG_SYNONYMS.get(key) == "acetylsalicylic acid"
