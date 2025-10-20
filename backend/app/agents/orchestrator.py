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

logger = logging.getLogger(__name__)


class CaptainAgent:
    """Agente orquestrador que coordena todos os outros agentes"""

    def __init__(self):
        """Inicializar o CaptainAgent"""
        self.vision_agent = VisionAgent()
        self.doc_agent = DocAgent()
        self.clinical_agent = ClinicalRulesAgent()

        logger.info("🚢 CaptainAgent inicializado")

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

            # 5. Gerar relatório final
            report = await self._generate_final_report(
                triage_id, vision_result, clinical_analysis, session_id
            )

            logger.info(f"✅ Análise orquestrada concluída: {session_id}")

            return {
                "session_id": session_id,
                "triage_id": str(triage_id),
                "report_id": str(report.id),
                "analysis": clinical_analysis,
                "evidence": evidence_snippets,
                "status": "completed"
            }

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
