"""
MedSafe LangGraph StateGraph - Multi-Agent Orchestration

PATTERN: StateGraph with conditional edges and checkpointing (PDF pg 22-24)
SKILLS: @ultrathink, @api-design-principles, @debugging-strategies

ARCHITECTURE:
This creates the complete multi-agent workflow with:
1. Sequential agent execution
2. Reflection loops for quality assurance
3. HITL interruption points
4. PostgreSQL checkpointing for persistence

WORKFLOW:
  START
    ↓
  TriageAgent (Step 1: Get the Mission)
    ↓
  DocumentAgent (Step 2: Scan the Scene)
    ↓
  ClinicalAgent (Step 3: Think It Through)
    ↓
  ReflectionAgent (Step 5: Observe) ─┐
    │                                 │
    ├─→ needs_refinement? ───YES─────┘ (loop back to ClinicalAgent, max 3 cycles)
    │
    NO
    ↓
  SafetyAgent (Step 4: Take Action)
    │
    ├─→ requires_hitl? ───YES──→ HITLAgent (INTERRUPT) ─→ (wait for human)
    │
    NO
    ↓
  END (Final Report)
"""

import logging
import threading
from datetime import datetime
from typing import Literal

from langgraph.graph import END, StateGraph

from .clinical_agent import create_clinical_agent
from .config import get_settings
from .document_agent import create_document_agent
from .hitl_agent import create_hitl_agent
from .reflection_agent import create_reflection_agent
from .safety_agent import create_safety_agent
from .state import MedSafeState

# Import all agents
from .triage_agent import create_triage_agent

# NOTE: Checkpointer import removed - state is persisted via AnalysisJob table


logger = logging.getLogger(__name__)


def finalize_report(state: MedSafeState) -> MedSafeState:
    """
    Finalize the analysis report

    PATTERN: Report generation

    NOTE: Module-level so the HITL approve endpoint can finalize a saved
    state directly (the graph has no checkpointer; re-invoking it with a
    full state would re-run the whole pipeline from START).
    """
    settings = get_settings()
    logger.info("📄 Finalizing report...")

    final_report = {
        "session_id": state.get("session_id"),
        "timestamp": datetime.now().isoformat(),
        "medication": state.get("medication_text"),
        "risk_level": (
            state.get("risk_level", "unknown").value
            if hasattr(state.get("risk_level"), "value")
            else state.get("risk_level", "unknown")
        ),
        "confidence_score": round(float(state.get("confidence_score", 0.0) or 0.0), 4),
        "risk_score": state.get("risk_score"),
        "patient_risk_factors": state.get("patient_risk_factors", []),
        # Findings
        "interactions": state.get("interactions", []),
        "contraindications": state.get("contraindications", []),
        # Recommendations
        "dosage_adjustments": state.get("dosage_adjustments", []),
        "adverse_reactions": state.get("adverse_reactions", []),
        # Evidence
        "evidence_links": state.get("evidence_links", []),
        # Quality metrics
        "critique_level": (
            state.get("critique_level", "unknown").value
            if hasattr(state.get("critique_level"), "value")
            else str(state.get("critique_level", "unknown"))
        ),
        "refinement_cycles": state.get("refinement_count", 0),
        "safety_classification": (
            state.get("safety_classification", "unknown").value
            if hasattr(state.get("safety_classification"), "value")
            else str(state.get("safety_classification", "unknown"))
        ),
        "human_reviewed": state.get("human_approved", False),
        # Metadata
        "agent_steps": state.get("agent_steps", []),
        "model_used": state.get("model_used", settings.effective_model_name),
        "timestamps": state.get("timestamps", {}),
    }

    return {
        **state,
        "final_report": final_report,
        "status": "completed",
    }


def create_medsafe_graph() -> StateGraph:
    """
    Create the complete MedSafe multi-agent workflow graph

    PATTERN: StateGraph orchestration (PDF pg 22-24)
    SKILLS: @ultrathink - Clear workflow architecture

    Returns:
        Compiled StateGraph with checkpointing
    """
    logger.info("🏗️  Building MedSafe LangGraph...")

    # Initialize settings
    settings = get_settings()

    # Create agents
    logger.info("   Creating agents...")
    triage_agent = create_triage_agent()
    document_agent = create_document_agent()
    clinical_agent = create_clinical_agent()
    reflection_agent = create_reflection_agent()
    safety_agent = create_safety_agent()
    hitl_agent = create_hitl_agent()

    # Define node functions (wrapper around agent.process)
    def triage_node(state: MedSafeState) -> MedSafeState:
        """Triage node: Initialize and validate patient data"""
        updates = triage_agent.process(state)
        return {**state, **updates}

    def document_node(state: MedSafeState) -> MedSafeState:
        """Document node: Retrieve medical evidence"""
        updates = document_agent.process(state)
        return {**state, **updates}

    def clinical_node(state: MedSafeState) -> MedSafeState:
        """Clinical node: Analyze interactions and contraindications"""
        updates = clinical_agent.process(state)
        return {**state, **updates}

    def reflection_node(state: MedSafeState) -> MedSafeState:
        """Reflection node: Quality assurance and critique"""
        updates = reflection_agent.process(state)
        merged_state = {**state, **updates}

        # Increment refinement_count if refinement is needed
        # This ensures the count is incremented BEFORE the next clinical pass
        if updates.get("needs_refinement", False):
            current_count = state.get("refinement_count", 0)
            merged_state["refinement_count"] = current_count + 1
            logger.info(f"Refinement count incremented to {current_count + 1}")

        return merged_state

    def safety_node(state: MedSafeState) -> MedSafeState:
        """Safety node: Validate outputs and check guardrails"""
        updates = safety_agent.process(state)
        return {**state, **updates}

    def hitl_node(state: MedSafeState) -> MedSafeState:
        """HITL node: Human physician review"""
        updates = hitl_agent.process(state)
        return {**state, **updates}

    # Define conditional edge functions
    def should_refine(state: MedSafeState) -> Literal["refine", "continue"]:
        """
        Decide if clinical analysis needs refinement

        PATTERN: Reflection loop (PDF pg 25)
        """
        needs_refinement = state.get("needs_refinement", False)
        refinement_count = state.get("refinement_count", 0)
        max_refinements = settings.max_reflection_cycles

        if needs_refinement and refinement_count < max_refinements:
            logger.info(f"🔄 Refinement cycle {refinement_count + 1}/{max_refinements}")
            # Increment count is now done in reflection_node wrapper
            return "refine"
        else:
            if refinement_count >= max_refinements:
                logger.warning(f" Max refinement cycles reached ({max_refinements})")
            return "continue"

    def should_escalate_to_hitl(state: MedSafeState) -> Literal["hitl", "finalize"]:
        """
        Decide if human review is needed

        PATTERN: HITL escalation (PDF pg 22, 32)
        """
        requires_hitl = state.get("requires_human_review", False)

        if requires_hitl and settings.enable_hitl:
            logger.info(
                f" Escalating to HITL: {', '.join(state.get('escalation_reasons', []))}"
            )
            return "hitl"
        else:
            logger.info("No HITL required - proceeding to finalization")
            return "finalize"

    # Create the graph (finalize_report is module-level — see above)
    logger.info("   Building graph structure...")
    workflow = StateGraph(MedSafeState)

    # Add nodes
    workflow.add_node("triage", triage_node)
    workflow.add_node("document", document_node)
    workflow.add_node("clinical", clinical_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("safety", safety_node)
    workflow.add_node("hitl", hitl_node)
    workflow.add_node("finalize", finalize_report)

    # Define edges
    # Entry point
    workflow.set_entry_point("triage")

    # Linear flow: triage → document → clinical
    workflow.add_edge("triage", "document")
    workflow.add_edge("document", "clinical")

    # Clinical → Reflection
    workflow.add_edge("clinical", "reflection")

    # Reflection → conditional (refine or continue)
    workflow.add_conditional_edges(
        "reflection",
        should_refine,
        {
            "refine": "clinical",  # Loop back to clinical for refinement
            "continue": "safety",  # Move to safety validation
        },
    )

    # Safety → conditional (HITL or finalize)
    workflow.add_conditional_edges(
        "safety",
        should_escalate_to_hitl,
        {
            "hitl": "hitl",  # Escalate to human review
            "finalize": "finalize",  # Skip HITL, go to finalization
        },
    )

    # HITL → finalize (after human review)
    workflow.add_edge("hitl", "finalize")

    # Finalize → END
    workflow.add_edge("finalize", END)

    # NOTE: We're NOT using LangGraph checkpointing because:
    # 1. Our AnalysisJob table already persists workflow state (durable)
    # 2. Sync PostgresSaver doesn't support ainvoke() (raises NotImplementedError)
    # 3. State is serialized via _json_serialize_state() to the DB
    #
    # For HITL patterns, the interrupt happens via the job status ('awaiting_review')
    # and state is recovered from the database, not from LangGraph's checkpointer.
    logger.info(
        "   Skipping LangGraph checkpointing (using AnalysisJob table for state)"
    )

    # Compile graph WITHOUT checkpointer to support ainvoke()
    logger.info("   Compiling graph...")
    compiled_graph = workflow.compile(
        # No checkpointer - state persisted via AnalysisJob table
        interrupt_before=(
            ["hitl"] if settings.enable_hitl else []
        ),  # Interrupt at HITL for human input
    )

    logger.info("MedSafe LangGraph compiled successfully")
    logger.info("   Agents: Triage, Document, Clinical, Reflection, Safety, HITL")
    logger.info(f"   Reflection cycles: max {settings.max_reflection_cycles}")
    logger.info(f"   HITL enabled: {settings.enable_hitl}")
    logger.info(f"   Safety guardrails: {settings.enable_safety_guardrails}")

    return compiled_graph


# Global graph instance with thread-safety

_graph = None
_graph_lock = threading.Lock()


def get_graph() -> StateGraph:
    """
    Get global graph instance (thread-safe singleton).

    SKILL: @api-design-principles - Singleton pattern
    SKILL: @python-performance-optimization - Thread-safe initialization

    Uses double-checked locking pattern for optimal performance:
    - First check without lock (fast path for already-initialized case)
    - Second check with lock (thread-safe initialization)
    """
    global _graph

    # Fast path: already initialized (no lock needed)
    if _graph is not None:
        return _graph

    # Slow path: need to initialize (with lock)
    with _graph_lock:
        # Double-check after acquiring lock
        if _graph is None:
            _graph = create_medsafe_graph()

    return _graph


def reset_graph():
    """
    Reset graph (useful for testing).

    Thread-safe reset using the global lock.
    """
    global _graph
    with _graph_lock:
        _graph = None
