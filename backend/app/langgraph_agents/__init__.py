"""
MedSafe LangGraph Multi-Agent System

ARCHITECTURE: Level 3 - Collaborative Multi-Agent System
Based on: "Introduction to Agents" (Google, Nov 2025)

SKILLS APPLIED:
- @ultrathink: Elegant architecture with clear separation of concerns
- @api-design-principles: Clean interfaces between agents
- @debugging-strategies: Comprehensive logging and observability
- @code-review-excellence: Self-documenting code with type hints

AGENTS:
1. TriageAgent - Processes patient data
2. DocumentAgent - RAG for medical evidence (PDF pg 21)
3. VisionAgent - OCR and visual analysis with qwen2.5-vl (NEW)
4. ClinicalAgent - Applies medical rules with Reflection (PDF pg 25)
5. SafetyAgent - Guardrails validation (PDF pg 34-38)
6. HITLAgent - Human-in-the-Loop approval (PDF pg 22, 32)
7. ReflectionAgent - Self-critique pattern (PDF pg 25)

ORCHESTRATION: StateGraph with conditional loops and checkpointing
"""

from .checkpointing import MedSafeCheckpointer, get_checkpointer
from .clinical_agent import create_clinical_agent
from .config import LangGraphSettings, get_settings
from .document_agent import create_document_agent
from .graph import create_medsafe_graph, get_graph, reset_graph
from .hitl_agent import create_hitl_agent
from .reflection_agent import create_reflection_agent
from .safety_agent import create_safety_agent
from .state import CritiqueLevel, MedSafeState, RiskLevel, SafetyClassification

# Import agent factory functions
from .triage_agent import create_triage_agent
from .vision_agent import create_vision_agent

__version__ = "2.0.0-langgraph"
__all__ = [
    # State
    "MedSafeState",
    "RiskLevel",
    "CritiqueLevel",
    "SafetyClassification",
    # Config
    "get_settings",
    "LangGraphSettings",
    # Checkpointing
    "get_checkpointer",
    "MedSafeCheckpointer",
    # Graph
    "get_graph",
    "create_medsafe_graph",
    "reset_graph",
    # Agents
    "create_triage_agent",
    "create_document_agent",
    "create_vision_agent",
    "create_clinical_agent",
    "create_reflection_agent",
    "create_safety_agent",
    "create_hitl_agent",
]
