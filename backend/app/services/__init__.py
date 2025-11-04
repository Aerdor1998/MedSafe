"""
Serviços da aplicação MedSafe
"""

from .drug_interactions import DrugInteractionService, get_interaction_service

__all__ = ["DrugInteractionService", "get_interaction_service"]
