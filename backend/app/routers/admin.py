"""
Admin Router (minimal)

Provides operational endpoints for:
- listing analysis jobs
- listing HITL queue
- listing HITL review audit log

This is intended for internal/admin use on a single VM deployment.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.rbac import require_admin
from ..db.database import get_db_context
from ..db.models import AnalysisJob, HITLReview

router = APIRouter(prefix="/api/v2/admin", tags=["admin"])


@router.get("/jobs")
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=200),
    status: Optional[str] = Query(None),
    current_user: str = Depends(require_admin),
) -> Dict[str, Any]:
    with get_db_context() as db:
        q = db.query(AnalysisJob)
        if status:
            q = q.filter(AnalysisJob.status == status)
        total = q.count()
        jobs = (
            q.order_by(AnalysisJob.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "jobs": [
                {
                    "id": str(j.id),
                    "session_id": j.session_id,
                    "triage_id": str(j.triage_id) if j.triage_id else None,
                    "user_id": j.user_id,
                    "status": j.status,
                    "retries": j.retries,
                    "max_retries": j.max_retries,
                    "created_at": j.created_at.isoformat() if j.created_at else None,
                    "started_at": j.started_at.isoformat() if j.started_at else None,
                    "finished_at": j.finished_at.isoformat() if j.finished_at else None,
                    "last_error": j.last_error,
                }
                for j in jobs
            ],
        }


@router.get("/hitl/queue")
async def hitl_queue(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=200),
    current_user: str = Depends(require_admin),
) -> Dict[str, Any]:
    with get_db_context() as db:
        q = db.query(AnalysisJob).filter(AnalysisJob.status == "awaiting_review")
        total = q.count()
        jobs = (
            q.order_by(AnalysisJob.created_at.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "jobs": [
                {
                    "id": str(j.id),
                    "session_id": j.session_id,
                    "triage_id": str(j.triage_id) if j.triage_id else None,
                    "user_id": j.user_id,
                    "created_at": j.created_at.isoformat() if j.created_at else None,
                }
                for j in jobs
            ],
        }


@router.get("/hitl/reviews")
async def list_hitl_reviews(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user: str = Depends(require_admin),
) -> Dict[str, Any]:
    with get_db_context() as db:
        q = db.query(HITLReview)
        total = q.count()
        rows = (
            q.order_by(HITLReview.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "reviews": [
                {
                    "id": str(r.id),
                    "session_id": r.session_id,
                    "job_id": str(r.job_id) if r.job_id else None,
                    "triage_id": str(r.triage_id) if r.triage_id else None,
                    "reviewer_id": r.reviewer_id,
                    "approved": r.approved,
                    "physician_notes": r.physician_notes,
                    "modifications": r.modifications,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }
