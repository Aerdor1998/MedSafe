"""
Analysis Orchestrator Service

Centralizes the medication analysis workflow to eliminate DRY violations
between v1 and v2 endpoints.

Responsibilities:
- Create triage records
- Run LangGraph analysis
- Save reports to database
- Format responses for different API versions
"""

import logging
import uuid
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, Optional
from uuid import UUID

from ..config import settings
from ..db.database import get_db_context
from ..db.models import AnalysisJob, Report, Triage
from ..langgraph_agents import get_graph
from ..langgraph_agents.config import get_settings as get_langgraph_settings
from .response_formatter import (
    build_recommendations_from_state,
    compute_accuracy,
    normalize_str,
)


def _json_serialize_state(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serializable objects to JSON-compatible types.

    Handles:
    - datetime/date objects -> ISO format strings
    - UUID objects -> string representation
    - Enum values -> their .value
    - MappingProxyType (read-only dicts) -> regular dicts
    - Objects with __dict__ -> recursively serialized dicts
    - Other non-serializable objects -> string representation

    This fixes errors like:
    - 'Object of type datetime is not JSON serializable'
    - 'Object of type mappingproxy is not JSON serializable'
    - 'Object of type RiskLevel is not JSON serializable'
    """
    # Handle None early
    if obj is None:
        return None

    # Handle basic JSON-serializable types (fast path)
    if isinstance(obj, (str, int, float, bool)):
        return obj

    # Handle datetime/date
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    # Handle UUID
    if isinstance(obj, UUID):
        return str(obj)

    # Handle Enum (like RiskLevel, CritiqueLevel, etc.)
    if isinstance(obj, Enum):
        return obj.value

    # Handle MappingProxyType (read-only dict view used by Python internals)
    if isinstance(obj, MappingProxyType):
        return {k: _json_serialize_state(v) for k, v in obj.items()}

    # Handle dict
    if isinstance(obj, dict):
        return {str(k): _json_serialize_state(v) for k, v in obj.items()}

    # Handle list/tuple
    if isinstance(obj, (list, tuple)):
        return [_json_serialize_state(item) for item in obj]

    # Handle set/frozenset
    if isinstance(obj, (set, frozenset)):
        return [_json_serialize_state(item) for item in obj]

    # Handle bytes
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")

    # Handle objects with __dict__ (dataclasses, custom objects)
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        try:
            return _json_serialize_state(vars(obj))
        except Exception:
            pass

    # Fallback: convert to string
    try:
        return str(obj)
    except Exception:
        return f"<non-serializable: {type(obj).__name__}>"


logger = logging.getLogger(__name__)


class AnalysisOrchestrator:
    """
    Orchestrates medication analysis workflow.

    Provides a unified interface for both v1 (legacy) and v2 endpoints.
    """

    async def create_triage(
        self,
        patient_data: Dict[str, Any],
        medication: str,
        user_id: Optional[str] = None,
        notes: Optional[str] = None,
        save_to_db: bool = True,
    ) -> Optional[str]:
        """
        Create a triage record in the database.

        Args:
            patient_data: Patient information dictionary
            medication: Medication name being analyzed
            user_id: User ID for tracking
            notes: Additional notes
            save_to_db: Whether to persist to database

        Returns:
            Triage ID if saved, None otherwise
        """
        if not save_to_db:
            return None

        with get_db_context() as db:
            # Extract patient data with compatibility for different field names
            meds_in_use = patient_data.get(
                "current_medications", patient_data.get("meds_in_use", [])
            )
            conditions = patient_data.get(
                "conditions", patient_data.get("cid_codes", [])
            )

            triage = Triage(
                user_id=user_id,
                age=patient_data.get("age"),
                weight=patient_data.get("weight"),
                pregnant=patient_data.get("pregnant", False),
                cid_codes=conditions,
                meds_in_use=[medication]
                + (meds_in_use if isinstance(meds_in_use, list) else []),
                allergies=patient_data.get("allergies", []),
                renal_function=patient_data.get("renal_function"),
                hepatic_function=patient_data.get("hepatic_function"),
                notes=notes,
                status="pending",
            )
            db.add(triage)
            db.commit()
            db.refresh(triage)

            logger.info(f"Triage created: {triage.id}")
            return str(triage.id)

    async def create_analysis_job(
        self,
        *,
        session_id: str,
        triage_id: Optional[str],
        user_id: Optional[str],
        medication: str,
        patient_data: Dict[str, Any],
        notes: Optional[str],
        model_override: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        """
        Create a durable AnalysisJob row used by the worker.

        The job stores a snapshot of the request (payload) and will be updated
        with the latest workflow state (state) during/after execution.

        Args:
            idempotency_key: Optional key for deduplication (stored in payload)
        """
        payload: Dict[str, Any] = {
            "patient_data": patient_data,
            "medication": medication,
            "notes": notes,
            "triage_id": triage_id,
            "model_override": model_override,
            "idempotency_key": idempotency_key,  # Store for deduplication
        }

        with get_db_context() as db:
            job = AnalysisJob(
                session_id=session_id,
                triage_id=triage_id,
                user_id=user_id,
                status="pending",
                payload=payload,
                state={},
            )
            db.add(job)

            # Attach job_id to triage for easier correlation (optional)
            if triage_id:
                db_triage = db.query(Triage).filter(Triage.id == triage_id).first()
                if db_triage:
                    db_triage.job_id = session_id

            db.commit()
            db.refresh(job)
            return str(job.id)

    async def update_job(
        self,
        *,
        job_id: str,
        status: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
        last_error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        increment_retries: bool = False,
    ) -> None:
        """Update job status/state/error fields."""
        with get_db_context() as db:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if not job:
                return
            if status is not None:
                job.status = status
            if state is not None:
                # Serialize datetime/UUID objects to JSON-compatible types
                job.state = _json_serialize_state(state)
            if last_error is not None:
                job.last_error = last_error
            if started_at is not None:
                job.started_at = started_at
            if finished_at is not None:
                job.finished_at = finished_at
            if increment_retries:
                job.retries = int(job.retries or 0) + 1
            db.commit()

    async def get_job_by_session(self, session_id: str) -> Optional[AnalysisJob]:
        """Fetch job by session_id."""
        with get_db_context() as db:
            return (
                db.query(AnalysisJob)
                .filter(AnalysisJob.session_id == session_id)
                .first()
            )

    async def run_analysis(
        self,
        patient_data: Dict[str, Any],
        medication_text: str,
        session_id: Optional[str] = None,
        triage_id: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run LangGraph analysis workflow.

        Args:
            patient_data: Patient information dictionary
            medication_text: Medication name/text to analyze
            session_id: Session ID for tracking (generated if not provided)
            triage_id: Associated triage ID
            model_override: Optional model to use instead of default

        Returns:
            Analysis result dictionary from LangGraph
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        # Normalize patient data field names
        current_meds = patient_data.get(
            "current_medications", patient_data.get("meds_in_use", [])
        )
        conditions = patient_data.get("conditions", patient_data.get("cid_codes", []))

        # Create initial state for LangGraph
        initial_state = {
            "patient_data": {
                "age": patient_data.get("age", 0),
                "weight": patient_data.get("weight"),
                "conditions": conditions,
                "current_medications": current_meds,
                "allergies": patient_data.get("allergies", []),
                "pregnant": patient_data.get("pregnant", False),
                "renal_function": patient_data.get("renal_function"),
                "hepatic_function": patient_data.get("hepatic_function"),
            },
            "medication_text": medication_text or "unknown",
            "session_id": session_id,
            "triage_id": triage_id,
            "model_override": model_override,
        }

        logger.info(f"Starting LangGraph analysis (session: {session_id})")

        # Get graph and execute
        graph = get_graph()
        config = {
            "configurable": {
                "thread_id": session_id,
                "model_override": model_override,
            }
        }

        result = await graph.ainvoke(initial_state, config)

        logger.info(f"Analysis completed (session: {session_id})")
        logger.info(f"   Risk: {result.get('risk_level', 'unknown')}")
        logger.info(f"   Interactions: {len(result.get('interactions', []))}")
        logger.info(f"   Contraindications: {len(result.get('contraindications', []))}")

        return result

    async def save_report(
        self,
        triage_id: str,
        result: Dict[str, Any],
    ) -> Optional[str]:
        """
        Save analysis report to database.

        Args:
            triage_id: Associated triage ID
            result: Analysis result from LangGraph

        Returns:
            Report ID if saved, None otherwise
        """
        if not triage_id:
            return None

        with get_db_context() as db:
            report = Report(
                triage_id=triage_id,
                risk_level=str(result.get("risk_level", "unknown")),
                contraindications=result.get("contraindications", []),
                interactions=result.get("interactions", []),
                dosage_adjustments=result.get("dosage_adjustments", []),
                adverse_reactions=result.get("adverse_reactions", []),
                evidence_links=result.get("evidence_links", []),
                model_used=result.get("model_used", settings.ollama_llm),
                confidence_score=result.get("confidence_score", 0.0),
                is_final=not result.get("requires_human_review", False),
            )
            db.add(report)

            # Update triage status
            db_triage = db.query(Triage).filter(Triage.id == triage_id).first()
            if db_triage:
                db_triage.status = (
                    "completed"
                    if not result.get("requires_human_review")
                    else "awaiting_review"
                )

            db.commit()
            db.refresh(report)

            logger.info(f"Report saved: {report.id}")
            return str(report.id)

    async def update_triage_status(self, triage_id: str, status: str) -> None:
        """Update triage status in database."""
        if not triage_id:
            return

        with get_db_context() as db:
            db_triage = db.query(Triage).filter(Triage.id == triage_id).first()
            if db_triage:
                db_triage.status = status
                db.commit()

    def format_v2_response(
        self,
        result: Dict[str, Any],
        session_id: str,
        triage_id: Optional[str] = None,
        report_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Format analysis result for v2 API response.

        Args:
            result: LangGraph analysis result
            session_id: Session ID
            triage_id: Optional triage ID
            report_id: Optional report ID

        Returns:
            Formatted v2 response dictionary
        """
        # Build structured recommendations if available
        structured_recs = None
        raw_structured = result.get("structured_recommendations", {})
        if raw_structured:
            structured_recs = {
                "header": raw_structured.get("header", ""),
                "immediate_actions": raw_structured.get("immediate_actions", []),
                "monitoring_required": raw_structured.get("monitoring_required", []),
                "laboratory_tests": raw_structured.get("laboratory_tests", []),
                "patient_alerts": raw_structured.get("patient_alerts", []),
                "alternatives": raw_structured.get("alternatives", []),
                "follow_up": raw_structured.get("follow_up", []),
                "patient_counseling": raw_structured.get("patient_counseling", []),
            }

        risk_level = result.get("risk_level", "unknown")
        if hasattr(risk_level, "value"):
            risk_level = risk_level.value

        return {
            "session_id": session_id,
            "triage_id": triage_id,
            "report_id": report_id,
            "status": result.get("status", "completed"),
            "risk_level": str(risk_level),
            "confidence_score": result.get("confidence_score", 0.0),
            "interactions": result.get("interactions", []),
            "contraindications": result.get("contraindications", []),
            "dosage_adjustments": result.get("dosage_adjustments", []),
            "adverse_reactions": result.get("adverse_reactions", []),
            "evidence_links": result.get("evidence_links", []),
            "structured_recommendations": structured_recs,
            "requires_human_review": result.get("requires_human_review", False),
            "escalation_reasons": result.get("escalation_reasons", []),
            "final_report": result.get("final_report", {}),
            "created_at": datetime.now().isoformat(),
        }

    def format_legacy_response(
        self,
        result: Dict[str, Any],
        patient_info: Dict[str, Any],
        model_used: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Format analysis result for legacy API response.

        Includes additional computed fields for UI compatibility.

        Args:
            result: LangGraph analysis result
            patient_info: Original patient information
            model_used: Model that was used for analysis

        Returns:
            Formatted legacy response dictionary
        """
        lang_settings = get_langgraph_settings()

        # Build enriched response
        recommendations_for_ui = build_recommendations_from_state(result)
        accuracy_score, accuracy_factors = compute_accuracy(result, patient_info)

        # Build analysis notes summary
        current_meds = patient_info.get(
            "current_medications", patient_info.get("meds_in_use", [])
        )
        conditions = patient_info.get("conditions", patient_info.get("cid_codes", []))

        sex_display = patient_info.get("sex") or patient_info.get("gender") or "N/A"
        age_display = patient_info.get("age", "N/A")
        weight_display = patient_info.get("weight", "N/A")
        meds_display = current_meds if isinstance(current_meds, list) else []
        allergies_display = patient_info.get("allergies", [])
        conditions_display = conditions if isinstance(conditions, list) else []

        interactions_list = result.get("interactions", []) or []
        contraindications_list = result.get("contraindications", []) or []
        highlights: list[str] = []

        for it in interactions_list[:2] if isinstance(interactions_list, list) else []:
            if isinstance(it, dict):
                highlights.append(
                    f"Interaction {(normalize_str(it.get('severity')) or '').upper()}: "
                    f"{normalize_str(it.get('drug1'))} + {normalize_str(it.get('drug2'))} — "
                    f"{normalize_str(it.get('description'))[:140]}"
                )

        for ct in (
            contraindications_list[:2]
            if isinstance(contraindications_list, list)
            else []
        ):
            if isinstance(ct, dict):
                highlights.append(
                    f"Contraindication {(normalize_str(ct.get('severity')) or '').upper()}: "
                    f"{normalize_str(ct.get('type'))} — {normalize_str(ct.get('description'))[:140]}"
                )

        analysis_notes = (
            "Analysis summary (based on anamnesis and findings):\n"
            f"- Anamnesis: age={age_display}, sex={sex_display}, weight={weight_display}kg; "
            f"conditions={len(conditions_display)}; meds_in_use={len(meds_display)}; "
            f"allergies={len(allergies_display) if isinstance(allergies_display, list) else 'N/A'}\n"
            f"- Overall risk: {normalize_str(result.get('risk_level'))}\n"
            f"- Findings: interactions={len(interactions_list) if isinstance(interactions_list, list) else 0}, "
            f"contraindications={len(contraindications_list) if isinstance(contraindications_list, list) else 0}\n"
            + (
                ("- Highlights:\n  - " + "\n  - ".join(highlights) + "\n")
                if highlights
                else ""
            )
            + (
                (
                    "- Recommendations (top):\n  - "
                    + "\n  - ".join(recommendations_for_ui[:6])
                    + "\n"
                )
                if recommendations_for_ui
                else ""
            )
            + f"- Estimated accuracy (calibrated): {accuracy_score:.0%}\n"
        ).strip()

        risk_level = result.get("risk_level", "unknown")
        if hasattr(risk_level, "value"):
            risk_level = risk_level.value

        return {
            "session_id": result.get("session_id"),
            "risk_level": str(risk_level),
            "confidence_score": result.get("confidence_score", 0.0),
            "accuracy_score": accuracy_score,
            "accuracy_factors": accuracy_factors,
            "interactions": result.get("interactions", []),
            "contraindications": result.get("contraindications", []),
            "dosage_adjustments": result.get("dosage_adjustments", []),
            "adverse_reactions": result.get("adverse_reactions", []),
            "evidence_links": result.get("evidence_links", []),
            "recommendations": recommendations_for_ui,
            "structured_recommendations": result.get("structured_recommendations", {}),
            "analysis_notes": analysis_notes,
            "final_report": result.get("final_report", {}),
            "status": result.get("status", "completed"),
            "requires_human_review": result.get("requires_human_review", False),
            "escalation_reasons": result.get("escalation_reasons", []),
            "model_used": model_used
            or result.get("model_used", lang_settings.effective_model_name),
        }


# Global orchestrator instance
_orchestrator: Optional[AnalysisOrchestrator] = None


def get_orchestrator() -> AnalysisOrchestrator:
    """
    Get global orchestrator instance (singleton pattern).

    Returns:
        AnalysisOrchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AnalysisOrchestrator()
    return _orchestrator
