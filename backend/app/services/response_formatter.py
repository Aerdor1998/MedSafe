"""
Response Formatter Service

Provides utility functions for formatting API responses.
Extracted from main.py for better modularity and reusability.
"""

from typing import Any


def normalize_str(value: Any) -> str:
    """
    Normalize any value to a string representation.

    Handles None, Enums, and regular values.

    Args:
        value: Any value to normalize

    Returns:
        String representation of the value
    """
    if value is None:
        return ""

    # Handle Enums (RiskLevel, CritiqueLevel, etc.) safely.
    # IMPORTANT: avoid `hasattr(value, "value")` because it may evaluate a property
    # and raise unexpectedly.
    try:
        enum_value = getattr(value, "value")
    except Exception:
        return str(value)
    else:
        if enum_value is not None:
            return str(enum_value)
        return str(value)


def patient_completeness(info: dict) -> tuple[float, list[str]]:
    """
    Evaluate completeness of patient anamnesis.

    Args:
        info: Patient information dictionary

    Returns:
        Tuple of (score_0_to_1, factors_text_list)
    """
    factors: list[str] = []

    age = info.get("age")
    weight = info.get("weight")
    sex = info.get("sex") or info.get("gender")

    has_allergies_field = "allergies" in info
    allergies = info.get("allergies", [])

    meds = info.get("current_medications", info.get("meds_in_use", []))
    conditions = info.get("conditions", info.get("cid_codes", []))

    completeness = {
        "has_age": age is not None and isinstance(age, (int, float)) and age > 0,
        "has_sex": bool(sex),
        "has_weight": weight is not None,
        "has_current_medications": isinstance(meds, list),
        "has_allergies": has_allergies_field,
        "has_conditions": isinstance(conditions, list),
    }

    score = sum(1 for v in completeness.values() if v) / len(completeness)

    if not completeness["has_age"]:
        factors.append("Incomplete anamnesis: age missing/0")
    if not completeness["has_sex"]:
        factors.append("Incomplete anamnesis: sex/gender missing")
    if not completeness["has_current_medications"]:
        factors.append("Incomplete anamnesis: current medications missing")
    if not completeness["has_allergies"]:
        factors.append("Incomplete anamnesis: allergies field missing")

    if has_allergies_field and isinstance(allergies, list) and len(allergies) == 0:
        factors.append("Allergies: not reported (field present)")

    return score, factors


def build_recommendations_from_state(state_dict: dict) -> list[str]:
    """
    Build a list of text recommendations for the frontend.

    Returns only strings to avoid [object Object] in frontend.

    Args:
        state_dict: LangGraph state dictionary

    Returns:
        List of recommendation strings
    """
    recs: list[str] = []

    structured = state_dict.get("structured_recommendations") or {}
    if isinstance(structured, dict):
        header = structured.get("header")
        if header:
            recs.append(normalize_str(header))

        sections = [
            ("Immediate actions", structured.get("immediate_actions", [])),
            ("Monitoring", structured.get("monitoring_required", [])),
            ("Lab tests", structured.get("laboratory_tests", [])),
            ("Patient alerts", structured.get("patient_alerts", [])),
            ("Alternatives", structured.get("alternatives", [])),
            ("Follow-up", structured.get("follow_up", [])),
            ("Counseling", structured.get("patient_counseling", [])),
        ]
        for label, items in sections:
            if isinstance(items, list):
                for it in items:
                    text = normalize_str(it).strip()
                    if text:
                        recs.append(f"{label}: {text}")

    # Fallback: dosage_adjustments / adverse_reactions
    dosage_adjustments = state_dict.get("dosage_adjustments", [])
    if isinstance(dosage_adjustments, list):
        for adj in dosage_adjustments:
            if isinstance(adj, dict):
                text = normalize_str(
                    adj.get("recommendation") or adj.get("description")
                ).strip()
            else:
                text = normalize_str(adj).strip()
            if text:
                recs.append(f"Dosage adjustment: {text}")

    # Deduplicate while preserving order
    seen = set()
    deduped: list[str] = []
    for r in recs:
        key = r.strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(r)

    return deduped[:30]


def compute_accuracy(
    state_dict: dict, patient_info_dict: dict
) -> tuple[float, list[str]]:
    """
    Compute calibrated quality metric for UI (0..1).

    Based on confidence_score and pipeline signals.
    Does not alter any clinical decisions (UI/observability only).

    Args:
        state_dict: LangGraph state dictionary
        patient_info_dict: Patient information dictionary

    Returns:
        Tuple of (accuracy_score, factors_list)
    """
    factors: list[str] = []

    base = float(state_dict.get("confidence_score", 0.0) or 0.0)
    accuracy = max(0.0, min(1.0, base))
    factors.append(f"Base: confidence_score={accuracy:.2f}")

    # Anamnesis completeness
    completeness, completeness_factors = patient_completeness(patient_info_dict)
    if completeness < 1.0:
        penalty = 0.8 + (0.2 * completeness)
        accuracy *= penalty
        factors.append(f"Anamnesis penalty (score={completeness:.2f}): x{penalty:.2f}")
        factors.extend(completeness_factors[:4])

    # Partial status (LLM failed at some point)
    status_val = normalize_str(state_dict.get("status")).lower()
    if "partial" in status_val:
        accuracy *= 0.85
        factors.append("Penalty: partial analysis (LLM unavailable): x0.85")

    # ReflectionAgent critique
    critique = normalize_str(state_dict.get("critique_level")).lower()
    critique_multipliers = {
        "pass": 1.00,
        "low": 0.95,
        "medium": 0.85,
        "high": 0.70,
        "critical": 0.50,
    }
    if critique in critique_multipliers:
        mult = critique_multipliers[critique]
        accuracy *= mult
        factors.append(f"CritiqueLevel={critique}: x{mult:.2f}")

    # Refinement cycles
    refinement_count = state_dict.get("refinement_count")
    if refinement_count is None:
        refinement_count = (state_dict.get("final_report") or {}).get(
            "refinement_cycles"
        )
    try:
        refinement_count_int = int(refinement_count or 0)
    except Exception:
        refinement_count_int = 0
    if refinement_count_int > 0:
        mult = 0.95**refinement_count_int
        accuracy *= mult
        factors.append(f"Refinements={refinement_count_int}: x{mult:.2f}")

    # Evidence links
    evidence_links = state_dict.get("evidence_links", [])
    has_evidence = isinstance(evidence_links, list) and len(evidence_links) > 0
    interactions = state_dict.get("interactions", []) or []
    contraindications = state_dict.get("contraindications", []) or []
    if (interactions or contraindications) and not has_evidence:
        accuracy *= 0.85
        factors.append("Penalty: findings without evidence: x0.85")

    accuracy = max(0.0, min(1.0, accuracy))
    return accuracy, factors[:12]
