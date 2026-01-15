"""
Legacy Agents for MedSafe

DEPRECATION NOTE:
- Main agent system has been migrated to LangGraph (see /backend/app/langgraph_agents/)
- This module is maintained for backwards compatibility only
- VisionAgent is still used by routers/vision.py until LangGraph vision integration

MIGRATION STATUS:
- orchestrator.py: REMOVED (replaced by services/analysis_orchestrator.py)
- human_in_the_loop.py: REMOVED (replaced by langgraph_agents/hitl_agent.py)
- vision.py: ACTIVE (pending migration to LangGraph)

TODO: Migrate VisionAgent to langgraph_agents/vision_agent.py when LangGraph
      supports image-based workflows efficiently.
"""

from .vision import VisionAgent

__all__ = [
    "VisionAgent",
]
