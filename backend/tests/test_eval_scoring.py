"""
Testes CI-safe do harness de eval (evals/): schema do golden set,
sanidade dos nomes de medicamentos e lógica de scoring — tudo sem LLM.
A execução real do pipeline fica em evals/run_eval.py (local-only).
"""

from pathlib import Path

import yaml

from backend.app.services.drug_identifier import (
    HybridDrugIdentifier,
    IdentificationMethod,
)
from evals.scoring import RISK_ORDER, score_case, summarize, validate_case

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "evals" / "golden_set.yaml"


def _load_cases():
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["cases"]


class TestGoldenSetSchema:
    def test_all_cases_valid(self):
        for case in _load_cases():
            errors = validate_case(case)
            assert not errors, f"caso {case.get('id')}: {errors}"

    def test_ids_unique(self):
        ids = [c["id"] for c in _load_cases()]
        assert len(ids) == len(set(ids))

    def test_has_safety_critical_and_negative_cases(self):
        cases = _load_cases()
        assert any(c.get("safety_critical") for c in cases)
        assert any(c.get("negative") for c in cases)

    def test_drug_names_resolvable_or_ascii(self):
        """
        Nomes devem resolver no HybridDrugIdentifier OU ser ASCII puro
        (nomes científicos em inglês passam no fast-filter do CSV mesmo
        sem constar no dicionário de sinônimos). Pega typos e nomes PT
        não mapeados (ex.: 'lítio') que quebrariam o lookup silenciosamente.
        """
        identifier = HybridDrugIdentifier()
        for case in _load_cases():
            drugs = [case["medication"]] + list(
                case["patient"].get("current_medications", [])
            )
            for name in drugs:
                ident = identifier.identify(name)
                resolved = ident.method != IdentificationMethod.NOT_FOUND
                assert resolved or name.isascii(), (
                    f"caso {case['id']}: '{name}' não resolve no identifier "
                    f"e não é ASCII — lookup no CSV falharia silenciosamente"
                )


class TestScoreCase:
    def _case(self, **expect):
        return {"id": "t", "medication": "x", "patient": {}, "expect": expect}

    def test_min_risk_level_pass_and_fail(self):
        case = self._case(min_risk_level="high")
        ok = score_case(case, {"risk_level": "critical"})
        bad = score_case(case, {"risk_level": "medium"})
        assert ok[0].passed is True
        assert bad[0].passed is False

    def test_max_risk_level_for_negatives(self):
        case = self._case(max_risk_level="low")
        assert score_case(case, {"risk_level": "low"})[0].passed is True
        assert score_case(case, {"risk_level": "high"})[0].passed is False

    def test_risk_level_accepts_enum_like(self):
        class _Enum:
            value = "critical"

        case = self._case(min_risk_level="critical")
        assert score_case(case, {"risk_level": _Enum()})[0].passed is True

    def test_interaction_pair_requires_both_sides_same_interaction(self):
        case = self._case(
            must_flag_interactions=[[["varfarina", "warfarin"], ["aspirin"]]]
        )
        hit = {
            "risk_level": "critical",
            "interactions": [{"drug1": "Warfarin", "drug2": "Aspirin"}],
        }
        # Lados em interações DIFERENTES não contam
        split = {
            "risk_level": "critical",
            "interactions": [
                {"drug1": "Warfarin", "drug2": "Vitamina C"},
                {"drug1": "Dipirona", "drug2": "Aspirin"},
            ],
        }
        assert score_case(case, hit)[0].passed is True
        assert score_case(case, split)[0].passed is False

    def test_contraindication_substring(self):
        case = self._case(must_flag_contraindication="alergia")
        found = {
            "contraindications": [
                {"type": "Alergia Conhecida", "description": "alergia a aspirina"}
            ]
        }
        assert score_case(case, found)[0].passed is True
        assert score_case(case, {"contraindications": []})[0].passed is False

    def test_requires_human_review_bool(self):
        case = self._case(requires_human_review=True)
        assert score_case(case, {"requires_human_review": True})[0].passed is True
        assert score_case(case, {})[0].passed is False


class TestSummarize:
    def _item(self, *, critical=False, negative=False, ok=True, error=None):
        from evals.scoring import CheckResult

        return {
            "case": {"id": "c", "safety_critical": critical, "negative": negative},
            "checks": [CheckResult("x", ok, "")],
            "error": error,
        }

    def test_gate_blocks_on_critical_failure(self):
        summary = summarize(
            [self._item(critical=True, ok=True), self._item(critical=True, ok=False)]
        )
        assert summary["safety_critical_recall"] == 0.5
        assert summary["gate_ok"] is False

    def test_false_alarm_rate(self):
        summary = summarize(
            [self._item(negative=True, ok=False), self._item(negative=True, ok=True)]
        )
        assert summary["false_alarm_rate"] == 0.5
        # negativos não são gate
        assert summary["gate_ok"] is True

    def test_error_counts_as_failure(self):
        summary = summarize([self._item(critical=True, ok=True, error="timeout")])
        assert summary["gate_ok"] is False

    def test_risk_order_sanity(self):
        assert RISK_ORDER["low"] < RISK_ORDER["medium"] < RISK_ORDER["high"]
        assert RISK_ORDER["high"] < RISK_ORDER["critical"]
