"""
DEPRECATED: Legacy v1 Human Review Endpoints

This module is DEPRECATED and NOT REGISTERED in main.py.
It references a non-existent module (agents.human_in_the_loop).

MIGRATION:
- Use the v2 HITL endpoints in /api/v2/hitl/approve instead
- See backend/app/routers/langgraph.py for the new HITL implementation

This file is kept for reference only and should be removed in a future cleanup.
"""

import warnings

warnings.warn(
    "human_review.py is deprecated. Use /api/v2/hitl/approve endpoints instead.",
    DeprecationWarning,
    stacklevel=2,
)

from datetime import datetime

# Placeholder enums for backwards compatibility
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

# DEPRECATED: These imports will fail - module no longer exists
# from ..agents.human_in_the_loop import get_hitl_agent, HumanReviewRequest, ReviewStatus, ReviewPriority
from ..auth.jwt import get_current_user


class ReviewStatus(str, Enum):
    """Deprecated - use HITL status in langgraph router instead."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewPriority(str, Enum):
    """Deprecated - priorities are now determined by SafetyAgent."""

    EMERGENCY = "emergency"
    URGENT = "urgent"
    ROUTINE = "routine"


# NOTE: This router is NOT registered in main.py
router = APIRouter(prefix="/api/v1/reviews", tags=["Human Reviews (DEPRECATED)"])


# === Schemas Pydantic ===


class ReviewListResponse(BaseModel):
    """Resposta de lista de revisões"""

    reviews: List[Dict[str, Any]]
    total: int
    pending: int
    overdue: int


class SubmitReviewRequest(BaseModel):
    """Request para submeter revisão"""

    reviewer_id: str = Field(..., description="ID do revisor")
    decision: ReviewStatus = Field(..., description="Decisão da revisão")
    notes: str = Field(..., description="Notas do revisor")
    modified_analysis: Optional[Dict[str, Any]] = Field(
        None, description="Análise modificada"
    )
    feedback: Optional[Dict[str, Any]] = Field(
        None, description="Feedback para o sistema"
    )


class ReviewDetailResponse(BaseModel):
    """Resposta detalhada de uma revisão"""

    review: Dict[str, Any]
    triage_summary: Dict[str, Any]
    analysis_summary: Dict[str, Any]


# === Endpoints ===


@router.get("/pending", response_model=ReviewListResponse)
async def get_pending_reviews(
    priority: Optional[ReviewPriority] = Query(
        None, description="Filtrar por prioridade"
    ),
    overdue_only: bool = Query(False, description="Apenas revisões atrasadas"),
    current_user: str = Depends(get_current_user),
):
    """
    Obter lista de revisões pendentes

    - **priority**: Filtrar por prioridade (EMERGENCY, URGENT, ROUTINE)
    - **overdue_only**: Mostrar apenas revisões atrasadas
    """
    hitl_agent = get_hitl_agent()

    reviews = await hitl_agent.get_pending_reviews(
        priority=priority, overdue_only=overdue_only
    )

    # Calcular estatísticas
    total = len(reviews)
    pending = len([r for r in reviews if r.status == ReviewStatus.PENDING])

    # Contar overdue
    now = datetime.now()
    overdue = len([r for r in reviews if datetime.fromisoformat(r.deadline) < now])

    # Serializar reviews
    reviews_data = [_serialize_review_request(r) for r in reviews]

    return ReviewListResponse(
        reviews=reviews_data, total=total, pending=pending, overdue=overdue
    )


@router.get("/{review_id}", response_model=ReviewDetailResponse)
async def get_review_details(
    review_id: str, current_user: str = Depends(get_current_user)
):
    """
    Obter detalhes completos de uma revisão

    - **review_id**: ID da revisão
    """
    hitl_agent = get_hitl_agent()

    if review_id not in hitl_agent.pending_reviews:
        raise HTTPException(status_code=404, detail="Revisão não encontrada")

    review = hitl_agent.pending_reviews[review_id]

    # Preparar resumos
    triage_summary = {
        "age": review.triage_data.get("age"),
        "pregnant": review.triage_data.get("pregnant", False),
        "conditions": review.triage_data.get("cid_codes", []),
        "current_medications": review.triage_data.get("meds_in_use", []),
        "allergies": review.triage_data.get("allergies", []),
    }

    analysis_summary = {
        "risk_level": review.analysis.get("risk_level"),
        "confidence_score": review.analysis.get("confidence_score"),
        "contraindications_count": len(review.analysis.get("contraindications", [])),
        "interactions_count": len(review.analysis.get("interactions", [])),
        "hallucination_risk": review.analysis.get("hallucination_risk", 0.0),
        "safety_classification": review.analysis.get("safety_classification"),
    }

    return ReviewDetailResponse(
        review=_serialize_review_request(review),
        triage_summary=triage_summary,
        analysis_summary=analysis_summary,
    )


@router.post("/{review_id}/submit")
async def submit_review(
    review_id: str,
    review_data: SubmitReviewRequest,
    current_user: str = Depends(get_current_user),
):
    """
    Submeter revisão humana de uma análise

    Permite que um profissional de saúde revise e aprove/rejeite/modifique uma análise.

    - **review_id**: ID da revisão
    - **reviewer_id**: ID do profissional que está revisando
    - **decision**: APPROVED, REJECTED, ou MODIFIED
    - **notes**: Notas explicando a decisão
    - **modified_analysis**: (Opcional) Análise corrigida, se decision = MODIFIED
    - **feedback**: (Opcional) Feedback para melhorar o sistema
    """
    hitl_agent = get_hitl_agent()

    try:
        updated_review = await hitl_agent.submit_review(
            review_id=review_id,
            reviewer_id=review_data.reviewer_id,
            decision=review_data.decision,
            notes=review_data.notes,
            modified_analysis=review_data.modified_analysis,
            feedback=review_data.feedback,
        )

        return {
            "success": True,
            "review_id": review_id,
            "status": updated_review.status,
            "message": f"Revisão {review_data.decision} submetida com sucesso",
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao submeter revisão: {str(e)}"
        )


@router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: str = Depends(get_current_user)):
    """
    Obter estatísticas do dashboard de revisões

    Retorna métricas agregadas sobre revisões pendentes, concluídas, etc.
    """
    hitl_agent = get_hitl_agent()

    # Obter todas as revisões
    all_reviews = list(hitl_agent.pending_reviews.values())

    now = datetime.now()

    # Calcular estatísticas
    stats = {
        "total_reviews": len(all_reviews),
        "by_status": {
            "pending": len(
                [r for r in all_reviews if r.status == ReviewStatus.PENDING]
            ),
            "in_review": len(
                [r for r in all_reviews if r.status == ReviewStatus.IN_REVIEW]
            ),
            "approved": len(
                [r for r in all_reviews if r.status == ReviewStatus.APPROVED]
            ),
            "rejected": len(
                [r for r in all_reviews if r.status == ReviewStatus.REJECTED]
            ),
            "modified": len(
                [r for r in all_reviews if r.status == ReviewStatus.MODIFIED]
            ),
        },
        "by_priority": {
            "emergency": len(
                [r for r in all_reviews if r.priority == ReviewPriority.EMERGENCY]
            ),
            "urgent": len(
                [r for r in all_reviews if r.priority == ReviewPriority.URGENT]
            ),
            "routine": len(
                [r for r in all_reviews if r.priority == ReviewPriority.ROUTINE]
            ),
        },
        "overdue_count": len(
            [
                r
                for r in all_reviews
                if datetime.fromisoformat(r.deadline) < now
                and r.status in [ReviewStatus.PENDING, ReviewStatus.IN_REVIEW]
            ]
        ),
        "avg_confidence_score": _calculate_avg_confidence(all_reviews),
        "escalation_reasons_breakdown": _calculate_escalation_breakdown(all_reviews),
    }

    return stats


@router.post("/{review_id}/escalate")
async def escalate_review(
    review_id: str,
    escalation_notes: str = Query(..., description="Notas sobre a escalação"),
    current_user: str = Depends(get_current_user),
):
    """
    Escalar revisão para nível superior (ex: de médico generalista para especialista)

    - **review_id**: ID da revisão
    - **escalation_notes**: Motivo da escalação
    """
    hitl_agent = get_hitl_agent()

    if review_id not in hitl_agent.pending_reviews:
        raise HTTPException(status_code=404, detail="Revisão não encontrada")

    review = hitl_agent.pending_reviews[review_id]

    # Atualizar status
    review.status = ReviewStatus.ESCALATED_FURTHER
    review.review_notes = f"ESCALADO: {escalation_notes}"

    # Aumentar prioridade se não for já EMERGENCY
    if review.priority != ReviewPriority.EMERGENCY:
        original_priority = review.priority
        review.priority = (
            ReviewPriority.URGENT
            if review.priority == ReviewPriority.ROUTINE
            else ReviewPriority.EMERGENCY
        )

    # Notificar especialistas
    await hitl_agent._notify_reviewers(review)

    return {
        "success": True,
        "review_id": review_id,
        "new_priority": review.priority,
        "message": "Revisão escalada para nível superior",
    }


# === Helper Functions ===


def _serialize_review_request(review: HumanReviewRequest) -> Dict[str, Any]:
    """Serializar HumanReviewRequest para dict"""
    return {
        "id": review.id,
        "session_id": review.session_id,
        "triage_id": review.triage_id,
        "report_id": review.report_id,
        "risk_level": review.risk_level,
        "confidence_score": review.confidence_score,
        "escalation_reasons": review.escalation_reasons,
        "priority": review.priority,
        "status": review.status,
        "requested_at": review.requested_at,
        "deadline": review.deadline,
        "reviewer_id": review.reviewer_id,
        "reviewed_at": review.reviewed_at,
        "review_decision": review.review_decision,
    }


def _calculate_avg_confidence(reviews: List[HumanReviewRequest]) -> float:
    """Calcular confidence score médio"""
    if not reviews:
        return 0.0

    total = sum(r.confidence_score for r in reviews)
    return total / len(reviews)


def _calculate_escalation_breakdown(
    reviews: List[HumanReviewRequest],
) -> Dict[str, int]:
    """Calcular breakdown de razões de escalação"""
    from collections import Counter

    all_reasons = []
    for review in reviews:
        all_reasons.extend(review.escalation_reasons)

    return dict(Counter(all_reasons))
