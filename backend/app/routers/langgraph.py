"""
FastAPI Router for MedSafe LangGraph Multi-Agent System v2 - Enhanced

CONSOLIDATED API v2 with:
- Database persistence (Triage, Report models)
- Rate limiting
- JWT authentication
- Complete CRUD operations
- HITL workflows
- Idempotency support

PATTERN: RESTful API for agent orchestration + persistence
SKILLS: @fastapi-templates, @api-design-principles, @ultrathink
"""

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth.jwt import get_current_user, get_optional_current_user
from ..config import settings as app_settings
from ..db.database import get_db_context
from ..db.models import AnalysisJob, HITLReview, Report, Triage
from ..langgraph_agents import get_graph, get_settings
from ..middleware.rate_limit import limiter
from ..services.analysis_orchestrator import get_orchestrator
from ..services.response_formatter import compute_accuracy

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v2", tags=["LangGraph Multi-Agent v2"])


# ============================================================================
# STANDARDIZED ERROR RESPONSES (RFC 7807 Problem Details)
# ============================================================================


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details for HTTP APIs"""

    type: str = Field(
        default="about:blank", description="URI identifying the problem type"
    )
    title: str = Field(..., description="Short, human-readable summary")
    status: int = Field(..., description="HTTP status code")
    detail: Optional[str] = Field(None, description="Human-readable explanation")
    instance: Optional[str] = Field(
        None, description="URI identifying the specific occurrence"
    )

    # Extended fields for MedSafe
    code: Optional[str] = Field(None, description="Machine-readable error code")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")


def create_problem_response(
    status: int,
    title: str,
    detail: Optional[str] = None,
    code: Optional[str] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Create a standardized RFC 7807 problem response."""
    problem = ProblemDetail(
        type=f"https://medsafe.local/problems/{code}" if code else "about:blank",
        title=title,
        status=status,
        detail=detail,
        code=code,
        request_id=request_id,
    )
    return JSONResponse(status_code=status, content=problem.dict(exclude_none=True))


# ============================================================================
# IDEMPOTENCY SUPPORT
# ============================================================================


def _compute_payload_hash(medication: str, patient_data: Dict) -> str:
    """Compute a deterministic hash of the analysis payload for deduplication."""
    # Normalize data for consistent hashing
    normalized = {
        "medication": medication.lower().strip(),
        "age": patient_data.get("age"),
        "weight": patient_data.get("weight"),
        "current_medications": sorted(
            [m.lower() for m in patient_data.get("current_medications", [])]
        ),
        "conditions": sorted([c.lower() for c in patient_data.get("conditions", [])]),
    }
    payload_str = str(sorted(normalized.items()))
    return hashlib.sha256(payload_str.encode()).hexdigest()[:32]


async def _find_existing_job_by_idempotency_key(
    idempotency_key: str,
    user_id: str,
) -> Optional[AnalysisJob]:
    """Find an existing job by idempotency key within a time window.

    NOTE: Only returns jobs that are NOT failed - failed jobs should be retried.
    """
    from datetime import timedelta

    with get_db_context() as db:
        # Look for jobs created in the last hour with the same idempotency key
        # Exclude failed jobs so they can be retried
        cutoff = datetime.utcnow() - timedelta(hours=1)

        jobs = (
            db.query(AnalysisJob)
            .filter(
                AnalysisJob.user_id == user_id,
                AnalysisJob.created_at >= cutoff,
                AnalysisJob.status != "failed",  # Don't return failed jobs for retry
            )
            .all()
        )

        # Filter in Python for JSON field match
        for job in jobs:
            if job.payload and job.payload.get("idempotency_key") == idempotency_key:
                return job

        return None


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class PatientData(BaseModel):
    """
    Patient information for analysis

    EXPANDED SCHEMA (2025-12-03):
    - Added detailed renal/hepatic function parameters
    - Added demographic fields for dose calculation
    - Added lactation status
    """

    # Demographics
    age: Optional[int] = Field(None, ge=0, le=150, description="Patient age in years")
    weight: Optional[float] = Field(
        None, ge=0, le=500, description="Patient weight in kg"
    )
    height: Optional[float] = Field(
        None, ge=0, le=3.0, description="Patient height in meters"
    )
    sex: Optional[str] = Field(None, pattern="^[MF]$", description="Patient sex (M/F)")

    # Pregnancy and lactation
    pregnant: Optional[bool] = Field(False, description="Is patient pregnant")
    lactating: Optional[bool] = Field(False, description="Is patient breastfeeding")

    # Medical history
    conditions: List[str] = Field(
        default_factory=list, description="Medical conditions (CID codes)"
    )
    current_medications: List[str] = Field(
        default_factory=list, description="Current medications"
    )
    allergies: List[str] = Field(default_factory=list, description="Known allergies")

    # Renal function (detailed)
    renal_function: Optional[str] = Field(
        None, description="Renal function status (legacy)"
    )
    creatinine: Optional[float] = Field(
        None, ge=0, le=30, description="Serum creatinine (mg/dL)"
    )
    gfr: Optional[float] = Field(
        None, ge=0, le=200, description="GFR (mL/min/1.73m2) - calculated or measured"
    )
    renal_stage: Optional[str] = Field(
        None,
        pattern="^G[1-5][ab]?$",
        description="CKD stage (G1, G2, G3a, G3b, G4, G5)",
    )

    # Hepatic function (detailed)
    hepatic_function: Optional[str] = Field(
        None, description="Hepatic function status (legacy)"
    )
    alt: Optional[float] = Field(None, ge=0, le=10000, description="ALT/TGP (U/L)")
    ast: Optional[float] = Field(None, ge=0, le=10000, description="AST/TGO (U/L)")
    bilirubin: Optional[float] = Field(
        None, ge=0, le=50, description="Total bilirubin (mg/dL)"
    )
    child_pugh: Optional[str] = Field(
        None, pattern="^[ABC]$", description="Child-Pugh classification (A, B, C)"
    )

    # Additional clinical context
    previous_adverse_reactions: List[str] = Field(
        default_factory=list, description="Previous adverse drug reactions"
    )


class AnalyzeRequest(BaseModel):
    """Request model for drug analysis"""

    medication: str = Field(..., min_length=1, description="Medication name to analyze")
    patient_data: PatientData = Field(..., description="Patient information")
    user_id: Optional[str] = Field(None, description="User ID for tracking")
    notes: Optional[str] = Field(None, description="Additional notes")
    save_to_db: bool = Field(True, description="Save triage and report to database")


class StructuredRecommendations(BaseModel):
    """Structured clinical recommendations by category"""

    header: str = ""
    immediate_actions: List[str] = []
    monitoring_required: List[str] = []
    laboratory_tests: List[str] = []
    patient_alerts: List[str] = []
    alternatives: List[str] = []
    follow_up: List[str] = []
    patient_counseling: List[str] = []


class AnalyzeResponse(BaseModel):
    """
    Response model for analysis results

    ENHANCED (2025-12-03):
    - Added structured_recommendations for actionable clinical guidance
    - Added patient_risk_factors for context-aware analysis
    - Added severity_modified flag to track adjustments

    ENHANCED (2026-01-14):
    - Added accuracy_score (calibrated metric based on confidence + anamnesis + critique)
    """

    session_id: str
    job_id: Optional[str] = None
    triage_id: Optional[str] = None
    report_id: Optional[str] = None
    status: str
    risk_level: Optional[str] = None
    confidence_score: Optional[float] = None
    accuracy_score: Optional[float] = None  # Calibrated accuracy metric for UI

    # Findings
    interactions: List[Dict[str, Any]] = []
    contraindications: List[Dict[str, Any]] = []

    # Recommendations (legacy)
    dosage_adjustments: List[Dict[str, Any]] = []
    adverse_reactions: List[Dict[str, Any]] = []
    evidence_links: List[str] = []

    # NEW: Structured recommendations
    structured_recommendations: Optional[StructuredRecommendations] = None

    # NEW: Patient context impact
    patient_risk_factors: List[str] = []
    severity_modified: bool = False
    original_risk_level: Optional[str] = None

    # HITL escalation
    requires_human_review: bool = False
    escalation_reasons: List[str] = []

    # Full report
    final_report: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    created_at: Optional[datetime] = None


class HITLApprovalRequest(BaseModel):
    """Request model for physician approval/rejection"""

    session_id: str = Field(..., description="Session ID to approve")
    approved: bool = Field(..., description="True for approve, False for reject")
    physician_notes: Optional[str] = Field(None, description="Physician notes/comments")
    modifications: Optional[Dict[str, Any]] = Field(
        None, description="Any modifications to apply"
    )


class TriageListResponse(BaseModel):
    """Response for list of triages"""

    triages: List[Dict[str, Any]]
    total: int
    page: int
    per_page: int


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute
async def analyze_drug_interaction(
    request: Request,
    data: AnalyzeRequest,
    current_user: Optional[str] = Depends(get_optional_current_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> AnalyzeResponse:
    """
    Analyze drug interactions using LangGraph multi-agent system

    **ENHANCED v2**: Now includes database persistence, rate limiting, and idempotency

    **Rate Limit**: 10 requests/minute per user

    **Idempotency**: Send `Idempotency-Key` header to prevent duplicate jobs on retries.
    If the same key is sent within 1 hour, returns the existing job instead of creating a new one.

    **Flow**:
    1. Check idempotency key (if provided)
    2. Create Triage record in database (if save_to_db=True)
    3. Invoke LangGraph workflow asynchronously
    4. Save Report to database when complete
    5. Return session_id and status
    """
    try:
        # Anonymous access is supported only when explicitly enabled (or in debug).
        # This keeps the v2 contract usable for the static frontend demos without forcing auth.
        if (
            not current_user
            and (not app_settings.debug)
            and (not getattr(app_settings, "allow_anonymous_analysis", False))
        ):
            raise HTTPException(status_code=401, detail="Authentication required")

        effective_user = (data.user_id or current_user or "anonymous").strip()

        # IDEMPOTENCY: Check if job already exists
        actual_idempotency_key = idempotency_key
        if not actual_idempotency_key:
            # Auto-generate idempotency key from payload hash (optional deduplication)
            actual_idempotency_key = _compute_payload_hash(
                data.medication, data.patient_data.dict()
            )

        # Try to find existing job with same idempotency key
        existing_job = await _find_existing_job_by_idempotency_key(
            actual_idempotency_key, effective_user
        )
        if existing_job:
            logger.info(
                "Returning existing job due to idempotency (job_id=%s)", existing_job.id
            )
            return AnalyzeResponse(
                session_id=existing_job.session_id,
                job_id=str(existing_job.id),
                triage_id=(
                    str(existing_job.triage_id) if existing_job.triage_id else None
                ),
                status=existing_job.status,
                message="Existing analysis found (idempotent). Check /api/v2/status/{session_id} for results.",
                created_at=existing_job.created_at,
            )

        # LGPD: avoid logging raw medication/patient details; keep session correlation
        logger.info("New analysis request (user=%s)", effective_user)

        orchestrator = get_orchestrator()
        session_id = str(uuid.uuid4())

        # Create Triage in database using orchestrator
        triage_id = await orchestrator.create_triage(
            patient_data=data.patient_data.dict(),
            medication=data.medication,
            user_id=effective_user if effective_user != "anonymous" else "anonymous",
            notes=data.notes,
            save_to_db=data.save_to_db,
        )

        # Create durable job for worker execution (include idempotency key in payload)
        job_id = await orchestrator.create_analysis_job(
            session_id=session_id,
            triage_id=triage_id,
            user_id=effective_user,
            medication=data.medication,
            patient_data=data.patient_data.dict(),
            notes=data.notes,
            idempotency_key=actual_idempotency_key,
        )

        # Return immediate response
        return AnalyzeResponse(
            session_id=session_id,
            job_id=job_id,
            triage_id=triage_id,
            status="pending",
            message="Analysis started. Check /api/v2/status/{session_id} for results.",
            created_at=datetime.now(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to start analysis: {str(e)}"
        )


@router.get("/status/{session_id}", response_model=AnalyzeResponse)
@limiter.limit("30/minute")  # Rate limit: 30 status checks per minute
async def get_analysis_status(
    request: Request,
    session_id: str,
    current_user: Optional[str] = Depends(get_optional_current_user),
) -> AnalyzeResponse:
    """
    Get current status of analysis

    **PATTERN**: Stateful checkpoint retrieval
    **Rate Limit**: 30 requests/minute per user

    Returns analysis results if completed, or current status if still running
    """
    try:
        logger.info(f"Status check for session: {session_id}")

        orchestrator = get_orchestrator()
        job = await orchestrator.get_job_by_session(session_id)
        if not job:
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

        # Authorization (if triage exists)
        if job.triage_id:
            with get_db_context() as db:
                triage = db.query(Triage).filter(Triage.id == job.triage_id).first()
                effective_user = current_user or "anonymous"
                if triage and triage.user_id and triage.user_id != effective_user:
                    raise HTTPException(status_code=403, detail="Access denied")

        result = job.state or {}

        # Build structured recommendations if available
        structured_recs = None
        raw_structured = result.get("structured_recommendations", {})
        if raw_structured:
            structured_recs = StructuredRecommendations(
                header=raw_structured.get("header", ""),
                immediate_actions=raw_structured.get("immediate_actions", []),
                monitoring_required=raw_structured.get("monitoring_required", []),
                laboratory_tests=raw_structured.get("laboratory_tests", []),
                patient_alerts=raw_structured.get("patient_alerts", []),
                alternatives=raw_structured.get("alternatives", []),
                follow_up=raw_structured.get("follow_up", []),
                patient_counseling=raw_structured.get("patient_counseling", []),
            )

        # Compute calibrated accuracy_score (2026-01-14)
        # Uses confidence_score + anamnesis completeness + critique level + refinements
        patient_info = (
            result.get("patient_data") or job.payload.get("patient_data", {})
            if job.payload
            else {}
        )
        raw_confidence = result.get("confidence_score", 0.0) or 0.0

        # Only compute accuracy if we have confidence data
        if (
            raw_confidence > 0
            or result.get("interactions")
            or result.get("contraindications")
        ):
            accuracy_score, _ = compute_accuracy(result, patient_info)
        else:
            accuracy_score = raw_confidence

        # Build response with new fields
        response = AnalyzeResponse(
            session_id=session_id,
            job_id=str(job.id),
            triage_id=result.get("triage_id"),
            status=str(job.status or result.get("status", "unknown")),
            risk_level=str(result.get("risk_level", "unknown")),
            confidence_score=raw_confidence,
            accuracy_score=accuracy_score,  # Calibrated metric for UI
            # Findings
            interactions=result.get("interactions", []),
            contraindications=result.get("contraindications", []),
            # Recommendations
            dosage_adjustments=result.get("dosage_adjustments", []),
            adverse_reactions=result.get("adverse_reactions", []),
            evidence_links=result.get("evidence_links", []),
            # NEW: Structured recommendations
            structured_recommendations=structured_recs,
            # HITL
            requires_human_review=result.get("requires_human_review", False),
            escalation_reasons=result.get("escalation_reasons", []),
            final_report=result.get("final_report", {}),
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.post("/hitl/approve", response_model=AnalyzeResponse)
@limiter.limit("20/minute")
async def approve_analysis(
    request: Request,
    data: HITLApprovalRequest,
    current_user: str = Depends(get_current_user),
) -> AnalyzeResponse:
    """
    Physician approves or rejects analysis (HITL continuation)

    **PATTERN**: Interrupt resume
    **Rate Limit**: 20 requests/minute per user

    Flow:
    1. Load checkpointed state
    2. Add human feedback to state
    3. Resume graph execution from HITL node
    4. Return final results
    """
    try:
        if not get_settings().enable_hitl:
            raise HTTPException(status_code=410, detail="HITL is disabled")

        logger.info(f"HITL decision from {current_user} for session: {data.session_id}")
        logger.info(f"   Decision: {'APPROVED' if data.approved else 'REJECTED'}")

        orchestrator = get_orchestrator()
        job = await orchestrator.get_job_by_session(data.session_id)
        if not job:
            raise HTTPException(
                status_code=404, detail=f"Session {data.session_id} not found"
            )

        state_values = job.state or {}
        if (
            str(job.status) != "awaiting_review"
            and state_values.get("status") != "awaiting_human_review"
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Session {data.session_id} is not awaiting human review",
            )

        # Prepare human feedback
        human_feedback = {
            "approved": data.approved,
            "notes": data.physician_notes or "",
            "modifications": data.modifications or {},
            "timestamp": datetime.now().isoformat(),
            "reviewer_id": current_user,
        }

        # Update state with human feedback
        updated_state = {
            **state_values,
            "human_feedback": human_feedback,
        }

        # Resume graph execution
        graph = get_graph()
        config = {"configurable": {"thread_id": data.session_id}}
        result = await graph.ainvoke(updated_state, config)

        # Update Report in database if exists
        triage_id = result.get("triage_id")
        if triage_id:
            with get_db_context() as db:
                db_triage = db.query(Triage).filter(Triage.id == triage_id).first()
                if db_triage:
                    db_triage.status = "completed" if data.approved else "rejected"

                    # Update or create report
                    report = (
                        db.query(Report).filter(Report.triage_id == triage_id).first()
                    )
                    if report:
                        report.is_final = True
                        report.confidence_score = result.get("confidence_score", 0.0)
                        report.status = "final" if data.approved else "rejected"

                    # Persist HITL decision (audit)
                    review = HITLReview(
                        session_id=data.session_id,
                        job_id=job.id,
                        triage_id=triage_id,
                        reviewer_id=current_user,
                        approved=bool(data.approved),
                        physician_notes=data.physician_notes,
                        modifications=data.modifications or {},
                    )
                    db.add(review)
                    db.commit()

        # Persist job state and mark terminal state
        await orchestrator.update_job(
            job_id=str(job.id),
            status="completed" if data.approved else "rejected",
            state=result,
            finished_at=datetime.utcnow(),
        )

        # Build response
        response = AnalyzeResponse(
            session_id=data.session_id,
            job_id=str(job.id),
            triage_id=triage_id,
            status="completed" if data.approved else "rejected",
            risk_level=str(result.get("risk_level", "unknown")),
            confidence_score=result.get("confidence_score", 0.0),
            interactions=result.get("interactions", []),
            contraindications=result.get("contraindications", []),
            dosage_adjustments=result.get("dosage_adjustments", []),
            adverse_reactions=result.get("adverse_reactions", []),
            evidence_links=result.get("evidence_links", []),
            final_report=result.get("final_report", {}),
            message=f"Analysis {'approved' if data.approved else 'rejected'} by physician {current_user}.",
        )

        logger.info(f"   HITL completed: {response.status}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HITL approval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"HITL approval failed: {str(e)}")


@router.get("/triages", response_model=TriageListResponse)
@limiter.limit("30/minute")
async def list_triages(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    current_user: str = Depends(get_current_user),
) -> TriageListResponse:
    """
    List triages for current user

    **Rate Limit**: 30 requests/minute

    Supports pagination and filtering by status
    """
    try:
        with get_db_context() as db:
            query = db.query(Triage).filter(Triage.user_id == current_user)

            if status:
                query = query.filter(Triage.status == status)

            total = query.count()

            triages = (
                query.order_by(Triage.created_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )

            triages_data = [
                {
                    "id": str(t.id),
                    "status": t.status,
                    "age": t.age,
                    "weight": t.weight,
                    "meds_in_use": t.meds_in_use,
                    "created_at": t.created_at.isoformat(),
                }
                for t in triages
            ]

            return TriageListResponse(
                triages=triages_data,
                total=total,
                page=page,
                per_page=per_page,
            )

    except Exception as e:
        logger.error(f"Failed to list triages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list triages: {str(e)}")


@router.get("/triages/{triage_id}/report")
@limiter.limit("30/minute")
async def get_triage_report(
    request: Request, triage_id: str, current_user: str = Depends(get_current_user)
):
    """
    Get report for a specific triage

    **Rate Limit**: 30 requests/minute
    """
    try:
        with get_db_context() as db:
            triage = db.query(Triage).filter(Triage.id == triage_id).first()

            if not triage:
                raise HTTPException(status_code=404, detail="Triage not found")

            if triage.user_id != current_user:
                raise HTTPException(status_code=403, detail="Access denied")

            report = db.query(Report).filter(Report.triage_id == triage_id).first()

            if not report:
                raise HTTPException(status_code=404, detail="Report not found")

            return {
                "triage_id": str(report.triage_id),
                "risk_level": report.risk_level,
                "contraindications": report.contraindications,
                "interactions": report.interactions,
                "dosage_adjustments": report.dosage_adjustments,
                "adverse_reactions": report.adverse_reactions,
                "evidence_links": report.evidence_links,
                "confidence_score": report.confidence_score,
                "is_final": report.is_final,
                "created_at": report.created_at.isoformat(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get report: {str(e)}")


@router.get("/health")
async def health_check():
    """
    Health check endpoint for v2 API

    Returns LangGraph system status and configuration
    """
    try:
        lg_settings = get_settings()

        return {
            "status": "healthy",
            "version": "2.0.0-langgraph-enhanced",
            "features": {
                "database_persistence": True,
                "rate_limiting": True,
                "jwt_authentication": True,
                "hitl_workflow": bool(lg_settings.enable_hitl),
            },
            "model": lg_settings.effective_model_name,
            "ollama_url": lg_settings.effective_ollama_url,
            "hitl_enabled": lg_settings.enable_hitl,
            "safety_guardrails": lg_settings.enable_safety_guardrails,
            "max_reflection_cycles": lg_settings.max_reflection_cycles,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}
