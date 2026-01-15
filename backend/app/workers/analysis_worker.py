"""
Durable analysis worker (DB-backed queue).

This worker polls `analysis_jobs` for pending jobs, executes the LangGraph workflow,
and persists the latest workflow state back into the job row.

It is meant to be run as:
  python -m backend.app.workers.analysis_worker
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from ..db.database import get_db_context
from ..db.models import AnalysisJob
from ..services.analysis_orchestrator import get_orchestrator
from ..langgraph_agents import get_settings as get_lang_settings

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _claim_next_job() -> Optional[str]:
    """
    Claim a single pending job atomically using SELECT ... FOR UPDATE SKIP LOCKED.

    This is race-condition safe for multiple workers:
    - FOR UPDATE locks the row exclusively
    - SKIP LOCKED makes other workers skip already-locked rows
    - Status update happens in the same transaction

    Returns:
        job_id as string, or None if none available.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    
    with get_db_context() as db:
        # Use raw SQL for FOR UPDATE SKIP LOCKED (SQLAlchemy ORM support varies)
        # This is PostgreSQL-specific but we're targeting PostgreSQL for production
        result = db.execute(
            text("""
                UPDATE analysis_jobs
                SET status = 'running', started_at = NOW(), updated_at = NOW()
                WHERE id = (
                    SELECT id FROM analysis_jobs
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id
            """)
        )
        
        row = result.fetchone()
        db.commit()
        
        if row:
            job_id = str(row[0])
            logger.debug("Worker claimed job %s atomically", job_id)
            return job_id
        
        return None


def _claim_next_job_sqlite_fallback() -> Optional[str]:
    """
    SQLite fallback for claim (non-atomic, for development only).
    
    SQLite doesn't support FOR UPDATE SKIP LOCKED, so we use the original
    optimistic approach. This is NOT safe for multiple workers.
    """
    with get_db_context() as db:
        job = (
            db.query(AnalysisJob)
            .filter(AnalysisJob.status == "pending")
            .order_by(AnalysisJob.created_at.asc())
            .first()
        )
        if not job:
            return None

        updated = (
            db.query(AnalysisJob)
            .filter(AnalysisJob.id == job.id)
            .filter(AnalysisJob.status == "pending")
            .update({"status": "running", "started_at": _utcnow()})
        )
        db.commit()
        if updated != 1:
            return None
        return str(job.id)


def _load_job(job_id: str) -> Optional[AnalysisJob]:
    with get_db_context() as db:
        return db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()


async def _execute_job(job_id: str) -> None:
    orchestrator = get_orchestrator()
    lang_settings = get_lang_settings()

    job = _load_job(job_id)
    if not job:
        return

    payload = job.payload or {}
    patient_data = payload.get("patient_data") or {}
    medication = payload.get("medication") or ""
    triage_id = payload.get("triage_id")
    model_override = payload.get("model_override")

    # Basic sanity: if we cannot run, mark failed.
    if not medication:
        await orchestrator.update_job(
            job_id=job_id,
            status="failed",
            last_error="Missing medication in job payload",
            finished_at=_utcnow(),
        )
        return

    try:
        logger.info("Worker executing job=%s session=%s", job_id, job.session_id)

        result = await orchestrator.run_analysis(
            patient_data=patient_data,
            medication_text=medication,
            session_id=job.session_id,
            triage_id=triage_id,
            model_override=model_override,
        )

        # Persist report (best-effort)
        report_id = None
        if triage_id:
            report_id = await orchestrator.save_report(triage_id=triage_id, result=result)
            # also write ids into state for /status response
            if isinstance(result, dict):
                result.setdefault("triage_id", triage_id)
                if report_id:
                    result.setdefault("report_id", report_id)

        requires_review = bool(result.get("requires_human_review", False)) if isinstance(result, dict) else False
        if requires_review and lang_settings.enable_hitl:
            status = "awaiting_review"
        else:
            status = "completed"

        await orchestrator.update_job(
            job_id=job_id,
            status=status,
            state=result if isinstance(result, dict) else {"final_report": str(result)},
            finished_at=_utcnow(),
        )

        logger.info("Worker finished job=%s status=%s", job_id, status)

    except Exception as e:
        logger.error("Worker job failed job=%s err=%s", job_id, e, exc_info=True)
        await orchestrator.update_job(
            job_id=job_id,
            status="failed",
            last_error=str(e),
            finished_at=_utcnow(),
            increment_retries=True,
        )


def _get_claim_function():
    """
    Get the appropriate job claim function based on database type.
    
    PostgreSQL: Uses atomic FOR UPDATE SKIP LOCKED
    SQLite: Uses optimistic locking fallback (dev only)
    """
    from ..db.database import is_sqlite
    
    if is_sqlite:
        logger.warning("⚠️ Using SQLite fallback for job claim (NOT safe for multiple workers)")
        return _claim_next_job_sqlite_fallback
    else:
        logger.info("✅ Using atomic PostgreSQL job claim (FOR UPDATE SKIP LOCKED)")
        return _claim_next_job


async def main() -> None:
    poll_interval = float(os.getenv("MEDSAFE_WORKER_POLL_INTERVAL", "1.0"))
    idle_sleep = max(0.2, min(poll_interval, 10.0))
    
    # Get the appropriate claim function for our database
    claim_job = _get_claim_function()

    logger.info("MedSafe analysis worker started (poll_interval=%.2fs)", idle_sleep)

    while True:
        job_id = claim_job()
        if not job_id:
            await asyncio.sleep(idle_sleep)
            continue

        await _execute_job(job_id)


if __name__ == "__main__":
    asyncio.run(main())

