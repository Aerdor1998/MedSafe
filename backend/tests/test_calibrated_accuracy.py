"""Regression tests for _calibrated_accuracy (shared by /status and /hitl/approve).

Bug: /hitl/approve retornava accuracy_score=null porque o cálculo calibrado
só existia no caminho /status. O helper _calibrated_accuracy agora é usado
nos dois caminhos.
"""

from types import SimpleNamespace

from app.routers.langgraph import _calibrated_accuracy


def _job(payload=None):
    return SimpleNamespace(payload=payload)


class TestCalibratedAccuracy:
    def test_returns_non_null_accuracy_with_confidence(self):
        result = {
            "confidence_score": 0.9,
            "risk_level": "low",
            "interactions": [],
            "contraindications": [],
        }
        job = _job({"patient_data": {"age": 30, "weight_kg": 70}})

        raw, accuracy = _calibrated_accuracy(result, job)

        assert raw == 0.9
        assert accuracy is not None
        assert 0.0 <= accuracy <= 1.0

    def test_zero_confidence_without_findings_returns_raw(self):
        result = {"confidence_score": 0.0}
        raw, accuracy = _calibrated_accuracy(result, _job({}))

        assert raw == 0.0
        assert accuracy == 0.0

    def test_none_confidence_is_normalized(self):
        # confidence_score presente porém None (caminho do bug original)
        result = {"confidence_score": None}
        raw, accuracy = _calibrated_accuracy(result, _job(None))

        assert raw == 0.0
        assert accuracy == 0.0

    def test_interactions_trigger_computation_even_without_confidence(self):
        result = {
            "confidence_score": 0.0,
            "interactions": [{"drug_a": "warfarina", "drug_b": "aspirina"}],
        }
        raw, accuracy = _calibrated_accuracy(result, _job({}))

        assert raw == 0.0
        assert accuracy is not None
        assert 0.0 <= accuracy <= 1.0

    def test_patient_data_falls_back_to_job_payload(self):
        result = {"confidence_score": 0.8}
        job = _job({"patient_data": {"age": 65, "conditions": ["hipertensão"]}})

        raw, accuracy = _calibrated_accuracy(result, job)

        assert raw == 0.8
        assert 0.0 <= accuracy <= 1.0
