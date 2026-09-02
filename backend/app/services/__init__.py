"""
Serviços da aplicação MedSafe

IMPORTANT:
This package must remain import-light to avoid circular imports.

Example cycle previously seen:
langgraph_agents -> document_agent -> services.drug_interactions -> services.__init__
-> services.analysis_orchestrator -> langgraph_agents

We keep convenience re-exports via lazy __getattr__ instead of importing
submodules at import time.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .analysis_orchestrator import AnalysisOrchestrator, get_orchestrator
    from .drug_interactions import DrugInteractionService, get_interaction_service
    from .response_formatter import (
        build_recommendations_from_state,
        compute_accuracy,
        normalize_str,
        patient_completeness,
    )

__all__ = [
    "DrugInteractionService",
    "get_interaction_service",
    "normalize_str",
    "patient_completeness",
    "build_recommendations_from_state",
    "compute_accuracy",
    "AnalysisOrchestrator",
    "get_orchestrator",
]


def __getattr__(name: str) -> Any:
    if name in {"DrugInteractionService", "get_interaction_service"}:
        from .drug_interactions import DrugInteractionService, get_interaction_service

        return (
            DrugInteractionService
            if name == "DrugInteractionService"
            else get_interaction_service
        )

    if name in {
        "normalize_str",
        "patient_completeness",
        "build_recommendations_from_state",
        "compute_accuracy",
    }:
        from . import response_formatter as rf

        return getattr(rf, name)

    if name in {"AnalysisOrchestrator", "get_orchestrator"}:
        from .analysis_orchestrator import AnalysisOrchestrator, get_orchestrator

        return (
            AnalysisOrchestrator if name == "AnalysisOrchestrator" else get_orchestrator
        )

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
