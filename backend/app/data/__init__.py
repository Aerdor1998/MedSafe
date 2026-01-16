"""
Drug data loader - Consolidated drug information from YAML
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

DATA_DIR = Path(__file__).parent


@lru_cache(maxsize=1)
def load_drug_data() -> Dict[str, Any]:
    """Load drug data from YAML file (cached)"""
    yaml_path = DATA_DIR / "drug_data.yaml"
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_high_risk_classes() -> Dict[str, List[str]]:
    """Get high risk drug classes (MAOI, stimulants, etc.)"""
    data = load_drug_data()
    return data.get("high_risk_drug_classes", {})


def get_population_alerts() -> Dict[str, Dict[str, Any]]:
    """Get population-specific drug alerts"""
    data = load_drug_data()
    return data.get("population_alerts", {})


def get_critical_combinations() -> List[Dict[str, Any]]:
    """Get critical drug combinations"""
    data = load_drug_data()
    return data.get("critical_combinations", [])


def get_critical_interactions() -> Dict[str, Dict[str, Any]]:
    """Get known critical interactions"""
    data = load_drug_data()
    return data.get("critical_interactions", {})


def get_drug_synonyms() -> Dict[str, List[str]]:
    """Get common drug synonyms"""
    data = load_drug_data()
    return data.get("common_synonyms", {})


def get_recommendation_templates() -> Dict[str, Dict[str, Any]]:
    """Get recommendation templates by severity"""
    data = load_drug_data()
    return data.get("recommendation_templates", {})


def get_category_recommendations() -> Dict[str, Dict[str, List[str]]]:
    """Get category-specific recommendations"""
    data = load_drug_data()
    return data.get("category_recommendations", {})


def is_drug_in_list(drug_name: str, drug_list: List[str]) -> bool:
    """Check if drug name matches any item in list (case-insensitive)"""
    drug_lower = drug_name.lower()
    return any(d.lower() in drug_lower or drug_lower in d.lower() for d in drug_list)


def get_population_risk_for_drug(
    drug_name: str, population: str
) -> Optional[Dict[str, Any]]:
    """
    Check if a drug has special risk for a population

    Returns dict with 'level' (contraindicated/high_risk) and 'severity_increase'
    """
    alerts = get_population_alerts().get(population, {})
    drug_lower = drug_name.lower()

    # Check contraindicated
    for contra in alerts.get("contraindicated", []):
        if contra.lower() in drug_lower:
            return {
                "level": "contraindicated",
                "severity_increase": alerts.get("severity_increase", 2),
                "drug": contra,
            }

    # Check high risk
    for high in alerts.get("high_risk", []):
        if high.lower() in drug_lower:
            return {
                "level": "high_risk",
                "severity_increase": alerts.get("severity_increase", 1),
                "drug": high,
            }

    return None
