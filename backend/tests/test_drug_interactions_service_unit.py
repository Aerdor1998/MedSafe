from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-minimum-32-characters-long")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://medsafe:test_password@localhost:5432/medsafe"
    )


@dataclass
class _IdResult:
    canonical_name: str
    method: Any
    confidence: float = 0.9


class _FakeIdentifier:
    def __init__(self, mod):
        self.mod = mod

    def identify(self, name: str) -> _IdResult:
        n = (name or "").lower().strip()
        if n in {"aspirina", "aspirin"}:
            return _IdResult(
                "acetylsalicylic acid", self.mod.IdentificationMethod.EXACT_MATCH, 0.99
            )
        if not n:
            return _IdResult("", self.mod.IdentificationMethod.NOT_FOUND, 0.0)
        return _IdResult(n, self.mod.IdentificationMethod.FUZZY_MATCH, 0.7)


@dataclass
class _ClsResult:
    severity: Any
    confidence: float = 0.9
    reasoning: str = "ok"


class _FakeClassifier:
    def __init__(self, mod):
        self.mod = mod

    def classify_interaction(
        self, description: str, drug1: str, drug2: str
    ) -> _ClsResult:  # noqa: ARG002
        desc = (description or "").lower()
        if "qt" in desc:
            return _ClsResult(self.mod.SeverityLevel.CRITICAL, 0.95, "qt")
        if "bleeding" in desc:
            return _ClsResult(self.mod.SeverityLevel.HIGH, 0.9, "bleed")
        return _ClsResult(self.mod.SeverityLevel.MEDIUM, 0.8, "med")

    def validate_critical_decision(
        self, result: _ClsResult, description: str
    ) -> _ClsResult:  # noqa: ARG002
        return result


class _FakeOpenFDA:
    async def get_drug_label(self, drug_name: str) -> Dict[str, Any]:  # noqa: ARG002
        return {
            "drug_interactions": ["Contraindicated with warfarin due to BLEEDING risk."]
        }


def _make_service(monkeypatch):
    from backend.app.services import drug_interactions as mod

    # Patch dependency factories used in __init__
    monkeypatch.setattr(
        mod, "get_classifier_agent", lambda: _FakeClassifier(mod), raising=True
    )
    monkeypatch.setattr(mod, "OpenFDAService", lambda: _FakeOpenFDA(), raising=True)
    monkeypatch.setattr(
        mod,
        "get_drug_identifier",
        lambda llm_client=None: _FakeIdentifier(mod),
        raising=True,
    )  # noqa: ARG002

    return mod, mod.DrugInteractionService()


def test_interactions_db_lazy_load_missing_file(monkeypatch, tmp_path):
    mod, svc = _make_service(monkeypatch)
    svc.db_path = tmp_path / "missing.csv"
    svc._interactions_cache = None

    db = svc.interactions_db
    assert isinstance(db, dict)
    assert svc._interactions_cache == {}


def test_find_interactions_returns_empty_when_no_other_drugs(monkeypatch):
    _mod, svc = _make_service(monkeypatch)
    assert svc.find_interactions("aspirin", []) == []
    assert svc.find_interactions("aspirin", ["", "  "]) == []


def test_find_interactions_db_fast_path(monkeypatch):
    _mod, svc = _make_service(monkeypatch)
    called = {"n": 0}

    def _db_lookup(drug_norm: str, other_map: Dict[str, str]):  # noqa: ARG002
        called["n"] += 1
        return [{"drug1": "a", "drug2": "b", "severity": "high"}]

    monkeypatch.setattr(svc, "_find_interactions_db", _db_lookup, raising=True)

    out = svc.find_interactions("aspirina", ["warfarin"])
    assert called["n"] == 1
    assert out and out[0]["severity"] == "high"


def test_find_interactions_csv_fallback_matches_row(monkeypatch, tmp_path):
    _mod, svc = _make_service(monkeypatch)

    csv_path = tmp_path / "db_drug_interactions.csv"
    csv_path.write_text(
        "Drug 1,Drug 2,Interaction Description\n"
        "Aspirin,Warfarin,May increase anticoagulant activities leading to bleeding\n",
        encoding="utf-8",
    )
    svc.db_path = csv_path

    # Keep normalization simple to hit fast filter and match branch
    monkeypatch.setattr(
        svc, "_normalize_drug_name", lambda s: (s or "").lower().strip(), raising=True
    )
    monkeypatch.setattr(
        svc, "_classify_severity", lambda desc, drug1="", drug2="": "high", raising=True
    )  # noqa: ARG002

    out = svc.find_interactions("aspirin", ["warfarin"])
    assert len(out) == 1
    assert out[0]["severity"] == "high"
    assert out[0]["category"] in {
        "Coagulação",
        "Farmacológica",
        "Farmacocinética",
        "Cardiovascular",
        "Renal",
        "Hepática",
        "Neurológica",
        "Fotossensibilidade",
    }


def test_find_interactions_db_lookup_builds_result_and_falls_back_to_classify(
    monkeypatch,
):
    mod, svc = _make_service(monkeypatch)

    class _Row:
        clinical_effect = "May prolong QT interval"
        mechanism = ""
        severity = None
        interaction_type = "X"
        source = "db"

    class _Q:
        def filter(self, *args, **kwargs):  # noqa: ARG002
            return self

        def first(self):
            return _Row()

    class _DB:
        def query(self, model):  # noqa: ARG002
            return _Q()

    @contextlib.contextmanager
    def _ctx():
        yield _DB()

    monkeypatch.setattr(mod, "get_db_context", _ctx, raising=True)
    monkeypatch.setattr(
        svc,
        "_classify_severity",
        lambda desc, drug1="", drug2="": "critical",
        raising=True,
    )  # noqa: ARG002

    out = svc._find_interactions_db("a", {"raw": "b"})
    assert out and out[0]["severity"] == "critical"
    assert out[0]["category"] == "X"
    assert out[0]["source"] == "db"


@pytest.mark.asyncio
async def test_query_openfda_detects_other_drug_and_sets_severity(monkeypatch):
    _mod, svc = _make_service(monkeypatch)
    # Make sure normalization returns tokens that appear in label text
    monkeypatch.setattr(
        svc, "_normalize_drug_name", lambda s: (s or "").lower().strip(), raising=True
    )
    out = await svc._query_openfda("aspirin", ["warfarin"])
    assert out and out[0]["source"] == "openfda_label"
    assert out[0]["severity"] in {"high", "medium"}


def test_check_known_clinical_rules_hits_at_least_one_pair(monkeypatch):
    mod, svc = _make_service(monkeypatch)
    # Regras críticas migraram para clinical_rules.py (fonte única);
    # drug_interactions.py não expõe mais CRITICAL_INTERACTIONS.
    from backend.app.services.clinical_rules import CRITICAL_INTERACTIONS

    (a, b), data = next(iter(CRITICAL_INTERACTIONS.items()))
    monkeypatch.setattr(
        svc, "_normalize_drug_name", lambda s: (s or "").lower().strip(), raising=True
    )
    out = svc._check_known_clinical_rules(a, [b])
    assert out
    assert out[0]["severity"] in {"critical", "high", "medium", "low"}
    assert out[0]["category"]
    assert out[0]["description"]


def test_analyze_contraindications_allergy_and_condition_map(monkeypatch):
    _mod, svc = _make_service(monkeypatch)
    monkeypatch.setattr(
        svc, "_normalize_drug_name", lambda s: (s or "").lower().strip(), raising=True
    )

    contra = svc.analyze_contraindications("warfarin", ["gravidez"], ["warfarin"])
    assert any(c.get("severity") == "critical" for c in contra)  # allergy match
    assert any(
        c.get("severity") in {"high", "critical"} for c in contra
    )  # condition map may add


def test_calculate_overall_risk_all_levels(monkeypatch):
    _mod, svc = _make_service(monkeypatch)
    assert svc.calculate_overall_risk([{"severity": "critical"}], []) == "critical"
    assert svc.calculate_overall_risk([], [{"severity": "high"}]) == "high"
    assert svc.calculate_overall_risk([{"severity": "medium"}], []) == "medium"
    assert svc.calculate_overall_risk([], []) == "low"
