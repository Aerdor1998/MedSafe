"""
Durable analysis worker (DB-backed queue).

This worker polls `analysis_jobs` for pending jobs, executes the LangGraph workflow,
and persists the latest workflow state back into the job row.

It is meant to be run as:
  python -m backend.app.workers.analysis_worker
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from ..db.database import get_db_context
from ..db.models import AnalysisJob
from ..langgraph_agents import get_settings as get_lang_settings
from ..services.analysis_orchestrator import get_orchestrator

logger = logging.getLogger(__name__)

# Limiar para considerar um job 'running' como órfão (worker morto mid-job).
# 600s = 2x o ollama_timeout (300s em langgraph_agents/config.py); a eval
# clínica mede média ~106s e máx ~178s por caso, então nenhum job legítimo
# chega perto disso.
DEFAULT_STALE_JOB_SECONDS = 600.0

# Tempo máximo de drain no shutdown: quanto esperamos o job em andamento
# terminar após SIGTERM/SIGINT antes de cancelá-lo e devolvê-lo à fila.
# 300s = ollama_timeout (nenhum job legítimo passa disso); cabe com folga
# no stop_grace_period de 360s do worker em docker-compose.prod.yml.
DEFAULT_DRAIN_TIMEOUT_SECONDS = 300.0


def _utcnow() -> datetime:
    return datetime.utcnow()


def _as_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normaliza datetimes aware (PG, timezone=True) ou naive para UTC naive."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


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

    with get_db_context() as db:
        # Use raw SQL for FOR UPDATE SKIP LOCKED (SQLAlchemy ORM support varies)
        # This is PostgreSQL-specific but we're targeting PostgreSQL for production
        result = db.execute(
            text(
                """
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
            """
            )
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
            report_id = await orchestrator.save_report(
                triage_id=triage_id, result=result
            )
            # also write ids into state for /status response
            if isinstance(result, dict):
                result.setdefault("triage_id", triage_id)
                if report_id:
                    result.setdefault("report_id", report_id)

        requires_review = (
            bool(result.get("requires_human_review", False))
            if isinstance(result, dict)
            else False
        )
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


def _requeue_or_fail(job: AnalysisJob, reason: str) -> str:
    """
    Devolve um job 'running' abandonado para um estado recuperável.

    Usa a MESMA contabilidade de retries de `_execute_job` (colunas
    retries/max_retries incrementadas via update_job): se o job já esgotou as
    tentativas, marca 'failed' em vez de reenfileirar para sempre.

    Returns:
        O novo status atribuído ('pending' ou 'failed').
    """
    retries = int(job.retries or 0)
    max_retries = int(job.max_retries or 3)
    job.last_error = reason

    if retries >= max_retries:
        job.status = "failed"
        job.finished_at = _utcnow()
        return "failed"

    job.status = "pending"
    job.retries = retries + 1
    job.started_at = None
    job.finished_at = None
    return "pending"


def _recover_stale_jobs(stale_seconds: Optional[float] = None) -> int:
    """
    Reenfileira no boot os jobs presos em 'running' além do limiar.

    Um job fica preso quando o worker morre mid-job (deploy, SIGKILL, OOM):
    sem isso, a análise clínica fica em 'running' para sempre e ninguém é
    avisado. O filtro roda em Python sobre os jobs 'running' (poucos por
    definição), usando o timestamp mais recente disponível (updated_at >
    started_at > created_at); jobs sem timestamp algum são tratados como
    órfãos. Jobs dentro do limiar são deixados em paz — podem estar vivos em
    um worker irmão.

    Returns:
        Quantidade de jobs recuperados (reenfileirados ou marcados 'failed').
    """
    if stale_seconds is None:
        stale_seconds = float(
            os.getenv(
                "MEDSAFE_WORKER_STALE_JOB_SECONDS", str(DEFAULT_STALE_JOB_SECONDS)
            )
        )
    cutoff = _utcnow() - timedelta(seconds=stale_seconds)
    recovered = 0

    with get_db_context() as db:
        running_jobs = (
            db.query(AnalysisJob).filter(AnalysisJob.status == "running").all()
        )
        for job in running_jobs:
            last_touch = _as_naive_utc(
                job.updated_at or job.started_at or job.created_at
            )
            if last_touch is not None and last_touch >= cutoff:
                continue  # recente demais — pode estar vivo em outro worker

            new_status = _requeue_or_fail(
                job,
                f"Job preso em 'running' por mais de {stale_seconds:.0f}s "
                "(provável restart do worker); recuperado no boot",
            )
            logger.warning(
                "Job %s órfão em 'running' recuperado no boot: novo status=%s "
                "(retries=%s/%s)",
                job.id,
                new_status,
                job.retries,
                job.max_retries,
            )
            recovered += 1

        if recovered:
            db.commit()

    return recovered


def _release_job(job_id: str, reason: str) -> None:
    """
    Libera um job que não terminou dentro do prazo de drain no shutdown.

    Só age se o job ainda estiver 'running' — guarda contra a corrida em que
    o job termina (ou falha e grava status) entre o timeout e o cancelamento.
    """
    with get_db_context() as db:
        job = (
            db.query(AnalysisJob)
            .filter(AnalysisJob.id == job_id)
            .filter(AnalysisJob.status == "running")
            .first()
        )
        if not job:
            return
        new_status = _requeue_or_fail(job, reason)
        db.commit()
        logger.warning(
            "Job %s liberado no shutdown: novo status=%s", job_id, new_status
        )


def _request_shutdown(shutdown_event: asyncio.Event, signame: str) -> None:
    """Marca o pedido de shutdown — o loop drena o job atual e encerra."""
    logger.info(
        "Sinal %s recebido — worker vai drenar o job em andamento e encerrar",
        signame,
    )
    shutdown_event.set()


def _install_signal_handlers(
    loop: asyncio.AbstractEventLoop, shutdown_event: asyncio.Event
) -> None:
    """Instala handlers de SIGTERM/SIGINT para shutdown gracioso (drain)."""
    # Deploy alvo é Linux/Docker, onde add_signal_handler é suportado.
    # Sem fallback para plataformas sem suporte (ex.: Windows dev):
    # falhar alto é melhor do que um worker sem shutdown gracioso.
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _request_shutdown, shutdown_event, sig.name)


async def _run_loop(
    claim_job: Callable[[], Optional[str]],
    shutdown_event: asyncio.Event,
    idle_sleep: float,
    drain_timeout: float,
) -> None:
    """
    Loop principal do worker com drain gracioso.

    Enquanto o shutdown não for solicitado, reivindica e executa jobs. Quando
    SIGTERM/SIGINT chega no meio de um job, espera até `drain_timeout`s pelo
    término; se estourar, cancela a execução e devolve o job para 'pending'
    (ou 'failed', se esgotou retries) em vez de abandoná-lo em 'running'.
    """
    while not shutdown_event.is_set():
        job_id = claim_job()
        if not job_id:
            # Sleep interrompível: acorda imediatamente se o shutdown chegar
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=idle_sleep)
            except asyncio.TimeoutError:
                pass
            continue

        job_task = asyncio.create_task(_execute_job(job_id))
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        try:
            done, _ = await asyncio.wait(
                {job_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED
            )

            if job_task in done:
                job_task.result()  # propaga exceções fora do try de _execute_job
                continue

            # Shutdown chegou com job em andamento: drenar
            logger.info(
                "Shutdown solicitado com job %s em andamento — aguardando até %.0fs",
                job_id,
                drain_timeout,
            )
            try:
                await asyncio.wait_for(job_task, timeout=drain_timeout)
                logger.info("Job %s terminou dentro do prazo de drain", job_id)
            except asyncio.TimeoutError:
                logger.warning(
                    "Job %s não terminou em %.0fs — cancelando e devolvendo à fila",
                    job_id,
                    drain_timeout,
                )
                job_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                    await asyncio.wait_for(job_task, timeout=5.0)
                _release_job(
                    job_id,
                    f"Job cancelado no shutdown após exceder o drain de "
                    f"{drain_timeout:.0f}s",
                )
        finally:
            if not shutdown_task.done():
                shutdown_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await shutdown_task

    logger.info("Worker encerrado de forma limpa (drain concluído)")


def _get_claim_function():
    """
    Get the appropriate job claim function based on database type.

    PostgreSQL: Uses atomic FOR UPDATE SKIP LOCKED
    SQLite: Uses optimistic locking fallback (dev only)
    """
    from ..db.database import is_sqlite

    if is_sqlite:
        logger.warning(
            "⚠️ Using SQLite fallback for job claim (NOT safe for multiple workers)"
        )
        return _claim_next_job_sqlite_fallback
    else:
        logger.info("✅ Using atomic PostgreSQL job claim (FOR UPDATE SKIP LOCKED)")
        return _claim_next_job


async def main() -> None:
    from ..config import settings
    from ..utils.error_tracking import setup_error_tracking

    setup_error_tracking(settings)

    poll_interval = float(os.getenv("MEDSAFE_WORKER_POLL_INTERVAL", "1.0"))
    idle_sleep = max(0.2, min(poll_interval, 10.0))
    drain_timeout = float(
        os.getenv("MEDSAFE_WORKER_DRAIN_TIMEOUT", str(DEFAULT_DRAIN_TIMEOUT_SECONDS))
    )

    # Shutdown gracioso: SIGTERM/SIGINT drenam o job atual antes de encerrar
    shutdown_event = asyncio.Event()
    _install_signal_handlers(asyncio.get_running_loop(), shutdown_event)

    # Recupera jobs órfãos de restarts anteriores antes de consumir a fila
    recovered = _recover_stale_jobs()
    if recovered:
        logger.warning(
            "Recuperados %d job(s) órfão(s) presos em 'running' no boot", recovered
        )

    # Get the appropriate claim function for our database
    claim_job = _get_claim_function()

    logger.info(
        "MedSafe analysis worker started (poll_interval=%.2fs, drain_timeout=%.0fs)",
        idle_sleep,
        drain_timeout,
    )

    await _run_loop(claim_job, shutdown_event, idle_sleep, drain_timeout)


if __name__ == "__main__":
    asyncio.run(main())
