"""
Unit tests for the analysis worker's graceful shutdown and stale-job recovery.

Cobre o drain em SIGTERM/SIGINT (o loop termina o job em andamento e encerra
sem reivindicar novos jobs), a recuperação no boot de jobs presos em
'running' (worker morto mid-job em deploys) e o respeito à contabilidade de
retries existente (colunas retries/max_retries): jobs que esgotaram as
tentativas vão para 'failed' em vez de serem reenfileirados para sempre.
Tudo com DB mockado — nenhum serviço externo é necessário.
"""

import asyncio
import os
import signal
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.app.workers import analysis_worker


def _make_job(**overrides) -> SimpleNamespace:
    defaults = dict(
        id="job-1",
        status="running",
        retries=0,
        max_retries=3,
        last_error=None,
        started_at=None,
        finished_at=None,
        created_at=None,
        updated_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _patch_db(db):
    """Substitui get_db_context por um context manager que devolve `db`."""
    ctx = MagicMock()
    ctx.__enter__.return_value = db
    ctx.__exit__.return_value = False
    return patch.object(analysis_worker, "get_db_context", return_value=ctx)


class TestRecuperacaoDeJobsOrfaos:
    """Tests for _recover_stale_jobs (requeue no boot de jobs presos)."""

    def _db_with_running_jobs(self, jobs):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = jobs
        return db

    def test_job_running_alem_do_limiar_e_reenfileirado(self):
        """
        Um job 'running' cujo último toque (updated_at, tz-aware como o PG
        devolve) passou do limiar deve voltar para 'pending' com retry
        incrementado — é um órfão de um worker morto mid-job.
        """
        stale = _make_job(
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=700)
        )
        db = self._db_with_running_jobs([stale])

        with _patch_db(db):
            recovered = analysis_worker._recover_stale_jobs(stale_seconds=600)

        assert recovered == 1
        assert stale.status == "pending"
        assert stale.retries == 1
        assert stale.started_at is None
        assert stale.finished_at is None
        assert "running" in stale.last_error
        db.commit.assert_called_once()

    def test_job_running_recente_e_deixado_em_paz(self):
        """
        Um job 'running' dentro do limiar pode estar vivo em um worker irmão
        e NÃO deve ser roubado.
        """
        fresh = _make_job(updated_at=datetime.utcnow() - timedelta(seconds=30))
        db = self._db_with_running_jobs([fresh])

        with _patch_db(db):
            recovered = analysis_worker._recover_stale_jobs(stale_seconds=600)

        assert recovered == 0
        assert fresh.status == "running"
        assert fresh.retries == 0
        db.commit.assert_not_called()

    def test_job_orfao_sem_retries_restantes_vai_para_failed(self):
        """
        Se o job órfão já esgotou max_retries, marcar 'failed' em vez de
        reenfileirar para sempre (respeita a contabilidade de _execute_job).
        """
        exhausted = _make_job(
            retries=3,
            max_retries=3,
            updated_at=datetime.utcnow() - timedelta(seconds=1000),
        )
        db = self._db_with_running_jobs([exhausted])

        with _patch_db(db):
            recovered = analysis_worker._recover_stale_jobs(stale_seconds=600)

        assert recovered == 1
        assert exhausted.status == "failed"
        assert exhausted.retries == 3  # não incrementa além do limite
        assert exhausted.finished_at is not None
        db.commit.assert_called_once()

    def test_job_sem_nenhum_timestamp_e_tratado_como_orfao(self):
        """Job 'running' sem updated_at/started_at/created_at é recuperado."""
        ghost = _make_job()
        db = self._db_with_running_jobs([ghost])

        with _patch_db(db):
            recovered = analysis_worker._recover_stale_jobs(stale_seconds=600)

        assert recovered == 1
        assert ghost.status == "pending"

    def test_limiar_configuravel_via_env(self):
        """MEDSAFE_WORKER_STALE_JOB_SECONDS controla o limiar por env."""
        job = _make_job(updated_at=datetime.utcnow() - timedelta(seconds=120))
        db = self._db_with_running_jobs([job])

        with _patch_db(db), patch.dict(
            os.environ, {"MEDSAFE_WORKER_STALE_JOB_SECONDS": "60"}
        ):
            recovered = analysis_worker._recover_stale_jobs()

        assert recovered == 1
        assert job.status == "pending"


class TestReleaseJob:
    """Tests for _release_job (devolução no shutdown após estourar o drain)."""

    def _db_with_first(self, job):
        db = MagicMock()
        chain = db.query.return_value.filter.return_value.filter.return_value
        chain.first.return_value = job
        return db

    def test_devolve_job_ainda_running_para_pending(self):
        job = _make_job(id="job-9")
        db = self._db_with_first(job)

        with _patch_db(db):
            analysis_worker._release_job("job-9", "drain estourado")

        assert job.status == "pending"
        assert job.retries == 1
        assert job.last_error == "drain estourado"
        db.commit.assert_called_once()

    def test_nao_faz_nada_se_job_ja_saiu_de_running(self):
        """Guarda contra corrida: o job terminou entre o timeout e a liberação."""
        db = self._db_with_first(None)

        with _patch_db(db):
            analysis_worker._release_job("job-9", "drain estourado")

        db.commit.assert_not_called()


class TestDrainGracioso:
    """Tests for signal handling and the shutdown-aware main loop."""

    def test_instala_handlers_de_sigterm_e_sigint(self):
        loop = MagicMock()
        shutdown_event = asyncio.Event()

        analysis_worker._install_signal_handlers(loop, shutdown_event)

        registered = {call.args[0] for call in loop.add_signal_handler.call_args_list}
        assert registered == {signal.SIGTERM, signal.SIGINT}

    def test_request_shutdown_seta_a_flag(self):
        shutdown_event = asyncio.Event()
        analysis_worker._request_shutdown(shutdown_event, "SIGTERM")
        assert shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_sigterm_no_meio_do_job_drena_e_encerra(self):
        """
        SIGTERM durante um job: a flag é setada, o job em andamento TERMINA
        e o loop encerra sem reivindicar nenhum job novo.
        """
        shutdown_event = asyncio.Event()
        executed = []
        claims = []

        def claim_job():
            claims.append(1)
            return "job-1" if len(claims) == 1 else None

        async def fake_execute(job_id):
            # Simula o SIGTERM chegando no meio da execução
            analysis_worker._request_shutdown(shutdown_event, "SIGTERM")
            await asyncio.sleep(0)
            executed.append(job_id)

        with patch.object(analysis_worker, "_execute_job", fake_execute):
            await asyncio.wait_for(
                analysis_worker._run_loop(
                    claim_job, shutdown_event, idle_sleep=0.01, drain_timeout=5.0
                ),
                timeout=5.0,
            )

        assert shutdown_event.is_set()
        assert executed == ["job-1"]  # o job em andamento foi concluído
        assert len(claims) == 1  # nenhum job novo após o sinal

    @pytest.mark.asyncio
    async def test_shutdown_durante_idle_encerra_sem_esperar_o_poll(self):
        """O sleep de idle é interrompível: o shutdown não espera 30s."""
        shutdown_event = asyncio.Event()

        loop_task = asyncio.create_task(
            analysis_worker._run_loop(
                lambda: None, shutdown_event, idle_sleep=30.0, drain_timeout=5.0
            )
        )
        await asyncio.sleep(0.05)
        analysis_worker._request_shutdown(shutdown_event, "SIGINT")

        await asyncio.wait_for(loop_task, timeout=2.0)

    @pytest.mark.asyncio
    async def test_job_que_estoura_o_drain_e_devolvido_para_a_fila(self):
        """
        Se o job não termina dentro do drain_timeout, ele é cancelado e
        liberado de volta para um estado recuperável (nunca fica 'running').
        """
        shutdown_event = asyncio.Event()
        started = asyncio.Event()
        claims = []

        def claim_job():
            claims.append(1)
            return "job-9" if len(claims) == 1 else None

        async def never_ends(job_id):
            started.set()
            await asyncio.sleep(60)

        with patch.object(analysis_worker, "_execute_job", never_ends), patch.object(
            analysis_worker, "_release_job"
        ) as release:
            loop_task = asyncio.create_task(
                analysis_worker._run_loop(
                    claim_job, shutdown_event, idle_sleep=0.01, drain_timeout=0.05
                )
            )
            await asyncio.wait_for(started.wait(), timeout=1.0)
            shutdown_event.set()
            await asyncio.wait_for(loop_task, timeout=2.0)

        release.assert_called_once()
        assert release.call_args[0][0] == "job-9"
