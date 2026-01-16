"""
MedSafe State Schema - The "Nervous System" of the Multi-Agent System

PATTERN: StateGraph with TypedDict (PDF pg 8-9, pg 22-24)
SKILL: @ultrathink - Clear, typed state management

This state flows through all agents in the "Think, Act, Observe" loop.
Each agent reads from and writes to this shared state.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class RiskLevel(str, Enum):
    """Risk classification levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CritiqueLevel(str, Enum):
    """Reflection critique severity (PDF pg 25)"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    PASS = "pass"


class SafetyClassification(str, Enum):
    """Safety guardrails classification (PDF pg 34-38)"""

    SAFE = "safe"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


def add_messages(existing: List[Dict], new: List[Dict]) -> List[Dict]:
    """
    Reducer function for messages - maintains conversation history
    PATTERN: Message accumulation (LangGraph standard)
    """
    return existing + new


class MedSafeState(TypedDict):
    """
    Complete state for MedSafe multi-agent workflow

    ARCHITECTURE: Central state shared across all agents (PDF pg 8-9)
    PATTERN: TypedDict with reducers for specific fields

    The state flows through 5 steps (PDF pg 10-13):
    1. Get the Mission - Initial patient data
    2. Scan the Scene - Evidence gathering
    3. Think It Through - Clinical analysis
    4. Take Action - Generate recommendations
    5. Observe and Iterate - Reflection & refinement
    """

    # ========================================================================
    # INPUT: Initial patient data (Step 1: Get the Mission)
    # ========================================================================
    patient_data: Dict[str, Any]  # Age, weight, conditions, etc.
    medication_text: str  # Drug name to analyze
    session_id: str  # Unique session identifier
    triage_id: Optional[str]  # Database triage ID

    # ========================================================================
    # PROCESSING: Intermediate data (Step 2: Scan the Scene)
    # ========================================================================
    messages: Annotated[List[Dict[str, str]], add_messages]  # Conversation history
    evidence: List[Dict[str, Any]]  # RAG results from DocumentAgent
    interactions: List[Dict[str, Any]]  # Drug interactions found
    contraindications: List[Dict[str, Any]]  # Patient-specific warnings

    # ========================================================================
    # REFLECTION: Iterative refinement (Step 3: Think It Through)
    # Based on "Iterative Refinement Pattern" (PDF pg 25)
    # ========================================================================
    reflection_history: List[Dict[str, Any]]  # All reflection cycles
    critique_level: CritiqueLevel  # Current quality assessment
    needs_refinement: bool  # Should we loop back to ClinicalAgent?
    refinement_count: int  # Number of refinement cycles (max 3)
    feedback: Optional[str]  # Reflection feedback for next iteration

    # ========================================================================
    # SAFETY: Guardrails & HITL (Step 4: Take Action)
    # Based on "Securing Agents" (PDF pg 34-38) and HITL (PDF pg 22, 32)
    # ========================================================================
    safety_classification: SafetyClassification  # Safe, needs_review, blocked
    safety_violations: List[Dict[str, str]]  # Any guardrail violations
    requires_human_review: bool  # HITL trigger flag
    escalation_reasons: List[str]  # Why human review is needed
    human_feedback: Optional[Dict[str, Any]]  # Response from physician
    human_approved: bool  # Final human approval status

    # ========================================================================
    # OUTPUT: Final analysis (Step 5: Observe and Iterate)
    # ========================================================================
    risk_level: RiskLevel  # Overall risk assessment
    dosage_adjustments: List[Dict[str, Any]]  # Dose recommendations
    adverse_reactions: List[Dict[str, Any]]  # Potential side effects
    evidence_links: List[str]  # Scientific sources
    final_report: Dict[str, Any]  # Complete structured report
    confidence_score: float  # Model confidence (0.0-1.0)

    # ========================================================================
    # STRUCTURED RECOMMENDATIONS (New - Clinical Rules Engine)
    # ========================================================================
    structured_recommendations: Dict[str, Any]  # Recommendations by category
    # Example structure:
    # {
    #   "header": "ALERTA CRITICO",
    #   "immediate_actions": ["NAO ADMINISTRAR sem avaliacao medica"],
    #   "monitoring_required": ["ECG basal e seriado", "PA e FC diarios"],
    #   "laboratory_tests": ["Eletrolitos", "Funcao renal"],
    #   "patient_alerts": ["Palpitacoes", "Tontura"],
    #   "alternatives": ["Droga X", "Droga Y"],
    #   "follow_up": ["Retorno em 1 semana"],
    #   "patient_counseling": ["Evitar atividades que exijam alerta"]
    # }

    # ========================================================================
    # METADATA: Agent Ops & Observability (PDF pg 27-31)
    # ========================================================================
    model_used: str  # "ollama/qwen3:8b"
    agent_steps: List[str]  # Trace of agent execution path
    timestamps: Dict[str, datetime]  # Performance tracking
    error: Optional[str]  # Any errors encountered
    status: str  # "pending", "processing", "completed", "blocked"
