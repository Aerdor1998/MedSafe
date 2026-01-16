"""
TriageAgent - Step 1: "Get the Mission"

PATTERN: Input validation and state initialization (PDF pg 10-13)
SKILLS: @ultrathink, @api-design-principles, @code-review-excellence

RESPONSIBILITIES:
1. Validate patient data and medication input
2. Initialize state with proper defaults
3. Extract structured information from inputs
4. Set up session for multi-agent workflow
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from .base_agent import BaseAgent
from .state import CritiqueLevel, MedSafeState, RiskLevel, SafetyClassification

logger = logging.getLogger(__name__)


class TriageAgent(BaseAgent):
    """
    TriageAgent: First contact in the multi-agent workflow

    MISSION: "Get the Mission" - Understand what the patient needs (PDF pg 10)
    PATTERN: Gateway agent that validates and structures inputs

    SKILLS APPLIED:
    - @ultrathink: Clear input validation logic
    - @api-design-principles: Defensive input handling
    - @code-review-excellence: Comprehensive validation checks
    """

    def __init__(self):
        super().__init__(agent_name="TriageAgent")

    def get_system_prompt(self) -> str:
        """
        System prompt for TriageAgent

        PATTERN: Prompt engineering for structured extraction (PDF pg 39-42)
        """
        return """You are the TriageAgent for MedSafe, a medical decision support system.

Your role is to:
1. Extract and validate patient information
2. Identify the medication being analyzed
3. Extract relevant medical history (conditions, allergies, current medications)
4. Ensure data quality before passing to clinical analysis

You must be:
- Thorough in validating medical data
- Clear about missing or ambiguous information
- Safety-focused (flag incomplete data that could affect safety)

Output format: Structured JSON with validated fields.
"""

    def process(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Process patient data and initialize state

        PATTERN: Think → Act → Observe (PDF pg 10-13)
        RESILIENCE: Continues even if LLM analysis fails

        Args:
            state: Current MedSafeState

        Returns:
            Dict with state updates
        """
        start_time = datetime.now()
        llm_failed = False

        try:
            # Log início do agente
            self.agent_logger.start(
                "Iniciando triagem do paciente",
                medication=state.get("medication_text", "N/A"),
                patient_age=state.get("patient_data", {}).get("age", "N/A"),
            )

            # Validate inputs
            self.agent_logger.progress("Validando campos obrigatórios")
            if not self.validate_state(state, ["patient_data", "medication_text"]):
                raise ValueError(
                    "Missing required fields: patient_data or medication_text"
                )

            patient_data = state["patient_data"]
            medication_text = state["medication_text"]

            self.agent_logger.progress(
                "Dados do paciente validados",
                age=patient_data.get("age", "N/A"),
                conditions_count=len(patient_data.get("conditions", [])),
                medications_count=len(patient_data.get("current_medications", [])),
                allergies_count=len(patient_data.get("allergies", [])),
            )

            # Extract structured information using LLM (may fail)
            self.agent_logger.progress("Analisando dados do paciente com LLM")
            try:
                triage_result = self._analyze_patient_data(
                    patient_data, medication_text
                )
            except Exception as llm_error:
                llm_failed = True
                self.agent_logger.error(f"LLM falhou na análise: {llm_error}")
                logger.warning(
                    f" LLM failed during triage, using fallback: {llm_error}"
                )
                # Fallback: proceed with basic data completeness assessment
                triage_result = {
                    "medication_normalized": medication_text.strip().lower(),
                    "analysis": f"Análise automática não disponível. Medicamento: {medication_text}",
                    "data_completeness": self._assess_data_completeness(patient_data),
                }

            # Initialize state fields
            self.agent_logger.progress("Inicializando campos do estado")
            updates = self._initialize_state(state, triage_result)

            # Update timestamps
            updates["timestamps"] = {
                "triage_start": start_time,
                "triage_end": datetime.now(),
            }

            # Mark if LLM failed for downstream agents to know
            if llm_failed:
                updates["triage_llm_failed"] = True

            # Log completion
            duration = (datetime.now() - start_time).total_seconds()
            self.agent_logger.end(
                "Triagem concluída"
                + (" (parcial - LLM falhou)" if llm_failed else " com sucesso"),
                success=not llm_failed,
                data_completeness=triage_result["data_completeness"]["score"],
                medication=medication_text,
            )

            return updates

        except Exception as e:
            self.agent_logger.error("Falha crítica na triagem", exc_info=True)
            logger.error(f"TriageAgent critical error: {e}")
            # Even on critical error, try to return minimal state initialization
            try:
                patient_data = state.get("patient_data", {})
                medication_text = state.get("medication_text", "unknown")
                fallback_result = {
                    "medication_normalized": (
                        medication_text.strip().lower()
                        if medication_text
                        else "unknown"
                    ),
                    "analysis": f"Erro na triagem: {str(e)}",
                    "data_completeness": {
                        "score": 0.0,
                        "is_complete": False,
                        "critical_missing": ["triage_failed"],
                    },
                }
                updates = self._initialize_state(state, fallback_result)
                updates["timestamps"] = {
                    "triage_start": start_time,
                    "triage_end": datetime.now(),
                }
                updates["error"] = str(e)
                return updates
            except Exception:
                return self.handle_error(state, e, "Failed to triage patient")

    def _analyze_patient_data(
        self, patient_data: Dict[str, Any], medication_text: str
    ) -> Dict[str, Any]:
        """
        Analyze patient data using LLM for extraction and validation

        SKILL: @ultrathink - LLM-assisted structured extraction
        """
        # Build context from patient data
        context = {
            "Age": patient_data.get("age", "Not provided"),
            "Weight": patient_data.get("weight", "Not provided"),
            "Conditions": ", ".join(patient_data.get("conditions", [])) or "None",
            "Allergies": ", ".join(patient_data.get("allergies", [])) or "None",
            "Current Medications": ", ".join(
                patient_data.get("current_medications", [])
            )
            or "None",
        }

        # Construct analysis prompt
        prompt = f"""Analyze the following patient requesting information about medication: {medication_text}

Extract and validate:
1. Is the medication name clear and unambiguous?
2. Are there any missing critical patient data points?
3. Are there any immediate red flags (e.g., known allergies to this medication)?
4. What are the key risk factors for this patient?

Provide a brief structured assessment."""

        # Invoke LLM
        analysis = self.invoke_llm(prompt, context=context)

        return {
            "medication_normalized": medication_text.strip().lower(),
            "analysis": analysis,
            "data_completeness": self._assess_data_completeness(patient_data),
        }

    def _assess_data_completeness(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess completeness of patient data

        SKILL: @code-review-excellence - Defensive data validation
        """
        completeness = {
            "has_age": "age" in patient_data and patient_data["age"] is not None,
            "has_weight": "weight" in patient_data
            and patient_data["weight"] is not None,
            "has_conditions": bool(patient_data.get("conditions", [])),
            "has_allergies": "allergies" in patient_data,  # Can be empty list
            "has_current_medications": "current_medications" in patient_data,
        }

        # Calculate completeness score
        score = sum(completeness.values()) / len(completeness)
        completeness["score"] = score

        # Flag if critical data missing
        critical_missing = []
        if not completeness["has_age"]:
            critical_missing.append("age")
        if not completeness["has_allergies"]:
            critical_missing.append("allergies")
        if not completeness["has_current_medications"]:
            critical_missing.append("current_medications")

        completeness["critical_missing"] = critical_missing
        completeness["is_complete"] = len(critical_missing) == 0

        return completeness

    def _initialize_state(
        self, state: MedSafeState, triage_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Initialize all state fields with proper defaults

        PATTERN: State initialization following TypedDict schema
        SKILL: @ultrathink - Clean state management
        """
        # Generate session ID if not present
        session_id = state.get("session_id") or str(uuid.uuid4())

        return {
            "session_id": session_id,
            "status": "triaged",
            # Messages
            "messages": [
                {
                    "role": "system",
                    "content": f"Patient triaged. Analyzing {state['medication_text']}",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
            # Processing fields (empty, will be filled by other agents)
            "evidence": [],
            "interactions": [],
            "contraindications": [],
            # Reflection fields (initial values)
            "reflection_history": [],
            "critique_level": CritiqueLevel.PASS,
            "needs_refinement": False,
            "refinement_count": 0,
            "feedback": None,
            # Safety fields (default to safe, will be validated)
            "safety_classification": SafetyClassification.SAFE,
            "safety_violations": [],
            "requires_human_review": False,
            "escalation_reasons": [],
            "human_feedback": None,
            "human_approved": False,
            # Output fields (empty, will be filled)
            "risk_level": RiskLevel.LOW,  # Default optimistic, will be updated
            "dosage_adjustments": [],
            "adverse_reactions": [],
            "evidence_links": [],
            "final_report": {},
            "confidence_score": 0.0,
            # Metadata
            "model_used": self.settings.effective_model_name,
            "agent_steps": [
                f"[{datetime.now().isoformat()}] TriageAgent: Triage completed",
                f"   Medication: {state['medication_text']}",
                f"   Data completeness: {triage_result['data_completeness']['score']:.1%}",
            ],
            "error": None,
        }


# Factory function
def create_triage_agent() -> TriageAgent:
    """Create TriageAgent instance"""
    return TriageAgent()
