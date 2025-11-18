"""
Agentes AG2 para o MedSafe

MIGRATION NOTE:
- Sistema principal migrado para LangGraph (ver /backend/app/langgraph_agents/)
- Agents legados movidos para /backend/app/agents_legacy/
- VisionAgent mantido temporariamente até implementação no LangGraph
"""

from .vision import VisionAgent

__all__ = [
    "VisionAgent",
]
