"""
Política de Retenção de Dados do MedSafe.

LGPD Compliance: Define períodos de retenção e procedimentos de limpeza
para dados sensíveis de saúde (PHI) armazenados no sistema.

Categorias de dados:
- Dados de análise (analysis_jobs, triages, reports): Período configurável
- Logs de auditoria: Mínimo 5 anos (compliance)
- Sessões de usuário: 90 dias após expiração
- Dados de usuário deletado: Anonimização imediata
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ============================================================================
# Configuração de Retenção
# ============================================================================


class DataCategory(str, Enum):
    """Categorias de dados para política de retenção."""

    ANALYSIS_JOBS = "analysis_jobs"  # Jobs de análise (contém state com PHI)
    TRIAGES = "triages"  # Dados de triagem de pacientes
    REPORTS = "reports"  # Relatórios de análise
    HITL_REVIEWS = "hitl_reviews"  # Revisões HITL
    AUDIT_LOGS = "audit_logs"  # Logs de auditoria (compliance)
    USER_SESSIONS = "user_sessions"  # Sessões de usuário
    INGEST_JOBS = "ingest_jobs"  # Jobs de ingestão


@dataclass
class RetentionPolicy:
    """Define política de retenção para uma categoria de dados."""

    category: DataCategory
    retention_days: int
    description: str
    requires_anonymization: bool = False
    can_be_archived: bool = True
    compliance_requirement: Optional[str] = None

    @property
    def retention_period(self) -> timedelta:
        return timedelta(days=self.retention_days)


# Políticas padrão (podem ser sobrescritas via config)
DEFAULT_RETENTION_POLICIES: Dict[DataCategory, RetentionPolicy] = {
    DataCategory.ANALYSIS_JOBS: RetentionPolicy(
        category=DataCategory.ANALYSIS_JOBS,
        retention_days=365,  # 1 ano
        description="Jobs de análise contendo estado do workflow e dados de paciente",
        requires_anonymization=True,
        can_be_archived=True,
        compliance_requirement="LGPD Art. 16 - Dados necessários para finalidade",
    ),
    DataCategory.TRIAGES: RetentionPolicy(
        category=DataCategory.TRIAGES,
        retention_days=365 * 5,  # 5 anos (padrão médico)
        description="Dados de triagem de pacientes para histórico médico",
        requires_anonymization=True,
        can_be_archived=True,
        compliance_requirement="CFM Res. 1821/2007 - Prontuário médico",
    ),
    DataCategory.REPORTS: RetentionPolicy(
        category=DataCategory.REPORTS,
        retention_days=365 * 5,  # 5 anos
        description="Relatórios de análise de interações medicamentosas",
        requires_anonymization=True,
        can_be_archived=True,
        compliance_requirement="CFM Res. 1821/2007 - Prontuário médico",
    ),
    DataCategory.HITL_REVIEWS: RetentionPolicy(
        category=DataCategory.HITL_REVIEWS,
        retention_days=365 * 5,  # 5 anos (auditoria médica)
        description="Decisões de revisão humana para rastreabilidade",
        requires_anonymization=False,  # Importante para auditoria
        can_be_archived=True,
        compliance_requirement="Rastreabilidade de decisões clínicas",
    ),
    DataCategory.AUDIT_LOGS: RetentionPolicy(
        category=DataCategory.AUDIT_LOGS,
        retention_days=365 * 5,  # 5 anos (compliance)
        description="Logs de auditoria de segurança e acesso",
        requires_anonymization=False,  # Necessário para investigação
        can_be_archived=True,
        compliance_requirement="LGPD Art. 37 - Registro de operações",
    ),
    DataCategory.USER_SESSIONS: RetentionPolicy(
        category=DataCategory.USER_SESSIONS,
        retention_days=90,  # 90 dias após expiração
        description="Sessões de usuário expiradas",
        requires_anonymization=False,
        can_be_archived=False,  # Deletar permanentemente
        compliance_requirement="Segurança - Limpeza de sessões",
    ),
    DataCategory.INGEST_JOBS: RetentionPolicy(
        category=DataCategory.INGEST_JOBS,
        retention_days=180,  # 6 meses
        description="Jobs de ingestão de dados (bulas, datasets)",
        requires_anonymization=False,
        can_be_archived=False,
        compliance_requirement="Operacional",
    ),
}


# ============================================================================
# Serviço de Retenção
# ============================================================================


@dataclass
class RetentionResult:
    """Resultado de uma operação de retenção."""

    category: DataCategory
    records_processed: int = 0
    records_anonymized: int = 0
    records_archived: int = 0
    records_deleted: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class DataRetentionService:
    """
    Serviço para aplicação de políticas de retenção de dados.

    Uso:
        service = DataRetentionService(db_session)
        results = await service.apply_retention_policies()
    """

    def __init__(
        self,
        db: Session,
        policies: Optional[Dict[DataCategory, RetentionPolicy]] = None,
        dry_run: bool = False,
    ):
        self.db = db
        self.policies = policies or DEFAULT_RETENTION_POLICIES
        self.dry_run = dry_run

    async def apply_retention_policies(
        self,
        categories: Optional[List[DataCategory]] = None,
    ) -> Dict[DataCategory, RetentionResult]:
        """
        Aplica políticas de retenção para categorias especificadas.

        Args:
            categories: Lista de categorias (todas se None)

        Returns:
            Dicionário com resultados por categoria
        """
        categories = categories or list(self.policies.keys())
        results = {}

        for category in categories:
            if category not in self.policies:
                logger.warning(f"Categoria {category} não tem política definida")
                continue

            policy = self.policies[category]
            cutoff_date = datetime.utcnow() - policy.retention_period

            logger.info(
                f"Aplicando retenção para {category.value}: "
                f"registros antes de {cutoff_date.isoformat()}"
            )

            try:
                result = await self._apply_policy(category, policy, cutoff_date)
                results[category] = result
            except Exception as e:
                logger.error(f"Erro ao aplicar retenção para {category}: {e}")
                results[category] = RetentionResult(
                    category=category,
                    errors=[str(e)],
                )

        return results

    async def _apply_policy(
        self,
        category: DataCategory,
        policy: RetentionPolicy,
        cutoff_date: datetime,
    ) -> RetentionResult:
        """Aplica política de retenção para uma categoria específica."""

        result = RetentionResult(category=category)

        # Mapeamento de categoria para handler
        handlers = {
            DataCategory.ANALYSIS_JOBS: self._process_analysis_jobs,
            DataCategory.TRIAGES: self._process_triages,
            DataCategory.REPORTS: self._process_reports,
            DataCategory.HITL_REVIEWS: self._process_hitl_reviews,
            DataCategory.AUDIT_LOGS: self._process_audit_logs,
            DataCategory.USER_SESSIONS: self._process_user_sessions,
            DataCategory.INGEST_JOBS: self._process_ingest_jobs,
        }

        handler = handlers.get(category)
        if handler:
            result = await handler(policy, cutoff_date)
        else:
            result.errors.append(f"Handler não implementado para {category}")

        return result

    async def _process_analysis_jobs(
        self,
        policy: RetentionPolicy,
        cutoff_date: datetime,
    ) -> RetentionResult:
        """Processa retenção de analysis_jobs."""
        from ..db.models import AnalysisJob

        result = RetentionResult(category=DataCategory.ANALYSIS_JOBS)

        try:
            # Buscar jobs antigos completados
            query = self.db.query(AnalysisJob).filter(
                and_(
                    AnalysisJob.created_at < cutoff_date,
                    AnalysisJob.status.in_(["completed", "failed", "cancelled"]),
                )
            )

            old_jobs = query.all()
            result.records_processed = len(old_jobs)

            if self.dry_run:
                logger.info(f"[DRY RUN] Processaria {len(old_jobs)} analysis_jobs")
                return result

            for job in old_jobs:
                if policy.requires_anonymization:
                    # Anonimizar state (contém PHI)
                    job.state = {"anonymized": True, "reason": "retention_policy"}
                    job.payload = {"anonymized": True}
                    result.records_anonymized += 1
                else:
                    self.db.delete(job)
                    result.records_deleted += 1

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            result.errors.append(str(e))
            logger.error(f"Erro processando analysis_jobs: {e}")

        return result

    async def _process_triages(
        self,
        policy: RetentionPolicy,
        cutoff_date: datetime,
    ) -> RetentionResult:
        """Processa retenção de triages."""
        from ..db.models import Triage

        result = RetentionResult(category=DataCategory.TRIAGES)

        try:
            query = self.db.query(Triage).filter(Triage.created_at < cutoff_date)

            old_triages = query.all()
            result.records_processed = len(old_triages)

            if self.dry_run:
                logger.info(f"[DRY RUN] Processaria {len(old_triages)} triages")
                return result

            for triage in old_triages:
                if policy.requires_anonymization:
                    # Anonimizar dados sensíveis
                    triage.meds_in_use = []
                    triage.allergies = []
                    triage.cid_codes = []
                    triage.notes = "[ANONYMIZED]"
                    triage.user_id = None
                    result.records_anonymized += 1
                else:
                    self.db.delete(triage)
                    result.records_deleted += 1

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            result.errors.append(str(e))
            logger.error(f"Erro processando triages: {e}")

        return result

    async def _process_reports(
        self,
        policy: RetentionPolicy,
        cutoff_date: datetime,
    ) -> RetentionResult:
        """Processa retenção de reports."""
        from ..db.models import Report

        result = RetentionResult(category=DataCategory.REPORTS)

        try:
            query = self.db.query(Report).filter(Report.created_at < cutoff_date)

            old_reports = query.all()
            result.records_processed = len(old_reports)

            if self.dry_run:
                logger.info(f"[DRY RUN] Processaria {len(old_reports)} reports")
                return result

            for report in old_reports:
                if policy.requires_anonymization:
                    # Manter estrutura mas anonimizar conteúdo
                    report.analysis_notes = "[ANONYMIZED]"
                    result.records_anonymized += 1
                else:
                    self.db.delete(report)
                    result.records_deleted += 1

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            result.errors.append(str(e))
            logger.error(f"Erro processando reports: {e}")

        return result

    async def _process_hitl_reviews(
        self,
        policy: RetentionPolicy,
        cutoff_date: datetime,
    ) -> RetentionResult:
        """Processa retenção de hitl_reviews (geralmente arquivamento)."""
        from ..db.models import HITLReview

        result = RetentionResult(category=DataCategory.HITL_REVIEWS)

        try:
            query = self.db.query(HITLReview).filter(
                HITLReview.created_at < cutoff_date
            )

            old_reviews = query.count()
            result.records_processed = old_reviews

            # HITL reviews são importantes para auditoria - apenas arquivar
            if policy.can_be_archived:
                logger.info(f"HITL reviews ({old_reviews}) marcados para arquivamento")
                result.records_archived = old_reviews

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Erro processando hitl_reviews: {e}")

        return result

    async def _process_audit_logs(
        self,
        policy: RetentionPolicy,
        cutoff_date: datetime,
    ) -> RetentionResult:
        """Processa retenção de audit_logs (arquivamento obrigatório)."""
        from ..db.user_models import AuditLog

        result = RetentionResult(category=DataCategory.AUDIT_LOGS)

        try:
            query = self.db.query(AuditLog).filter(AuditLog.created_at < cutoff_date)

            old_logs = query.count()
            result.records_processed = old_logs

            # Audit logs NUNCA são deletados - apenas arquivados
            logger.info(
                f"Audit logs ({old_logs}) antes de {cutoff_date.isoformat()} "
                "devem ser arquivados em cold storage"
            )
            result.records_archived = old_logs

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Erro processando audit_logs: {e}")

        return result

    async def _process_user_sessions(
        self,
        policy: RetentionPolicy,
        cutoff_date: datetime,
    ) -> RetentionResult:
        """Processa retenção de user_sessions (deleção)."""
        from ..db.user_models import UserSession

        result = RetentionResult(category=DataCategory.USER_SESSIONS)

        try:
            # Sessões expiradas e inativas
            query = self.db.query(UserSession).filter(
                or_(
                    and_(
                        UserSession.expires_at < cutoff_date,
                        UserSession.is_active.is_(False),
                    ),
                    UserSession.created_at < cutoff_date,
                )
            )

            old_sessions = query.all()
            result.records_processed = len(old_sessions)

            if self.dry_run:
                logger.info(f"[DRY RUN] Deletaria {len(old_sessions)} sessions")
                return result

            # Sessões podem ser deletadas permanentemente
            for session in old_sessions:
                self.db.delete(session)
                result.records_deleted += 1

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            result.errors.append(str(e))
            logger.error(f"Erro processando user_sessions: {e}")

        return result

    async def _process_ingest_jobs(
        self,
        policy: RetentionPolicy,
        cutoff_date: datetime,
    ) -> RetentionResult:
        """Processa retenção de ingest_jobs."""
        from ..db.models import IngestJob

        result = RetentionResult(category=DataCategory.INGEST_JOBS)

        try:
            query = self.db.query(IngestJob).filter(
                and_(
                    IngestJob.created_at < cutoff_date,
                    IngestJob.status.in_(["completed", "failed"]),
                )
            )

            old_jobs = query.all()
            result.records_processed = len(old_jobs)

            if self.dry_run:
                logger.info(f"[DRY RUN] Deletaria {len(old_jobs)} ingest_jobs")
                return result

            for job in old_jobs:
                self.db.delete(job)
                result.records_deleted += 1

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            result.errors.append(str(e))
            logger.error(f"Erro processando ingest_jobs: {e}")

        return result


# ============================================================================
# Funções utilitárias
# ============================================================================


def get_retention_policy(category: DataCategory) -> RetentionPolicy:
    """Retorna a política de retenção para uma categoria."""
    return DEFAULT_RETENTION_POLICIES.get(category)


def get_all_retention_policies() -> Dict[DataCategory, RetentionPolicy]:
    """Retorna todas as políticas de retenção."""
    return DEFAULT_RETENTION_POLICIES.copy()


async def run_retention_cleanup(
    db: Session,
    categories: Optional[List[DataCategory]] = None,
    dry_run: bool = True,
) -> Dict[DataCategory, RetentionResult]:
    """
    Executa limpeza de retenção.

    Args:
        db: Sessão do banco de dados
        categories: Categorias a processar (todas se None)
        dry_run: Se True, apenas simula (padrão seguro)

    Returns:
        Resultados por categoria
    """
    service = DataRetentionService(db, dry_run=dry_run)
    return await service.apply_retention_policies(categories)


# ============================================================================
# Exportações
# ============================================================================

__all__ = [
    "DataCategory",
    "RetentionPolicy",
    "RetentionResult",
    "DataRetentionService",
    "get_retention_policy",
    "get_all_retention_policies",
    "run_retention_cleanup",
    "DEFAULT_RETENTION_POLICIES",
]
