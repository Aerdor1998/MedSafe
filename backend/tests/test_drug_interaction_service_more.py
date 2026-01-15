from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.app.services import drug_interactions as di


@dataclass
class _Ident:
    canonical_name: str
    method: Any
    confidence: float = 1.0


class _Method:
    NOT_FOUND = type("X", (), {"value": "NOT_FOUND"})()
    EXACT = type("X", (), {"value": "exact"})()


class _DrugId:
    def identify(self, name: str) -> _Ident:
        # Emula o comportamento esperado do identificador: normaliza e aplica sinônimos
        # para aumentar chance de match com CSV.
        normalized = di.normalize_drug_name(name)
        canon = di.DrugInteractionService.DRUG_SYNONYMS.get(normalized, normalized)
        return _Ident(canonical_name=canon, method=_Method.EXACT, confidence=1.0)


class _Classifier:
    def classify_interaction(self, description: str, drug1: str, drug2: str):
        # minimal object with .severity.value + .confidence + .reasoning
        sev = type("S", (), {"value": "high"})()
        return type("R", (), {"severity": sev, "confidence": 0.9, "reasoning": "stub"})()

    def validate_critical_decision(self, result, description: str):
        return result


class _OpenFDA:
    async def get_drug_label(self, drug_name: str):
        # Deve mencionar o "other_drug" para que _query_openfda encontre match
        return {"warnings": ["contraindicated with ibuprofen"]}


def test_find_interactions_csv_fast_filter_and_match(tmp_path, monkeypatch):
    # Prepare a tiny CSV to avoid scanning large dataset
    csv_text = """Drug 1,Drug 2,Interaction Description
aspirin,ibuprofen,May increase bleeding risk
metformin,vitamin c,No major interaction
"""
    p = tmp_path / "db_drug_interactions.csv"
    p.write_text(csv_text, encoding="utf-8")

    monkeypatch.setattr(di, "get_classifier_agent", lambda: _Classifier())
    monkeypatch.setattr(di, "OpenFDAService", lambda: _OpenFDA())
    monkeypatch.setattr(di, "get_drug_identifier", lambda llm_client=None: _DrugId())
    monkeypatch.setattr(di, "IdentificationMethod", _Method)

    svc = di.DrugInteractionService()
    svc.db_path = Path(p)

    # Force DB lookup to be empty so CSV path is exercised
    monkeypatch.setattr(svc, "_find_interactions_db", lambda *a, **k: [])

    out = svc.find_interactions("Aspirina", ["Ibuprofeno"])
    assert len(out) == 1
    assert out[0]["severity"] == "high"
    assert out[0]["category"]


@pytest.mark.asyncio
async def test_openfda_fallback_when_csv_empty(monkeypatch):
    monkeypatch.setattr(di, "get_classifier_agent", lambda: _Classifier())
    monkeypatch.setattr(di, "OpenFDAService", lambda: _OpenFDA())
    monkeypatch.setattr(di, "get_drug_identifier", lambda llm_client=None: _DrugId())
    monkeypatch.setattr(di, "IdentificationMethod", _Method)

    svc = di.DrugInteractionService()
    monkeypatch.setattr(svc, "find_interactions", lambda *a, **k: [])

    res = await svc.find_interactions_with_fallback("aspirin", ["ibuprofen"])
    assert res
    assert res[0]["source"].startswith("openfda")


def test_analyze_contraindications_allergy_and_condition(monkeypatch):
    monkeypatch.setattr(di, "get_classifier_agent", lambda: _Classifier())
    monkeypatch.setattr(di, "OpenFDAService", lambda: _OpenFDA())
    monkeypatch.setattr(di, "get_drug_identifier", lambda llm_client=None: _DrugId())
    monkeypatch.setattr(di, "IdentificationMethod", _Method)

    svc = di.DrugInteractionService()
    contraindications = svc.analyze_contraindications(
        "paracetamol",
        patient_conditions=["insuficiência hepática"],
        allergies=["paracetamol"],
    )
    # Allergy critical + condition high
    assert any(c["severity"] == "critical" for c in contraindications)
    assert any("Contraindicação" in c["type"] for c in contraindications)

