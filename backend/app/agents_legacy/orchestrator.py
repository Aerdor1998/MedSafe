"""
CaptainAgent - Agente orquestrador principal do MedSafe
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from ..config import settings
from ..db.models import Triage, Report
from ..db.database import get_db_context
from .vision import VisionAgent
from .docagent import DocAgent
from .clinical import ClinicalRulesAgent
from .safety_guardrails import get_safety_guardrails, GuardrailViolation
from .human_in_the_loop import get_hitl_agent, ReviewStatus
from .reflection_agent import get_reflection_agent, CritiqueLevel

logger = logging.getLogger(__name__)


class CaptainAgent:
    """Agente orquestrador que coordena todos os outros agentes"""

    def __init__(self):
        """Inicializar o CaptainAgent"""
        self.vision_agent = VisionAgent()
        self.doc_agent = DocAgent()
        self.clinical_agent = ClinicalRulesAgent()
        self.safety_guardrails = get_safety_guardrails()
        self.hitl_agent = get_hitl_agent()
        self.reflection_agent = get_reflection_agent()

        logger.info("🚢 CaptainAgent inicializado com Safety Guardrails, HITL e Reflection")

    async def orchestrate_analysis(
        self,
        triage_data: Dict[str, Any],
        image_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Orquestrar análise completa de triagem + visão + evidências

        Args:
            triage_data: Dados da triagem do paciente
            image_data: Dados da imagem/PDF (opcional)

        Returns:
            Relatório completo da análise
        """
        try:
            session_id = str(uuid.uuid4())
            logger.info(f"🎯 Iniciando análise orquestrada: {session_id}")

            # 1. Criar triagem no banco
            triage_id = await self._create_triage(triage_data, session_id)

            # 2. Análise de imagem/PDF se disponível OU usar medication_text diretamente
            vision_result = None
            if image_data:
                # Se há file_path, analisar imagem com VisionAgent
                if image_data.get('file_path'):
                    vision_result = await self._analyze_vision(image_data, session_id)
                # Se não há file_path mas há drug_name/medication_text, usar diretamente
                elif image_data.get('drug_name') or image_data.get('medication_text'):
                    vision_result = {
                        'drug_name': image_data.get('drug_name') or image_data.get('medication_text'),
                        'session_id': session_id,
                        'status': 'text_input'
                    }
                    logger.info(f"📝 Usando medication_text: {vision_result['drug_name']}")

            # 3. Buscar evidências relevantes
            evidence_snippets = await self._gather_evidence(triage_data, vision_result)

            # 4. Análise clínica com regras
            clinical_analysis = await self._apply_clinical_rules(
                triage_data, vision_result, evidence_snippets
            )

            # 4.5. NOVO: Reflexão e refinamento iterativo (Capítulo 4 - Reflection Pattern)
            clinical_analysis, reflection_history = await self._reflect_and_refine(
                clinical_analysis, triage_data, evidence_snippets
            )

            # 5. NOVO: Validar com Safety Guardrails
            try:
                clinical_analysis = await self.safety_guardrails.validate_analysis(
                    clinical_analysis, triage_data
                )
                logger.info(f"🛡️ Guardrails validados - Classificação: {clinical_analysis.get('safety_classification')}")
            except GuardrailViolation as e:
                logger.error(f"🚫 Violação de guardrail crítica: {e}")
                # Bloquear análise e notificar
                return {
                    "session_id": session_id,
                    "triage_id": str(triage_id),
                    "status": "blocked",
                    "error": f"Análise bloqueada por violação de segurança: {e.violation_type}",
                    "message": "Esta análise foi bloqueada por questões de segurança. Consulte um profissional de saúde."
                }

            # 6. NOVO: Avaliar necessidade de revisão humana
            needs_review, escalation_reasons = await self.hitl_agent.evaluate_need_for_human_review(
                clinical_analysis, triage_data, session_id
            )

            # 7. Gerar relatório final
            report = await self._generate_final_report(
                triage_id, vision_result, clinical_analysis, session_id
            )

            # 8. NOVO: Se precisa revisão humana, criar solicitação
            review_request = None
            if needs_review:
                logger.warning(f"⚠️ Análise requer revisão humana: {session_id}")
                review_request = await self.hitl_agent.request_human_review(
                    analysis=clinical_analysis,
                    triage_data=triage_data,
                    triage_id=str(triage_id),
                    session_id=session_id,
                    escalation_reasons=escalation_reasons,
                    report_id=str(report.id)
                )

            logger.info(f"✅ Análise orquestrada concluída: {session_id}")

            result = {
                "session_id": session_id,
                "triage_id": str(triage_id),
                "report_id": str(report.id),
                "analysis": clinical_analysis,
                "evidence": evidence_snippets,
                "status": "pending_review" if needs_review else "completed",
                "requires_human_review": needs_review
            }

            if review_request:
                result["review_request_id"] = review_request.id
                result["review_priority"] = review_request.priority
                result["review_deadline"] = review_request.deadline
                result["escalation_reasons"] = escalation_reasons

            return result

        except Exception as e:
            logger.error(f"❌ Erro na análise orquestrada: {e}")
            raise

    async def _create_triage(
        self,
        triage_data: Dict[str, Any],
        session_id: str
    ) -> str:
        """Criar triagem no banco de dados"""
        try:
            with get_db_context() as db:
                # Gerar UUID como string para compatibilidade com SQLite
                triage_id = str(uuid.uuid4())

                triage = Triage(
                    id=triage_id,
                    user_id=triage_data.get("user_id"),
                    age=triage_data["age"],
                    weight=triage_data.get("weight"),
                    pregnant=triage_data.get("pregnant", False),
                    cid_codes=triage_data.get("cid_codes", []),
                    meds_in_use=triage_data.get("meds_in_use", []),
                    allergies=triage_data.get("allergies", []),
                    renal_function=triage_data.get("renal_function"),
                    hepatic_function=triage_data.get("hepatic_function"),
                    notes=triage_data.get("notes"),
                    status="processing"
                )

                db.add(triage)
                db.commit()
                db.refresh(triage)

                logger.info(f"📋 Triagem criada: {triage.id}")
                return str(triage.id)

        except Exception as e:
            logger.error(f"❌ Erro ao criar triagem: {e}")
            raise

    async def _analyze_vision(
        self,
        image_data: Dict[str, Any],
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Analisar imagem/PDF com VisionAgent"""
        try:
            logger.info(f"👁️ Iniciando análise de visão: {session_id}")

            vision_result = await self.vision_agent.analyze_document(
                image_data, session_id
            )

            logger.info(f"✅ Análise de visão concluída: {session_id}")
            return vision_result

        except Exception as e:
            logger.error(f"❌ Erro na análise de visão: {e}")
            # Não falhar a análise completa se a visão falhar
            return None

    async def _gather_evidence(
        self,
        triage_data: Dict[str, Any],
        vision_result: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Coletar evidências relevantes com DocAgent"""
        try:
            logger.info("🔍 Coletando evidências relevantes")

            # Extrair medicamentos para busca
            medications = []

            # Da triagem
            if triage_data.get("meds_in_use"):
                medications.extend([med.get("name") for med in triage_data["meds_in_use"]])

            # Da visão
            if vision_result and vision_result.get("drug_name"):
                medications.append(vision_result["drug_name"])

            # Buscar evidências para cada medicamento
            evidence_snippets = []
            for med in medications:
                if med:
                    evidence = await self.doc_agent.find_evidence(
                        drug_name=med,
                        sections=["contraindicações", "advertências", "posologia", "interações"]
                    )
                    evidence_snippets.extend(evidence)

            logger.info(f"📚 {len(evidence_snippets)} evidências coletadas")
            return evidence_snippets

        except Exception as e:
            logger.error(f"❌ Erro ao coletar evidências: {e}")
            return []

    async def _apply_clinical_rules(
        self,
        triage_data: Dict[str, Any],
        vision_result: Optional[Dict[str, Any]],
        evidence_snippets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aplicar regras clínicas com ClinicalRulesAgent"""
        try:
            logger.info("🏥 Aplicando regras clínicas")

            clinical_analysis = await self.clinical_agent.analyze_contraindications(
                triage_data=triage_data,
                vision_data=vision_result,
                evidence_snippets=evidence_snippets
            )

            logger.info("✅ Análise clínica concluída")
            return clinical_analysis

        except Exception as e:
            logger.error(f"❌ Erro na análise clínica: {e}")
            raise

    async def _generate_final_report(
        self,
        triage_id: str,
        vision_result: Optional[Dict[str, Any]],
        clinical_analysis: Dict[str, Any],
        session_id: str
    ) -> Report:
        """Gerar relatório final no banco de dados"""
        try:
            with get_db_context() as db:
                # Gerar UUID como string para compatibilidade com SQLite
                report_id = str(uuid.uuid4())

                report = Report(
                    id=report_id,
                    triage_id=triage_id,
                    vision_id=vision_result.get("id") if vision_result else None,
                    risk_level=clinical_analysis["risk_level"],
                    contraindications=clinical_analysis.get("contraindications", []),
                    interactions=clinical_analysis.get("interactions", []),
                    dosage_adjustments=clinical_analysis.get("dosage_adjustments", []),
                    adverse_reactions=clinical_analysis.get("adverse_reactions", []),
                    evidence_links=clinical_analysis.get("evidence_links", []),
                    model_used=clinical_analysis.get("model_used", "qwen2.5:7b"),
                    confidence_score=clinical_analysis.get("confidence_score"),
                    analysis_notes=clinical_analysis.get("analysis_notes"),
                    status="completed",
                    is_final=True
                )

                db.add(report)
                db.commit()
                db.refresh(report)

                # Atualizar status da triagem
                triage = db.query(Triage).filter(Triage.id == triage_id).first()
                if triage:
                    triage.status = "completed"
                    db.commit()

                logger.info(f"📊 Relatório final gerado: {report.id}")
                return report

        except Exception as e:
            logger.error(f"❌ Erro ao gerar relatório final: {e}")
            raise

    async def _reflect_and_refine(
        self,
        clinical_analysis: Dict[str, Any],
        triage_data: Dict[str, Any],
        evidence_snippets: List[Dict[str, Any]]
    ) -> tuple[Dict[str, Any], List]:
        """
        Aplicar Reflection Pattern para refinamento iterativo da análise

        PADRÃO: Reflection (Self-Critique) - Capítulo 4

        Args:
            clinical_analysis: Análise clínica inicial
            triage_data: Dados do paciente
            evidence_snippets: Evidências coletadas

        Returns:
            Tupla (análise_refinada, histórico_de_reflexões)
        """
        try:
            logger.info("🔍 Iniciando reflexão sobre análise clínica")

            # Callback para regeneração de análise com feedback
            async def regenerate_with_feedback(
                current_analysis: Dict[str, Any],
                feedback: Dict[str, Any]
            ) -> Dict[str, Any]:
                """Regenerar análise incorporando feedback da reflexão"""
                logger.info("🔄 Regenerando análise com feedback da reflexão")

                # Criar prompt enriquecido com feedback
                feedback_prompt = self._build_feedback_prompt(feedback)

                # Chamar clinical_agent novamente com contexto de feedback
                # NOTA: Seria ideal ter um método específico no ClinicalAgent
                # para regeneração com feedback, mas por ora reaproveitamos
                # o método existente e confiamos que o LLM considerará o histórico
                regenerated = await self.clinical_agent.analyze_contraindications(
                    triage_data=triage_data,
                    vision_data=None,  # Já temos evidências
                    evidence_snippets=evidence_snippets,
                    reflection_feedback=feedback_prompt  # Novo parâmetro (se suportado)
                )

                return regenerated

            # Executar refinamento iterativo
            refined_analysis, reflection_history = await self.reflection_agent.iterative_refinement(
                initial_analysis=clinical_analysis,
                triage_data=triage_data,
                regeneration_callback=regenerate_with_feedback,
                max_cycles=2  # Limitar a 2 ciclos para performance
            )

            # Log resumo da reflexão
            reflection_summary = self.reflection_agent.get_reflection_summary(reflection_history)
            logger.info(f"✅ Reflexão concluída: {reflection_summary['total_reflections']} reflexões, "
                       f"{reflection_summary['total_issues_found']} issues encontrados")

            # Adicionar metadados de reflexão na análise
            refined_analysis['reflection_metadata'] = {
                'applied': True,
                'cycles': len(reflection_history),
                'summary': reflection_summary,
                'final_critique_level': reflection_history[-1].critique_level.value if reflection_history else 'pass'
            }

            return refined_analysis, reflection_history

        except Exception as e:
            logger.error(f"❌ Erro na reflexão: {e}")
            # Em caso de erro, retornar análise original sem refinamento
            logger.warning("⚠️ Usando análise original sem refinamento")
            return clinical_analysis, []

    def _build_feedback_prompt(self, feedback: Dict[str, Any]) -> str:
        """
        Construir prompt de feedback para regeneração

        Args:
            feedback: Feedback compilado das reflexões

        Returns:
            String de prompt formatada
        """
        prompt = "FEEDBACK DA REVISÃO:\n\n"

        if feedback.get('critical_count', 0) > 0:
            prompt += f"⚠️ {feedback['critical_count']} PROBLEMAS CRÍTICOS encontrados:\n"

        if feedback.get('high_count', 0) > 0:
            prompt += f"⚠️ {feedback['high_count']} problemas de alta severidade encontrados:\n"

        # Listar issues priorizados
        for i, issue in enumerate(feedback.get('issues', [])[:5], 1):  # Top 5 issues
            prompt += f"\n{i}. [{issue.get('severity', 'unknown').upper()}] "
            prompt += f"{issue.get('category', 'general')}: "
            prompt += f"{issue.get('description', 'Sem descrição')}\n"

        # Adicionar sugestões
        if feedback.get('suggestions'):
            prompt += "\nSUGESTÕES DE MELHORIA:\n"
            for i, suggestion in enumerate(feedback.get('suggestions', [])[:3], 1):  # Top 3
                prompt += f"{i}. {suggestion}\n"

        prompt += "\nPor favor, regenere a análise corrigindo esses problemas.\n"

        return prompt

    async def get_analysis_status(self, session_id: str) -> Dict[str, Any]:
        """Verificar status de uma análise"""
        try:
            # Implementar verificação de status
            return {
                "session_id": session_id,
                "status": "completed",  # Placeholder
                "progress": 100
            }
        except Exception as e:
            logger.error(f"❌ Erro ao verificar status: {e}")
            return {"status": "error", "error": str(e)}
