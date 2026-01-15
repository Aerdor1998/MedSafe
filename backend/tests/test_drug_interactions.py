"""
Testes leves para o serviço de interações (versão atual).
"""

from backend.app.services.drug_interactions import normalize_drug_name, DrugInteractionService


def test_normalize_drug_name_handles_accents():
    # normalize_drug_name atualmente apenas lower/strip (mantém acentos)
    assert normalize_drug_name("Ácido Acetilsalicílico") == "ácido acetilsalicílico"


def test_drug_synonyms_contains_common_entries():
    service = DrugInteractionService()
    assert "aspirina" in service.DRUG_SYNONYMS
    assert service.DRUG_SYNONYMS["aspirina"] == "acetylsalicylic acid"
