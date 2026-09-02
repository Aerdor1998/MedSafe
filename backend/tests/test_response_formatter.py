import enum

from backend.app.services.response_formatter import (
    build_recommendations_from_state,
    compute_accuracy,
    normalize_str,
    patient_completeness,
)


class _EnumLike:
    def __init__(self, value):
        self.value = value


class _ExplodingValue:
    @property
    def value(self):  # pragma: no cover (property invoked by test)
        raise RuntimeError("boom")

    def __str__(self):
        return "fallback-str"


def test_normalize_str_handles_none_and_enum_like():
    assert normalize_str(None) == ""
    assert normalize_str(_EnumLike("critical")) == "critical"
    # enum value is None -> normalize_str falls back to str(obj)
    obj = _EnumLike(None)
    assert normalize_str(obj) == str(obj)


def test_normalize_str_does_not_crash_on_bad_value_property():
    assert normalize_str(_ExplodingValue()) == "fallback-str"


def test_patient_completeness_scores_and_factors():
    score, factors = patient_completeness({"age": 0})
    assert 0.0 <= score <= 1.0
    assert any("age missing" in f for f in factors)
    assert any("sex/gender missing" in f for f in factors)
    assert any("allergies field missing" in f for f in factors)

    score2, factors2 = patient_completeness(
        {
            "age": 30,
            "weight": 70,
            "sex": "M",
            "current_medications": [],
            "allergies": [],
            "conditions": [],
        }
    )
    assert score2 > score
    assert any("Allergies: not reported" in f for f in factors2)


def test_build_recommendations_from_state_structured_and_fallback_dedupes():
    state = {
        "structured_recommendations": {
            "header": "Header",
            "immediate_actions": ["Do X", "Do X", ""],
            "monitoring_required": ["Monitor Y"],
        },
        "dosage_adjustments": [{"recommendation": "Reduce dose"}, "Reduce dose"],
    }
    recs = build_recommendations_from_state(state)
    assert "Header" in recs[0]
    assert any(r.startswith("Immediate actions:") for r in recs)
    assert any(r.startswith("Monitoring:") for r in recs)
    # dedupe
    assert len([r for r in recs if "Do X" in r]) == 1
    assert any("Dosage adjustment:" in r for r in recs)


def test_compute_accuracy_penalizes_partial_missing_anamnesis_and_critique():
    state = {
        "confidence_score": 0.9,
        "status": "partial",
        "critique_level": "high",
        "refinement_count": 2,
        "interactions": [{"x": 1}],
        "evidence_links": [],  # findings without evidence -> penalty
    }
    patient = {"age": 0}  # incomplete
    acc, factors = compute_accuracy(state, patient)
    assert 0.0 <= acc <= 1.0
    assert acc < 0.9
    assert any("partial analysis" in f.lower() for f in factors)
    assert any("CritiqueLevel=high" in f for f in factors)


class _E(enum.Enum):
    A = "a"


class _WeirdEnumLike:
    @property
    def value(self):
        raise RuntimeError("boom")


def test_normalize_str_handles_none_enum_and_fallback():
    assert normalize_str(None) == ""
    assert normalize_str(_E.A) == "a"
    # value property exists but errors -> fallback to str(obj)
    obj = _WeirdEnumLike()
    assert normalize_str(obj) == str(obj)


def test_patient_completeness_scoring_and_factors():
    score, factors = patient_completeness(
        {"age": 30, "sex": "M", "weight": 70, "allergies": [], "conditions": []}
    )
    assert 0.0 <= score <= 1.0
    # allergies field present but empty -> informational factor
    assert any("Allergies: not reported" in f for f in factors)

    score2, factors2 = patient_completeness(
        {"age": 0, "weight": 70, "current_medications": []}
    )
    assert score2 < score
    assert any("age missing/0" in f for f in factors2)
    assert any("sex/gender missing" in f for f in factors2)
    assert any("allergies field missing" in f for f in factors2)


def test_build_recommendations_from_state_structured_and_fallback_and_dedup():
    state = {
        "structured_recommendations": {
            "header": "Header",
            "immediate_actions": ["Do X", "Do X"],  # duplicate
            "monitoring_required": [
                {"value": "Watch Y"}
            ],  # enum-like dict becomes string
            "patient_alerts": ["  "],  # ignored
        },
        "dosage_adjustments": [
            {"recommendation": "Adjust dose"},
            "Adjust dose",
        ],  # duplicate across formats
    }
    recs = build_recommendations_from_state(state)
    assert recs[0] == "Header"
    assert any(r.startswith("Immediate actions:") for r in recs)
    assert any(r.startswith("Dosage adjustment:") for r in recs)
    # dedup preserves only one "do x" and one "adjust dose"
    lowered = [r.lower() for r in recs]
    assert sum("do x" in r for r in lowered) == 1
    assert sum("adjust dose" in r for r in lowered) == 1
    assert len(recs) <= 30


def test_compute_accuracy_applies_penalties_and_clamps():
    state = {
        "confidence_score": 0.9,
        "status": "analyzed_partial",
        "critique_level": "high",
        "refinement_count": 2,
        "interactions": [{"a": 1}],
        "evidence_links": [],
    }
    patient = {"age": 0, "current_medications": []}  # incomplete -> penalty
    acc, factors = compute_accuracy(state, patient)
    assert 0.0 <= acc <= 1.0
    assert any("Base: confidence_score" in f for f in factors)
    assert any("Anamnesis penalty" in f for f in factors)
    assert any("partial analysis" in f.lower() for f in factors)
    assert any("CritiqueLevel=high" in f for f in factors)
    assert any("Refinements=2" in f for f in factors)
    assert any("findings without evidence" in f.lower() for f in factors)
