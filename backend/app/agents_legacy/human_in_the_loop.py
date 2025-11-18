"""
HumanInTheLoopAgent - Sistema de supervisão humana para decisões críticas
Implementa padrão Human-in-the-Loop do Capítulo 13 - Agentic Design Patterns

Responsabilidades:
- Identificar casos que requerem validação humana
- Escalar análises de alto risco para profissionais
- Gerenciar workflow de aprovação médica
- Coletar feedback para melhoria contínua
- Pausar execução aguardando decisão humana
"""

import logging
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict

from ..config import settings
from ..db.models import Triage, Report
from ..db.database import get_db_context

logger = logging.getLogger(__name__)


class EscalationReason(str, Enum):
    """Razões para escalar para humano"""
    CRITICAL_RISK = "critical_risk"
    LOW_CONFIDENCE = "low_confidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    NOVEL_CASE = "novel_case"
    HALLUCINATION_DETECTED = "hallucination_detected"
    REGULATORY_CONCERN = "regulatory_concern"
    PATIENT_VULNERABLE = "patient_vulnerable"
    COMPLEX_INTERACTION = "complex_interaction"


class ReviewStatus(str, Enum):
    """Status da revisão humana"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    ESCALATED_FURTHER = "escalated_further"


class ReviewPriority(str, Enum):
    """Prioridade da revisão"""
    ROUTINE = "routine"       # 24-48h
    URGENT = "urgent"         # 2-4h
    EMERGENCY = "emergency"   # < 30min


@dataclass
class HumanReviewRequest:
    """Solicitação de revisão humana"""
    id: str
    session_id: str
    triage_id: str
    report_id: Optional[str]

    # Informações da análise
    analysis: Dict[str, Any]
    triage_data: Dict[str, Any]

    # Razões para escalação
    escalation_reasons: List[str]
    confidence_score: float
    risk_level: str

    # Metadados da revisão
    priority: str
    requested_at: str
    deadline: str
    status: str

    # Informações do revisor
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    review_decision: Optional[str] = None

    # Feedback
    feedback: Optional[Dict[str, Any]] = None


class HumanInTheLoopAgent:
    """
    Agente para gerenciar intervenção humana em casos críticos
    """

    def __init__(self):
        """Inicializar Human-in-the-Loop Agent"""
        self.pending_reviews: Dict[str, HumanReviewRequest] = {}

        # Critérios de escalação (configuráveis)
        self.escalation_criteria = {
            'min_confidence_threshold': 0.7,
            'critical_risk_auto_escalate': True,
            'high_risk_with_vulnerable_patient': True,
            'hallucination_threshold': 0.5,
            'max_contraindications_auto': 3,
            'novel_interaction_threshold': 0.8
        }

        logger.info("👤 HumanInTheLoopAgent inicializado")

    async def evaluate_need_for_human_review(
        self,
        analysis: Dict[str, Any],
        triage_data: Dict[str, Any],
        session_id: str
    ) -> tuple[bool, List[str]]:
        """
        Avaliar se caso requer revisão humana

        Returns:
            (needs_review, escalation_reasons)
        """
        escalation_reasons = []

        # 1. CRITÉRIO: Risco Crítico
        if analysis.get('risk_level') == 'critical':
            escalation_reasons.append(EscalationReason.CRITICAL_RISK)
            logger.warning(f"⚠️ Risco crítico detectado - Escalando para revisão: {session_id}")

        # 2. CRITÉRIO: Baixa Confiança
        confidence = analysis.get('confidence_score', 1.0)
        if confidence < self.escalation_criteria['min_confidence_threshold']:
            escalation_reasons.append(EscalationReason.LOW_CONFIDENCE)
            logger.warning(f"⚠️ Baixa confiança ({confidence:.2f}) - Escalando: {session_id}")

        # 3. CRITÉRIO: Alucinação Detectada
        hallucination_risk = analysis.get('hallucination_risk', 0.0)
        if hallucination_risk > self.escalation_criteria['hallucination_threshold']:
            escalation_reasons.append(EscalationReason.HALLUCINATION_DETECTED)
            logger.warning(f"⚠️ Possível alucinação ({hallucination_risk:.2f}) - Escalando: {session_id}")

        # 4. CRITÉRIO: Evidências Conflitantes
        if self._has_conflicting_evidence(analysis):
            escalation_reasons.append(EscalationReason.CONFLICTING_EVIDENCE)
            logger.warning(f"⚠️ Evidências conflitantes - Escalando: {session_id}")

        # 5. CRITÉRIO: Caso Novel (sem precedentes similares)
        if await self._is_novel_case(analysis, triage_data):
            escalation_reasons.append(EscalationReason.NOVEL_CASE)
            logger.info(f"📊 Caso novel detectado - Escalando para revisão: {session_id}")

        # 6. CRITÉRIO: Paciente Vulnerável + Risco Alto
        if self._is_vulnerable_patient(triage_data) and analysis.get('risk_level') in ['high', 'critical']:
            escalation_reasons.append(EscalationReason.PATIENT_VULNERABLE)
            logger.warning(f"⚠️ Paciente vulnerável com alto risco - Escalando: {session_id}")

        # 7. CRITÉRIO: Múltiplas Contraindicações
        contraindications = analysis.get('contraindications', [])
        if len(contraindications) > self.escalation_criteria['max_contraindications_auto']:
            escalation_reasons.append(EscalationReason.COMPLEX_INTERACTION)
            logger.warning(f"⚠️ Múltiplas contraindicações ({len(contraindications)}) - Escalando: {session_id}")

        # 8. CRITÉRIO: Problemas Regulatórios
        compliance_issues = analysis.get('compliance_issues', [])
        critical_compliance = [i for i in compliance_issues if i.get('severity') == 'critical']
        if critical_compliance:
            escalation_reasons.append(EscalationReason.REGULATORY_CONCERN)
            logger.warning(f"⚠️ Problemas regulatórios - Escalando: {session_id}")

        needs_review = len(escalation_reasons) > 0

        if needs_review:
            logger.info(f"🔔 Caso {session_id} requer revisão humana: {len(escalation_reasons)} razões")
        else:
            logger.info(f"✅ Caso {session_id} aprovado automaticamente (sem necessidade de revisão)")

        return needs_review, escalation_reasons

    def _has_conflicting_evidence(self, analysis: Dict[str, Any]) -> bool:
        """Detectar evidências conflitantes"""
        # Verificar se há contraindicações mas risco baixo
        contraindications = analysis.get('contraindications', [])
        risk_level = analysis.get('risk_level', 'low')

        if len(contraindications) >= 2 and risk_level == 'low':
            return True

        # Verificar se há interações graves mas análise diz seguro
        interactions = analysis.get('interactions', [])
        severe_interactions = [i for i in interactions if i.get('severity') in ['critical', 'high']]

        if severe_interactions and risk_level == 'low':
            return True

        return False

    async def _is_novel_case(
        self,
        analysis: Dict[str, Any],
        triage_data: Dict[str, Any]
    ) -> bool:
        """
        Verificar se é caso novel (sem casos similares no histórico)

        Returns:
            True se for caso novel
        """
        # TODO: Implementar busca de similaridade no histórico
        # Por enquanto, critérios simples:

        # Caso com combinação incomum
        meds_in_use = triage_data.get('meds_in_use', [])
        if len(meds_in_use) >= 5:  # Polimedicação complexa
            return True

        # Paciente com múltiplas comorbidades
        conditions = triage_data.get('cid_codes', [])
        if len(conditions) >= 4:
            return True

        return False

    def _is_vulnerable_patient(self, triage_data: Dict[str, Any]) -> bool:
        """Verificar se paciente é de população vulnerável"""
        age = triage_data.get('age', 0)
        pregnant = triage_data.get('pregnant', False)

        # Crianças, idosos, grávidas são vulneráveis
        if age < 18 or age >= 65 or pregnant:
            return True

        # Pacientes com insuficiência renal/hepática
        if triage_data.get('renal_function') or triage_data.get('hepatic_function'):
            return True

        return False

    async def request_human_review(
        self,
        analysis: Dict[str, Any],
        triage_data: Dict[str, Any],
        triage_id: str,
        session_id: str,
        escalation_reasons: List[str],
        report_id: Optional[str] = None
    ) -> HumanReviewRequest:
        """
        Criar solicitação de revisão humana

        Returns:
            HumanReviewRequest com detalhes da solicitação
        """
        # Determinar prioridade
        priority = self._determine_priority(analysis, escalation_reasons)

        # Calcular deadline baseado na prioridade
        deadline = self._calculate_deadline(priority)

        # Criar solicitação
        review_request = HumanReviewRequest(
            id=str(uuid.uuid4()),
            session_id=session_id,
            triage_id=triage_id,
            report_id=report_id,
            analysis=analysis,
            triage_data=triage_data,
            escalation_reasons=escalation_reasons,
            confidence_score=analysis.get('confidence_score', 0.0),
            risk_level=analysis.get('risk_level', 'unknown'),
            priority=priority,
            requested_at=datetime.now().isoformat(),
            deadline=deadline.isoformat(),
            status=ReviewStatus.PENDING
        )

        # Armazenar solicitação
        self.pending_reviews[review_request.id] = review_request

        # Persistir no banco de dados
        await self._persist_review_request(review_request)

        # Notificar revisores (TODO: implementar sistema de notificação)
        await self._notify_reviewers(review_request)

        logger.info(
            f"📋 Revisão humana solicitada: {review_request.id} "
            f"(Prioridade: {priority}, Deadline: {deadline.isoformat()})"
        )

        return review_request

    def _determine_priority(
        self,
        analysis: Dict[str, Any],
        escalation_reasons: List[str]
    ) -> ReviewPriority:
        """Determinar prioridade da revisão"""

        # EMERGENCY: Risco crítico ou alucinação grave
        if (
            EscalationReason.CRITICAL_RISK in escalation_reasons or
            (EscalationReason.HALLUCINATION_DETECTED in escalation_reasons and
             analysis.get('hallucination_risk', 0) > 0.7)
        ):
            return ReviewPriority.EMERGENCY

        # URGENT: Paciente vulnerável, risco alto, problemas regulatórios
        if (
            EscalationReason.PATIENT_VULNERABLE in escalation_reasons or
            analysis.get('risk_level') == 'high' or
            EscalationReason.REGULATORY_CONCERN in escalation_reasons
        ):
            return ReviewPriority.URGENT

        # ROUTINE: Outros casos
        return ReviewPriority.ROUTINE

    def _calculate_deadline(self, priority: ReviewPriority) -> datetime:
        """Calcular deadline baseado na prioridade"""
        now = datetime.now()

        if priority == ReviewPriority.EMERGENCY:
            return now + timedelta(minutes=30)
        elif priority == ReviewPriority.URGENT:
            return now + timedelta(hours=4)
        else:  # ROUTINE
            return now + timedelta(hours=48)

    async def _persist_review_request(self, review_request: HumanReviewRequest) -> None:
        """Persistir solicitação de revisão no banco de dados"""
        try:
            with get_db_context() as db:
                # Atualizar relatório para indicar que está em revisão
                if review_request.report_id:
                    report = db.query(Report).filter(Report.id == review_request.report_id).first()
                    if report:
                        report.status = "pending_review"
                        report.analysis_notes = (
                            f"⏳ AGUARDANDO REVISÃO HUMANA\n"
                            f"Prioridade: {review_request.priority}\n"
                            f"Razões: {', '.join(review_request.escalation_reasons)}\n\n"
                            f"{report.analysis_notes}"
                        )
                        db.commit()

                # Atualizar triagem
                triage = db.query(Triage).filter(Triage.id == review_request.triage_id).first()
                if triage:
                    triage.status = "pending_human_review"
                    db.commit()

                logger.debug(f"💾 Review request persistido: {review_request.id}")

        except Exception as e:
            logger.error(f"❌ Erro ao persistir review request: {e}")

    async def _notify_reviewers(self, review_request: HumanReviewRequest) -> None:
        """
        Notificar revisores sobre nova solicitação

        TODO: Implementar sistema de notificação real (email, Slack, etc)
        """
        logger.info(
            f"📧 [NOTIFICAÇÃO] Nova revisão solicitada:\n"
            f"   ID: {review_request.id}\n"
            f"   Prioridade: {review_request.priority}\n"
            f"   Deadline: {review_request.deadline}\n"
            f"   Risco: {review_request.risk_level}\n"
            f"   Razões: {', '.join(review_request.escalation_reasons)}"
        )

        # TODO: Enviar email, SMS, ou notificação Slack para equipe médica

    async def get_pending_reviews(
        self,
        priority: Optional[ReviewPriority] = None,
        overdue_only: bool = False
    ) -> List[HumanReviewRequest]:
        """
        Obter lista de revisões pendentes

        Args:
            priority: Filtrar por prioridade específica
            overdue_only: Retornar apenas revisões atrasadas

        Returns:
            Lista de revisões pendentes
        """
        reviews = []

        for review in self.pending_reviews.values():
            # Filtrar por status
            if review.status not in [ReviewStatus.PENDING, ReviewStatus.IN_REVIEW]:
                continue

            # Filtrar por prioridade
            if priority and review.priority != priority:
                continue

            # Filtrar por overdue
            if overdue_only:
                deadline = datetime.fromisoformat(review.deadline)
                if datetime.now() < deadline:
                    continue

            reviews.append(review)

        # Ordenar por prioridade e deadline
        priority_order = {
            ReviewPriority.EMERGENCY: 0,
            ReviewPriority.URGENT: 1,
            ReviewPriority.ROUTINE: 2
        }

        reviews.sort(
            key=lambda r: (
                priority_order.get(r.priority, 999),
                r.deadline
            )
        )

        return reviews

    async def submit_review(
        self,
        review_id: str,
        reviewer_id: str,
        decision: ReviewStatus,
        notes: str,
        modified_analysis: Optional[Dict[str, Any]] = None,
        feedback: Optional[Dict[str, Any]] = None
    ) -> HumanReviewRequest:
        """
        Submeter revisão humana

        Args:
            review_id: ID da revisão
            reviewer_id: ID do revisor
            decision: Decisão (APPROVED, REJECTED, MODIFIED)
            notes: Notas do revisor
            modified_analysis: Análise modificada (se aplicável)
            feedback: Feedback para melhoria do sistema

        Returns:
            Review request atualizado
        """
        if review_id not in self.pending_reviews:
            raise ValueError(f"Review {review_id} não encontrado")

        review = self.pending_reviews[review_id]

        # Atualizar revisão
        review.reviewer_id = reviewer_id
        review.reviewed_at = datetime.now().isoformat()
        review.status = decision
        review.review_notes = notes
        review.review_decision = decision
        review.feedback = feedback

        # Se foi modificado, atualizar análise
        if modified_analysis:
            review.analysis = modified_analysis

        # Persistir decisão
        await self._persist_review_decision(review)

        # Processar feedback para aprendizado
        if feedback:
            await self._process_feedback(review, feedback)

        logger.info(
            f"✅ Revisão concluída: {review_id} "
            f"(Decisão: {decision}, Revisor: {reviewer_id})"
        )

        return review

    async def _persist_review_decision(self, review: HumanReviewRequest) -> None:
        """Persistir decisão da revisão no banco"""
        try:
            with get_db_context() as db:
                if review.report_id:
                    report = db.query(Report).filter(Report.id == review.report_id).first()
                    if report:
                        # Atualizar status
                        if review.status == ReviewStatus.APPROVED:
                            report.status = "approved"
                            report.is_final = True
                        elif review.status == ReviewStatus.REJECTED:
                            report.status = "rejected"
                        elif review.status == ReviewStatus.MODIFIED:
                            report.status = "modified"
                            report.is_final = True

                            # Atualizar com análise modificada
                            if review.analysis:
                                report.contraindications = review.analysis.get('contraindications', [])
                                report.interactions = review.analysis.get('interactions', [])
                                report.risk_level = review.analysis.get('risk_level', report.risk_level)

                        # Adicionar notas do revisor
                        report.analysis_notes = (
                            f"👤 REVISÃO HUMANA CONCLUÍDA\n"
                            f"Revisor: {review.reviewer_id}\n"
                            f"Decisão: {review.status}\n"
                            f"Notas: {review.review_notes}\n\n"
                            f"---\n\n"
                            f"{report.analysis_notes}"
                        )

                        db.commit()
                        logger.debug(f"💾 Decisão de revisão persistida: {review.id}")

        except Exception as e:
            logger.error(f"❌ Erro ao persistir decisão de revisão: {e}")

    async def _process_feedback(
        self,
        review: HumanReviewRequest,
        feedback: Dict[str, Any]
    ) -> None:
        """
        Processar feedback do revisor para melhorar sistema

        TODO: Implementar aprendizado com feedback (Capítulo 9)
        """
        logger.info(f"📚 Feedback recebido para caso {review.id}")

        # Armazenar feedback para análise posterior
        # Aqui você pode:
        # 1. Ajustar pesos do modelo
        # 2. Atualizar regras clínicas
        # 3. Melhorar critérios de escalação
        # 4. Fine-tune do LLM com casos corrigidos

        feedback_summary = {
            'review_id': review.id,
            'was_correct': feedback.get('analysis_was_correct', False),
            'missed_issues': feedback.get('missed_issues', []),
            'false_positives': feedback.get('false_positives', []),
            'suggestions': feedback.get('suggestions', ''),
            'severity_assessment': feedback.get('severity_assessment', '')
        }

        logger.info(f"💡 Feedback summary: {feedback_summary}")

        # TODO: Armazenar no banco para análise posterior


# Instância global (singleton)
_hitl_agent = None


def get_hitl_agent() -> HumanInTheLoopAgent:
    """Obter instância singleton do HITL agent"""
    global _hitl_agent
    if _hitl_agent is None:
        _hitl_agent = HumanInTheLoopAgent()
    return _hitl_agent
