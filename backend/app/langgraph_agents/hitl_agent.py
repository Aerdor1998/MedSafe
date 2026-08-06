"""
HITLAgent - Human-in-the-Loop Pattern

PATTERN: Interrupt pattern for human oversight (PDF pg 22, 32)
SKILLS: @ultrathink, @api-design-principles, @code-review-excellence

RESPONSIBILITIES:
1. Present analysis to human physician for review
2. Wait for human feedback/approval
3. Incorporate human feedback into final recommendations
4. Handle approval/rejection workflows
"""

import logging
from datetime import datetime
from typing import Any, Dict

from .base_agent import BaseAgent
from .state import MedSafeState

logger = logging.getLogger(__name__)


class HITLAgent(BaseAgent):
    """
    HITLAgent: Human-in-the-Loop checkpoint

    PATTERN: Interrupt Pattern (PDF pg 22, 32)
    - Pauses workflow for human review
    - Presents structured analysis summary
    - Waits for physician approval/feedback
    - Resumes workflow with human input

    ARCHITECTURE:
    Uses LangGraph checkpointing to persist state during human review.
    The graph execution interrupts at this node and waits for external
    input (physician's decision) before continuing.

    SKILLS APPLIED:
    - @ultrathink: Clean human-agent collaboration pattern
    - @api-design-principles: Clear interface for human feedback
    - @code-review-excellence: Comprehensive review presentation
    """

    def __init__(self):
        super().__init__(agent_name="HITLAgent")

    def get_system_prompt(self) -> str:
        """
        System prompt for HITLAgent

        PATTERN: Human-centered communication
        """
        return """You are the HITLAgent for MedSafe, facilitating physician oversight.

Your role is to:
1. Summarize the clinical analysis clearly for physicians
2. Highlight key findings and concerns
3. Present escalation reasons transparently
4. Format information for rapid clinical decision-making

Your summary should be:
- Concise but complete
- Clinically relevant
- Action-oriented
- Easy to scan (bullet points, clear sections)

Remember: The physician has limited time and needs to quickly understand
the safety concerns and make an informed decision.
"""

    def process(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Prepare analysis for human review

        PATTERN: Think → Act → Observe (PDF pg 10-13, step 4)

        NOTE: In LangGraph, this node will cause an INTERRUPT.
        The execution will pause here and wait for human input via
        the API endpoint that updates the checkpoint with human feedback.

        Args:
            state: Current MedSafeState

        Returns:
            Dict with review summary for physician
        """
        try:
            start_time = datetime.now()
            self.log_step(state, "Preparing analysis for human review")

            # Check if we already have human feedback (resuming after interrupt)
            if state.get("human_feedback") is not None:
                return self._process_human_feedback(state)

            # First time: prepare review package for physician
            review_package = self._prepare_review_package(state)

            # Update state
            updates = {
                "status": "awaiting_human_review",
                "review_package": review_package,  # For API to display to physician
            }

            # Update timestamps
            if "timestamps" not in state:
                updates["timestamps"] = {}
            updates["timestamps"]["hitl_started"] = datetime.now()

            duration = (datetime.now() - start_time).total_seconds()
            self.log_step(state, f"Review package prepared in {duration:.2f}s")

            logger.info(" HITLAgent: Review package prepared")
            logger.info(
                f"   Escalation reasons: {', '.join(state.get('escalation_reasons', []))}"
            )
            logger.info("   Awaiting physician decision...")

            return updates

        except Exception as e:
            return self.handle_error(state, e, "Failed to prepare HITL review")

    def _prepare_review_package(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Prepare comprehensive review package for physician

        SKILL: @code-review-excellence - Clear, structured presentation
        """
        # Generate executive summary using LLM
        summary = self._generate_executive_summary(state)

        # Structure review package
        package = {
            "timestamp": datetime.now().isoformat(),
            "session_id": state.get("session_id"),
            # Executive summary
            "executive_summary": summary,
            # Key metrics
            "metrics": {
                "risk_level": (
                    state.get("risk_level", "unknown").value
                    if hasattr(state.get("risk_level"), "value")
                    else state.get("risk_level", "unknown")
                ),
                "confidence_score": state.get("confidence_score", 0.0),
                "interactions_count": len(state.get("interactions", [])),
                "contraindications_count": len(state.get("contraindications", [])),
                "safety_violations_count": len(state.get("safety_violations", [])),
            },
            # Escalation reasons
            "escalation_reasons": state.get("escalation_reasons", []),
            # Detailed findings
            "interactions": state.get("interactions", []),
            "contraindications": state.get("contraindications", []),
            "safety_violations": state.get("safety_violations", []),
            # Current recommendations
            "recommendations": {
                "dosage_adjustments": state.get("dosage_adjustments", []),
                "adverse_reactions": state.get("adverse_reactions", []),
            },
            # Patient context
            "patient_context": {
                "medication": state.get("medication_text", "Unknown"),
                "age": state.get("patient_data", {}).get("age"),
                "conditions": state.get("patient_data", {}).get("conditions", []),
                "current_medications": state.get("patient_data", {}).get(
                    "current_medications", []
                ),
                "allergies": state.get("patient_data", {}).get("allergies", []),
            },
        }

        return package

    def _generate_executive_summary(self, state: MedSafeState) -> str:
        """
        Generate concise executive summary for physician

        SKILL: @ultrathink - LLM-powered summarization
        """
        medication = state.get("medication_text", "Unknown medication")
        risk_level = state.get("risk_level", "unknown")
        interactions = state.get("interactions", [])
        contraindications = state.get("contraindications", [])

        # Build context
        context = {
            "Medication": medication,
            "Risk Level": (
                risk_level.value if hasattr(risk_level, "value") else str(risk_level)
            ),
            "Interactions": len(interactions),
            "Contraindications": len(contraindications),
            "Confidence": f"{state.get('confidence_score', 0.0):.1%}",
        }

        # Key findings summary
        critical_findings = []
        for item in interactions + contraindications:
            if item.get("severity") == "critical":
                critical_findings.append(item.get("description", "Unknown")[:100])

        findings_text = (
            "\n".join(f"- {f}" for f in critical_findings[:3])
            if critical_findings
            else "No critical findings"
        )

        prompt = f"""Generate a concise executive summary for a physician reviewing this case:

**Key Findings:**
{findings_text}

**Escalation Reasons:**
{', '.join(state.get('escalation_reasons', []))}

Write a 2-3 sentence summary that:
1. States the clinical concern clearly
2. Highlights the most critical finding
3. Indicates what decision is needed

Be direct and action-oriented."""

        summary = self.invoke_llm(prompt, context=context)

        return summary

    def _process_human_feedback(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Process feedback from physician after review

        PATTERN: Resuming after interrupt (PDF pg 22, 32)
        SKILL: @api-design-principles - Clean feedback integration
        """
        self.log_step(state, "Processing physician feedback")

        human_feedback = state["human_feedback"]

        # Extract decision
        approved = human_feedback.get("approved", False)
        physician_notes = human_feedback.get("notes", "")
        modifications = human_feedback.get("modifications", {})

        logger.info(
            f" HITLAgent: Physician decision = {'APPROVED' if approved else 'REJECTED'}"
        )
        if physician_notes:
            logger.info(f"   Notes: {physician_notes[:100]}")

        # Apply modifications if provided
        updates = {
            "human_approved": approved,
            "status": "human_reviewed",
        }

        # Apply physician modifications
        if modifications:
            if "risk_level" in modifications:
                updates["risk_level"] = modifications["risk_level"]
                logger.info(
                    f"   Physician modified risk level to: {modifications['risk_level']}"
                )

            if "dosage_adjustments" in modifications:
                updates["dosage_adjustments"] = modifications["dosage_adjustments"]

            if "additional_warnings" in modifications:
                # Add physician's additional warnings
                additional = modifications["additional_warnings"]
                current_adverse = state.get("adverse_reactions", [])
                current_adverse.append(
                    {
                        "description": additional,
                        "source": "Physician Override",
                    }
                )
                updates["adverse_reactions"] = current_adverse

        # Update timestamps
        if "timestamps" not in state:
            updates["timestamps"] = {}
        updates["timestamps"]["hitl_completed"] = datetime.now()

        # Calculate HITL duration
        if state.get("timestamps", {}).get("hitl_started"):
            hitl_duration = (
                datetime.now() - state["timestamps"]["hitl_started"]
            ).total_seconds()
            logger.info(f"   HITL review duration: {hitl_duration:.1f}s")

        self.log_step(
            state,
            f"Physician feedback processed: {'APPROVED' if approved else 'REJECTED'}",
        )

        return updates


# Factory function
def create_hitl_agent() -> HITLAgent:
    """Create HITLAgent instance"""
    return HITLAgent()
