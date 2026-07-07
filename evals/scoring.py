"""
Scoring determinístico do golden set (evals/golden_set.yaml).

Sem LLM: recebe o resultado do pipeline (dict do LangGraph) e as
expectativas do caso, e devolve checks pass/fail auditáveis. Toda a
lógica daqui é coberta por testes unitários no CI
(backend/tests/test_eval_scoring.py) — só a EXECUÇÃO do pipeline
(run_eval.py) exige Ollama/Postgres locais.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

_EXPECT_KEYS = {
    "min_risk_level",
    "max_risk_level",
    "must_flag_interactions",
    "must_flag_contraindication",
    "requires_human_review",
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def validate_case(case: Dict[str, Any]) -> List[str]:
    """Valida o schema de um caso do golden set. Retorna lista de erros."""
    errors: List[str] = []

    for field in ("id", "medication", "patient", "expect"):
        if not case.get(field):
            errors.append(f"campo obrigatório ausente: {field}")

    expect = case.get("expect") or {}
    for key in expect:
        if key not in _EXPECT_KEYS:
            errors.append(f"expect desconhecido: {key}")

    for key in ("min_risk_level", "max_risk_level"):
        value = expect.get(key)
        if value is not None and value not in RISK_ORDER:
            errors.append(f"{key} inválido: {value}")

    for pair in expect.get("must_flag_interactions") or []:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(side, list) and side for side in pair)
        ):
            errors.append(
                f"must_flag_interactions deve ser [[aliases_a],[aliases_b]]: {pair!r}"
            )

    if not expect:
        errors.append("expect vazio: caso não verifica nada")

    return errors


def _risk_value(result: Dict[str, Any]) -> Optional[str]:
    risk = result.get("risk_level")
    if hasattr(risk, "value"):
        risk = risk.value
    if risk is None:
        return None
    return str(risk).lower()


def _interaction_matches(interaction: Dict[str, Any], aliases: List[str]) -> bool:
    """Algum alias aparece em drug1 ou drug2 da interação (case-insensitive)."""
    drug1 = str(interaction.get("drug1", "")).lower()
    drug2 = str(interaction.get("drug2", "")).lower()
    return any(a.lower() in drug1 or a.lower() in drug2 for a in aliases)


def score_case(case: Dict[str, Any], result: Dict[str, Any]) -> List[CheckResult]:
    """Aplica todas as expectativas do caso ao resultado do pipeline."""
    expect = case.get("expect") or {}
    checks: List[CheckResult] = []

    risk = _risk_value(result)

    min_risk = expect.get("min_risk_level")
    if min_risk is not None:
        passed = risk in RISK_ORDER and RISK_ORDER[risk] >= RISK_ORDER[min_risk]
        checks.append(
            CheckResult(
                name="min_risk_level",
                passed=passed,
                detail=f"esperado >= {min_risk}, obtido {risk}",
            )
        )

    max_risk = expect.get("max_risk_level")
    if max_risk is not None:
        passed = risk in RISK_ORDER and RISK_ORDER[risk] <= RISK_ORDER[max_risk]
        checks.append(
            CheckResult(
                name="max_risk_level",
                passed=passed,
                detail=f"esperado <= {max_risk}, obtido {risk}",
            )
        )

    interactions = result.get("interactions") or []
    for pair in expect.get("must_flag_interactions") or []:
        aliases_a, aliases_b = pair
        found = any(
            _interaction_matches(i, aliases_a) and _interaction_matches(i, aliases_b)
            for i in interactions
        )
        checks.append(
            CheckResult(
                name=f"must_flag_interaction:{aliases_a[0]}+{aliases_b[0]}",
                passed=found,
                detail=(
                    f"{len(interactions)} interações no resultado; "
                    f"par {'encontrado' if found else 'NÃO encontrado'}"
                ),
            )
        )

    contra_substr = expect.get("must_flag_contraindication")
    if contra_substr is not None:
        contras = result.get("contraindications") or []
        found = any(
            contra_substr.lower()
            in (str(c.get("type", "")) + " " + str(c.get("description", ""))).lower()
            for c in contras
        )
        checks.append(
            CheckResult(
                name=f"must_flag_contraindication:{contra_substr}",
                passed=found,
                detail=(
                    f"{len(contras)} contraindicações; "
                    f"'{contra_substr}' {'encontrado' if found else 'NÃO encontrado'}"
                ),
            )
        )

    expected_review = expect.get("requires_human_review")
    if expected_review is not None:
        actual = bool(result.get("requires_human_review", False))
        checks.append(
            CheckResult(
                name="requires_human_review",
                passed=actual == expected_review,
                detail=f"esperado {expected_review}, obtido {actual}",
            )
        )

    return checks


def summarize(
    scored: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Agrega os resultados por caso.

    Args:
        scored: lista de dicts {"case": case, "checks": [CheckResult], "error": str|None}

    Métricas:
        - safety_critical_recall: fração de casos GATE totalmente aprovados.
          É o número que bloqueia troca de modelo (não pode regredir).
        - false_alarm_rate: fração de casos negativos reprovados
          (superproteção/alert fatigue).
    """
    total = len(scored)
    passed_cases = 0
    critical_total = 0
    critical_passed = 0
    negative_total = 0
    negative_failed = 0

    for item in scored:
        case = item["case"]
        checks: List[CheckResult] = item["checks"]
        case_ok = item.get("error") is None and all(c.passed for c in checks)

        if case_ok:
            passed_cases += 1
        if case.get("safety_critical"):
            critical_total += 1
            if case_ok:
                critical_passed += 1
        if case.get("negative"):
            negative_total += 1
            if not case_ok:
                negative_failed += 1

    return {
        "total_cases": total,
        "passed_cases": passed_cases,
        "safety_critical_total": critical_total,
        "safety_critical_passed": critical_passed,
        "safety_critical_recall": (
            critical_passed / critical_total if critical_total else None
        ),
        "negative_total": negative_total,
        "negative_failed": negative_failed,
        "false_alarm_rate": (
            negative_failed / negative_total if negative_total else None
        ),
        "gate_ok": critical_passed == critical_total,
    }
