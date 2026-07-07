"""
Data Retention Worker - LGPD Compliance.

Este worker executa periodicamente para:
1. Remover dados expirados conforme política de retenção LGPD
2. Anonimizar dados sensíveis em registros antigos
3. Gerar relatório de auditoria de exclusões

Executar como:
  python -m backend.app.workers.data_retention_worker

SECURITY: Este é um processo crítico de compliance. Todos os deletions são logados
no audit_logs com justificativa LGPD e não podem ser revertidos.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, column, delete, func, inspect, or_, table, text, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db.database import get_db_context
from ..db.models import AnalysisJob, HITLReview, IngestJob, Report, Triage

logger = logging.getLogger(__name__)
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class RetentionPolicy:
    """Define uma política de retenção para uma tabela."""

    table_name: str
    retention_days: int
    date_column: str = "created_at"
    soft_delete: bool = True  # Se True, marca is_deleted ao invés de DELETE
    anonymize_columns: List[str] = field(default_factory=list)
    cascade_tables: List[str] = field(default_factory=list)


@dataclass
class RetentionResult:
    """Resultado da execução de uma política de retenção."""

    table_name: str
    records_processed: int
    records_deleted: int
    records_anonymized: int
    errors: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0


# =============================================================================
# Políticas de Retenção LGPD
# =============================================================================


def get_retention_policies() -> List[RetentionPolicy]:
    """
    Retorna as políticas de retenção baseadas nas configurações.

    Conformidade:
    - CFM Resolução 1821/2007: Prontuários médicos = 20 anos mínimo
    - LGPD Art. 15: Dados devem ser eliminados após término do tratamento
    - LGPD Art. 37: Logs de acesso mantidos durante período de guarda

    Configuramos valores mais curtos por padrão para dados de staging/teste,
    ajustar para produção conforme requisitos regulatórios.
    """
    return [
        # Jobs de análise - dados operacionais (contêm estado com PHI)
        RetentionPolicy(
            table_name="analysis_jobs",
            retention_days=settings.retention_analysis_jobs_days,
            date_column="finished_at",  # Retenção após conclusão
            soft_delete=False,  # Hard delete - dados operacionais
            anonymize_columns=["payload", "state", "last_error"],
        ),
        # Triagens - dados clínicos (PHI)
        RetentionPolicy(
            table_name="triage",
            retention_days=settings.retention_triages_days,
            date_column="created_at",
            soft_delete=True,  # Soft delete para auditoria
            anonymize_columns=["meds_in_use", "allergies", "notes", "cid_codes"],
            cascade_tables=["reports"],
        ),
        # Relatórios - derivados de triagens
        RetentionPolicy(
            table_name="reports",
            retention_days=settings.retention_reports_days,
            date_column="created_at",
            soft_delete=True,
            anonymize_columns=["contraindications", "interactions", "analysis_notes"],
        ),
        # Revisões HITL - auditoria médica
        RetentionPolicy(
            table_name="hitl_reviews",
            retention_days=settings.retention_hitl_reviews_days,
            date_column="created_at",
            soft_delete=True,  # Nunca hard delete - compliance
            anonymize_columns=["physician_notes", "modifications"],
        ),
        # Jobs de ingestão - dados operacionais
        RetentionPolicy(
            table_name="ingest_jobs",
            retention_days=settings.retention_ingest_jobs_days,
            date_column="created_at",
            soft_delete=False,
            anonymize_columns=["errors", "processed_items"],
        ),
    ]


# =============================================================================
# Funções de Retenção
# =============================================================================


def _get_cutoff_date(retention_days: int) -> datetime:
    """Calcula a data de corte para retenção."""
    return datetime.utcnow() - timedelta(days=retention_days)


def _execute_anonymization(
    db: Session,
    table_name: str,
    columns: List[str],
    cutoff_date: datetime,
    date_column: str,
) -> int:
    """
    Anonimiza colunas sensíveis em registros antigos.

    LGPD Art. 18, V: Direito à anonimização de dados.
    """
    if not columns:
        return 0

    _validate_identifier(table_name, "table_name")
    _validate_identifier(date_column, "date_column")
    for col in columns:
        _validate_identifier(col, "column")

    valid_columns = [col for col in columns if _table_has_column(db, table_name, col)]
    missing_columns = [col for col in columns if col not in valid_columns]
    if missing_columns:
        logger.warning(
            f"Tabela {table_name} não tem colunas {missing_columns}, pulando anonimização dessas colunas"
        )
    if not valid_columns:
        return 0

    # Verificar se tabela tem coluna is_deleted (soft delete)
    has_is_deleted = _table_has_column(db, table_name, "is_deleted")
    has_updated_at = _table_has_column(db, table_name, "updated_at")

    t = table(
        table_name,
        column(date_column),
        column("is_deleted"),
        *([column("updated_at")] if has_updated_at else []),
        *[column(col) for col in valid_columns],
    )
    stmt = update(t).where(column(date_column) < cutoff_date)
    if has_is_deleted:
        stmt = stmt.where(
            or_(column("is_deleted") == False, column("is_deleted").is_(None))
        )  # noqa: E712
    values = {col: '"[ANONYMIZED_LGPD]"' for col in valid_columns}
    if has_updated_at:
        values["updated_at"] = func.now()
    stmt = stmt.values(**values)

    try:
        result = db.execute(stmt)
        return result.rowcount
    except Exception as e:
        logger.error(f"Erro ao anonimizar {table_name}: {e}")
        return 0


def _execute_soft_delete(
    db: Session,
    table_name: str,
    cutoff_date: datetime,
    date_column: str,
) -> int:
    """
    Marca registros como deletados (soft delete).

    Mantém registro para compliance/auditoria mas impede acesso normal.
    """
    _validate_identifier(table_name, "table_name")
    _validate_identifier(date_column, "date_column")

    # Verificar se tabela suporta soft delete
    if not _table_has_column(db, table_name, "is_deleted"):
        logger.warning(
            f"Tabela {table_name} não tem coluna is_deleted, pulando soft delete"
        )
        return 0

    has_deleted_at = _table_has_column(db, table_name, "deleted_at")
    has_updated_at = _table_has_column(db, table_name, "updated_at")
    t = table(
        table_name,
        column(date_column),
        column("is_deleted"),
        *([column("deleted_at")] if has_deleted_at else []),
        *([column("updated_at")] if has_updated_at else []),
    )
    values = {"is_deleted": True}
    if has_deleted_at:
        values["deleted_at"] = func.now()
    if has_updated_at:
        values["updated_at"] = func.now()
    stmt = (
        update(t)
        .where(column(date_column) < cutoff_date)
        .where(
            or_(column("is_deleted") == False, column("is_deleted").is_(None))
        )  # noqa: E712
        .values(**values)
    )

    try:
        result = db.execute(stmt)
        return result.rowcount
    except Exception as e:
        logger.error(f"Erro ao soft delete {table_name}: {e}")
        return 0


def _execute_hard_delete(
    db: Session,
    table_name: str,
    cutoff_date: datetime,
    date_column: str,
) -> int:
    """
    Remove registros permanentemente (hard delete).

    Usar apenas para dados operacionais sem requisito de auditoria.
    """
    _validate_identifier(table_name, "table_name")
    _validate_identifier(date_column, "date_column")
    t = table(table_name, column(date_column))
    stmt = delete(t).where(column(date_column) < cutoff_date)

    try:
        result = db.execute(stmt)
        return result.rowcount
    except Exception as e:
        logger.error(f"Erro ao hard delete {table_name}: {e}")
        return 0


def _table_has_column(db: Session, table_name: str, column_name: str) -> bool:
    """Verifica se uma tabela tem uma coluna específica."""
    try:
        _validate_identifier(table_name, "table_name")
        _validate_identifier(column_name, "column_name")
        inspector = inspect(db.get_bind())
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def _validate_identifier(name: str, kind: str) -> None:
    if not name or not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier for {kind}: {name}")


def _log_retention_action(
    db: Session,
    action: str,
    table_name: str,
    records_affected: int,
    policy: RetentionPolicy,
) -> None:
    """
    Registra ação de retenção no audit_log para compliance.

    LGPD Art. 37: Controlador deve manter registro das operações de tratamento.
    """
    # Verificar se tabela audit_logs existe
    if not _table_has_column(db, "audit_logs", "id"):
        logger.debug("Tabela audit_logs não existe, pulando log de auditoria")
        return

    try:
        sql = """
            INSERT INTO audit_logs (
                id, event_type, event_category, severity, user_id,
                resource_type, action, details, success, created_at
            ) VALUES (
                gen_random_uuid(), :event_type, :event_category, :severity, NULL,
                :resource_type, :action, :details, TRUE, NOW()
            )
        """

        details = {
            "action": action,
            "table": table_name,
            "records_affected": records_affected,
            "retention_days": policy.retention_days,
            "compliance": "LGPD",
            "justification": f"Retenção automática após {policy.retention_days} dias",
        }

        db.execute(
            text(sql),
            {
                "event_type": f"data_retention_{action}",
                "event_category": "lgpd",
                "severity": "INFO",
                "resource_type": table_name,
                "action": action,
                "details": json.dumps(details),
            },
        )
    except Exception as e:
        logger.error(
            f"Falha ao registrar auditoria de retenção LGPD (table={table_name}, action={action}): {e}"
        )


# =============================================================================
# Executor Principal
# =============================================================================


def execute_retention_policy(policy: RetentionPolicy) -> RetentionResult:
    """
    Executa uma política de retenção completa.

    Ordem de operações:
    1. Anonimizar colunas sensíveis (se configurado)
    2. Soft delete ou hard delete (conforme política)
    3. Registrar ação no audit_log
    """
    start_time = time.time()

    result = RetentionResult(
        table_name=policy.table_name,
        records_processed=0,
        records_deleted=0,
        records_anonymized=0,
    )

    cutoff_date = _get_cutoff_date(policy.retention_days)

    logger.info(
        f"Executando retenção para {policy.table_name}: "
        f"cutoff={cutoff_date.isoformat()}, retention={policy.retention_days} dias"
    )
    try:
        with get_db_context() as db:
            # 1. Anonimizar colunas sensíveis
            if policy.anonymize_columns:
                anonymized = _execute_anonymization(
                    db,
                    policy.table_name,
                    policy.anonymize_columns,
                    cutoff_date,
                    policy.date_column,
                )
                result.records_anonymized = anonymized

                if anonymized > 0:
                    _log_retention_action(
                        db, "anonymize", policy.table_name, anonymized, policy
                    )

            # 2. Executar delete (soft ou hard)
            if policy.soft_delete:
                deleted = _execute_soft_delete(
                    db, policy.table_name, cutoff_date, policy.date_column
                )
            else:
                deleted = _execute_hard_delete(
                    db, policy.table_name, cutoff_date, policy.date_column
                )

            result.records_deleted = deleted
            result.records_processed = result.records_anonymized + deleted

            if deleted > 0:
                action = "soft_delete" if policy.soft_delete else "hard_delete"
                _log_retention_action(db, action, policy.table_name, deleted, policy)

            db.commit()

    except Exception as e:
        result.errors.append(str(e))
        logger.error(
            f"Erro ao executar retenção para {policy.table_name}: {e}", exc_info=True
        )

    result.execution_time_ms = (time.time() - start_time) * 1000

    logger.info(
        f"Retenção {policy.table_name}: "
        f"processados={result.records_processed}, "
        f"deletados={result.records_deleted}, "
        f"anonimizados={result.records_anonymized}, "
        f"tempo={result.execution_time_ms:.2f}ms"
    )

    return result


def run_all_retention_policies() -> List[RetentionResult]:
    """
    Executa todas as políticas de retenção configuradas.

    Returns:
        Lista de resultados de cada política.
    """
    policies = get_retention_policies()
    results = []

    logger.info(f"Iniciando execução de {len(policies)} políticas de retenção")

    for policy in policies:
        try:
            result = execute_retention_policy(policy)
            results.append(result)
        except Exception as e:
            logger.error(f"Falha crítica na política {policy.table_name}: {e}")
            results.append(
                RetentionResult(
                    table_name=policy.table_name,
                    records_processed=0,
                    records_deleted=0,
                    records_anonymized=0,
                    errors=[str(e)],
                )
            )

    # Resumo final
    total_processed = sum(r.records_processed for r in results)
    total_deleted = sum(r.records_deleted for r in results)
    total_anonymized = sum(r.records_anonymized for r in results)
    total_errors = sum(len(r.errors) for r in results)

    logger.info(
        f"Retenção concluída: "
        f"processados={total_processed}, "
        f"deletados={total_deleted}, "
        f"anonimizados={total_anonymized}, "
        f"erros={total_errors}"
    )

    return results


# =============================================================================
# Worker Loop
# =============================================================================


async def main() -> None:
    """
    Loop principal do worker de retenção.

    Executa a cada RETENTION_INTERVAL_HOURS (padrão: 24h).
    Em produção, configurar via cron ou scheduler externo.
    """
    from ..utils.error_tracking import setup_error_tracking

    setup_error_tracking(settings)

    interval_hours = float(os.getenv("RETENTION_INTERVAL_HOURS", "24"))
    run_once = os.getenv("RETENTION_RUN_ONCE", "false").lower() == "true"

    logger.info(
        f"MedSafe data retention worker started "
        f"(interval={interval_hours}h, run_once={run_once})"
    )

    while True:
        try:
            results = run_all_retention_policies()

            # Verificar erros críticos
            critical_errors = [r for r in results if r.errors]
            if critical_errors:
                logger.warning(
                    f"Retenção concluída com {len(critical_errors)} erros: "
                    f"{[r.table_name for r in critical_errors]}"
                )

        except Exception as e:
            logger.error(f"Erro crítico no worker de retenção: {e}", exc_info=True)

        if run_once:
            logger.info("RETENTION_RUN_ONCE=true, encerrando worker")
            break

        # Aguardar próximo ciclo
        await asyncio.sleep(interval_hours * 3600)


if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(main())
