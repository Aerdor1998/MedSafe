"""
ClinicalAgent - Step 3: "Think It Through"

PATTERN: Clinical reasoning with drug interaction analysis (PDF pg 11)
SKILLS: @ultrathink, @debugging-strategies, @api-design-principles

RESPONSIBILITIES:
1. Analyze drug interactions using existing DrugInteractionService
2. Identify contraindications based on patient conditions
3. Calculate overall risk level
4. Generate clinical recommendations
5. Support iterative refinement via Reflection Pattern
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..db.vector_store import MedicalVectorStore, get_vector_store
from ..services.clinical_rules import (
    PatientContext,
    calculate_gfr_cockroft_gault,
    get_rules_engine,
)
from ..services.drug_interactions import get_interaction_service, normalize_drug_name
from .base_agent import BaseAgent
from .state import MedSafeState, RiskLevel

logger = logging.getLogger(__name__)


class ClinicalAgent(BaseAgent):
    """
    ClinicalAgent: Core medical reasoning and drug interaction analysis

    MISSION: "Think It Through" - Apply medical knowledge (PDF pg 11)
    PATTERN: Combines rule-based analysis + LLM reasoning

    SKILLS APPLIED:
    - @ultrathink: Clean integration of rule-based + LLM analysis
    - @debugging-strategies: Comprehensive logging for medical traceability
    - @api-design-principles: Clear separation between analysis stages
    """

    def __init__(self):
        super().__init__(agent_name="ClinicalAgent")
        self.interaction_service = get_interaction_service()
        self.rules_engine = get_rules_engine()
        try:
            self.vector_store: MedicalVectorStore = get_vector_store()
        except Exception as e:
            logger.warning(f"Vector store indisponível: {e}")
            self.vector_store = None

    def get_system_prompt(self) -> str:
        """
        System prompt for ClinicalAgent

        PATTERN: Medical reasoning prompt (PDF pg 39-42)
        """
        return """Você é o ClinicalAgent do MedSafe, um sistema de suporte à decisão médica.

Você é um especialista em farmacologia clínica responsável por:
1. Analisar interações medicamentosas com precisão científica
2. Avaliar a significância clínica das interações
3. Fornecer recomendações baseadas em evidências
4. Considerar fatores específicos do paciente (idade, peso, condições)

Diretrizes:
- Baseie todas as avaliações em evidências farmacológicas
- Considere farmacocinética e farmacodinâmica
- Avalie tanto a gravidade quanto a probabilidade clínica
- Forneça recomendações acionáveis para clínicos
- Sempre erre pelo lado da cautela para segurança do paciente

IMPORTANTE: Todas as suas respostas devem ser em PORTUGUÊS BRASILEIRO.
Traduza termos técnicos quando apropriado, mantendo precisão médica.

Sua análise será revisada por um ReflectionAgent para garantia de qualidade.
Seja minucioso, preciso e baseado em evidências.
"""

    def process(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Perform clinical analysis of drug interactions

        PATTERN: Think → Act → Observe (PDF pg 10-13, step 3)
        RESILIENCE: Continues with partial results even if LLM fails

        Args:
            state: Current MedSafeState

        Returns:
            Dict with clinical analysis results
        """
        start_time = datetime.now()

        # Initialize variables to track partial results
        interactions = []
        contraindications = []
        risk_level = RiskLevel.LOW
        recommendations = {
            "dosage_adjustments": [],
            "adverse_reactions": [],
            "recommendations_text": "",
        }
        llm_failed = False

        # Analysis metadata for observability
        analysis_metadata = {
            "sources_used": [],
            "model_used": getattr(self, "model_name", "unknown"),
            "fallback_triggered": False,
            "evidence_quality": "unknown",
            "cache_hits": {"rag": 0, "openfda": 0},
            "start_time": start_time.isoformat(),
        }

        try:
            # Check if this is a refinement cycle
            is_refinement = state.get("refinement_count", 0) > 0
            feedback = state.get("feedback")

            if is_refinement:
                self.agent_logger.start(
                    f"Iniciando refinamento (ciclo {state['refinement_count']})",
                    feedback_preview=feedback[:100] if feedback else "None",
                )
            else:
                self.agent_logger.start(
                    "Iniciando análise clínica", medication=state["medication_text"]
                )

            # Extract patient info
            patient_data = state["patient_data"]
            medication_text = state["medication_text"]

            # Step 1: Analyze drug interactions (rule-based, doesn't need LLM)
            self.agent_logger.progress(
                "Analisando interações medicamentosas",
                current_medications_count=len(
                    patient_data.get("current_medications", [])
                ),
            )
            interactions, sources_used = self._analyze_interactions(
                medication_text, patient_data
            )
            analysis_metadata["sources_used"] = sources_used

            # Assess evidence quality for low-evidence marker
            evidence_quality = self._assess_evidence_quality(interactions, sources_used)
            analysis_metadata["evidence_quality"] = evidence_quality

            # Step 2: Analyze contraindications (rule-based, doesn't need LLM)
            self.agent_logger.progress(
                "Analisando contraindicações",
                conditions_count=len(patient_data.get("conditions", [])),
                allergies_count=len(patient_data.get("allergies", [])),
            )
            contraindications = self._analyze_contraindications(
                medication_text, patient_data
            )

            # Step 2b: Interações CRÍTICAS com medicamentos em uso são
            # contraindicações de bula (ex: aspirina + varfarina = uso
            # concomitante contraindicado). Deriva entradas para que a
            # seção de contraindicações nunca fique vazia nesses casos.
            contraindications.extend(
                self._derive_interaction_contraindications(
                    interactions, contraindications
                )
            )

            # Step 3: Calculate overall risk (rule-based, doesn't need LLM)
            self.agent_logger.progress("Calculando nível de risco geral")
            risk_level = self._calculate_risk(interactions, contraindications)

            # Step 4: Build patient context for rules engine
            self.agent_logger.progress(
                "Construindo contexto do paciente para regras clinicas"
            )
            patient_ctx = self._build_patient_context(patient_data)

            # Step 5: Check if escalation to HITL is needed
            self.agent_logger.progress("Verificando necessidade de escalonamento HITL")
            (
                needs_escalation,
                escalation_reasons,
            ) = self.rules_engine.check_escalation_needed(
                severity=risk_level.value,
                confidence=0.8,  # Will be calculated later
                interactions=interactions,
                patient_context=patient_ctx,
                drug_name=medication_text,
            )

            # Add low-evidence escalation for high-risk patients
            if evidence_quality in [
                "low",
                "insufficient",
            ] and self._is_high_risk_patient(patient_data):
                if not needs_escalation:
                    needs_escalation = True
                escalation_reasons.append(
                    f"Evidência insuficiente ({evidence_quality}) "
                    "para paciente de alto risco - revisão humana recomendada"
                )
                logger.warning(
                    f"Low-evidence escalation triggered: "
                    f"evidence_quality={evidence_quality}, high_risk_patient=True"
                )

            # Step 5b: Guardrail — medicamento não identificado nas bases.
            # "Nenhuma interação encontrada" para droga desconhecida é
            # falso-negativo perigoso: força revisão humana e aviso visível.
            unidentified = self._find_unidentified_drugs(medication_text)
            if unidentified:
                needs_escalation = True
                nomes = ", ".join(sorted(unidentified))
                escalation_reasons.append(
                    f"Medicamento(s) não identificado(s) nas bases oficiais: "
                    f"{nomes}. A análise de interações pode estar incompleta — "
                    "revisão humana obrigatória."
                )
                logger.warning(
                    f"⚠️ HITL por medicamento não identificado: {nomes}"
                )

            # Step 6: Generate structured recommendations
            self.agent_logger.progress("Gerando recomendacoes estruturadas")
            structured_recs = self.rules_engine.generate_structured_recommendations(
                severity=risk_level.value,
                category=self._get_primary_category(interactions, contraindications),
                interactions=interactions,
                contraindications=contraindications,
                patient_context=patient_ctx,
            )

            # Step 7: Generate clinical recommendations with LLM (enriched)
            self.agent_logger.progress(
                "Gerando recomendacoes clinicas com LLM", risk_level=risk_level.value
            )
            try:
                recommendations = self._generate_recommendations(
                    state, interactions, contraindications, risk_level, feedback
                )
                # Merge da deliberação estruturada do LLM nos achados
                # rule-based (dedup por descrição; LLM nunca rebaixa risco).
                interactions = self._merge_llm_findings(
                    interactions, recommendations.pop("llm_interactions", [])
                )
                contraindications = self._merge_llm_findings(
                    contraindications,
                    recommendations.pop("llm_contraindications", []),
                )
                new_level = self._reconcile_risk(
                    risk_level, recommendations.pop("llm_risk_level", None)
                )
                if new_level != risk_level:
                    risk_level = new_level
                    if not needs_escalation and risk_level in (
                        RiskLevel.HIGH,
                        RiskLevel.CRITICAL,
                    ):
                        needs_escalation = True
                        escalation_reasons.append(
                            "Risco elevado identificado na deliberação "
                            "clínica do LLM"
                        )
                # Merge structured recommendations
                recommendations["structured"] = structured_recs
                recommendations["escalation_needed"] = needs_escalation
                recommendations["escalation_reasons"] = escalation_reasons
            except Exception as llm_error:
                llm_failed = True
                analysis_metadata["fallback_triggered"] = True
                self.agent_logger.error(
                    f"LLM falhou ao gerar recomendacoes: {llm_error}"
                )
                logger.warning(
                    f"LLM failed, using fallback recommendations: {llm_error}"
                )
                # Generate fallback recommendations based on risk level
                recommendations = self._generate_fallback_recommendations(
                    interactions, contraindications, risk_level
                )
                recommendations["structured"] = structured_recs
                recommendations["escalation_needed"] = needs_escalation
                recommendations["escalation_reasons"] = escalation_reasons

        except Exception as e:
            self.agent_logger.error("Falha na análise clínica", exc_info=True)
            logger.error(f"ClinicalAgent critical error: {e}")
            # Even on critical error, try to preserve any partial results
            # The error will be logged but we'll return what we have

        # Step 5: Calculate confidence score (doesn't need LLM)
        try:
            self.agent_logger.progress("Calculando score de confiança")
            confidence = self._calculate_confidence(
                interactions, contraindications, state
            )
            # Reduce confidence if LLM failed
            if llm_failed:
                confidence = max(0.3, confidence * 0.7)  # Reduce by 30% but min 0.3
        except Exception:
            confidence = 0.5 if interactions or contraindications else 0.3

        # Prepare state updates - ALWAYS return interactions/contraindications if found
        # Include escalation info from rules engine
        escalation_needed = recommendations.get("escalation_needed", False)
        escalation_reasons_list = recommendations.get("escalation_reasons", [])

        # Finalize analysis metadata
        analysis_metadata["end_time"] = datetime.now().isoformat()
        analysis_metadata["processing_time_ms"] = int(
            (datetime.now() - start_time).total_seconds() * 1000
        )

        updates = {
            "interactions": interactions,
            "contraindications": contraindications,
            "risk_level": risk_level,
            "confidence_score": confidence,
            "risk_score": self._score_from_level(
                risk_level, recommendations.get("risk_score")
            ),
            "patient_risk_factors": self._patient_risk_factors(
                state.get("patient_data") or {}
            ),
            "dosage_adjustments": recommendations.get("dosage_adjustments", []),
            "adverse_reactions": recommendations.get("adverse_reactions", []),
            "status": "analyzed" if not llm_failed else "analyzed_partial",
            # New structured recommendations
            "structured_recommendations": recommendations.get("structured", {}),
            # Escalation info for SafetyAgent/HITL
            "requires_human_review": escalation_needed,
            "escalation_reasons": escalation_reasons_list,
            # Observability metadata
            "analysis_metadata": analysis_metadata,
        }

        # Note: refinement_count is now managed in graph.py reflection_node
        # to ensure proper increment before re-entering clinical analysis

        # Update timestamps - ensure timestamps dict exists in updates
        if "timestamps" not in updates:
            updates["timestamps"] = state.get("timestamps", {}).copy()
        updates["timestamps"]["clinical_analysis_end"] = datetime.now()

        # Log results
        self.agent_logger.end(
            "Análise clínica concluída"
            + (" (parcial - LLM falhou)" if llm_failed else ""),
            success=not llm_failed,
            risk_level=risk_level.value,
            interactions_count=len(interactions),
            contraindications_count=len(contraindications),
            confidence=confidence,
        )

        return updates

    def _assess_evidence_quality(
        self, interactions: List[Dict[str, Any]], sources_used: List[str]
    ) -> str:
        """
        Assess quality of evidence for interactions.

        PATTERN: Evidence quality assessment for low-evidence marker
        SKILL: @debugging-strategies - Quality gates for clinical decisions

        Returns:
            str: "sufficient", "rules_only", "no_csv_match", "low", or "insufficient"
        """
        if not interactions:
            return "insufficient"

        # Check if we have diverse sources
        has_csv = "csv" in sources_used
        has_rag = "rag" in sources_used
        has_openfda = "openfda" in sources_used
        has_rules = "clinical_rules" in sources_used

        # Best case: multiple authoritative sources
        if has_csv and (has_rag or has_openfda):
            return "sufficient"

        # Good case: CSV match (most reliable)
        if has_csv:
            return "sufficient"

        # Moderate case: RAG or OpenFDA only
        if has_rag or has_openfda:
            return "moderate"

        # Limited case: only clinical rules (heuristics)
        if has_rules and not has_csv and not has_rag and not has_openfda:
            return "rules_only"

        # Low evidence
        return "low"

    def _is_high_risk_patient(self, patient_data: Dict[str, Any]) -> bool:
        """
        Determine if patient is high-risk (requires more careful review).

        PATTERN: Risk stratification for evidence-based escalation
        SKILL: @ultrathink - Patient safety first

        Returns:
            bool: True if patient is considered high-risk
        """
        # Age-based risk
        age = patient_data.get("age", 0)
        if age >= 75 or age <= 2:
            return True

        # Pregnancy
        if patient_data.get("pregnant"):
            return True

        # Renal/hepatic impairment
        if patient_data.get("renal_function") in ["severe", "dialysis"]:
            return True
        if patient_data.get("hepatic_function") in ["severe", "cirrhosis"]:
            return True

        # Multiple conditions (polypharmacy risk)
        conditions = patient_data.get("conditions", [])
        if len(conditions) >= 3:
            return True

        # Multiple medications (interaction risk)
        meds = patient_data.get("current_medications", []) or patient_data.get(
            "meds_in_use", []
        )
        if len(meds) >= 5:
            return True

        return False

    def _canonical_dedup_name(self, name: str) -> str:
        """
        Nome canônico para dedup: PT/EN/marcas colapsam no mesmo identificador
        ('varfarina', 'Marevan' e 'warfarin' → 'warfarin'). Usa a normalização
        canônica do DrugInteractionService com fallback textual simples.
        """
        try:
            canonical = self.interaction_service._normalize_drug_name(name)
            # Type-check defensivo: se o serviço retornar algo que não é
            # string não-vazia (mock em testes, None, objeto inesperado),
            # cai no fallback textual em vez de propagar lixo para a chave
            # de dedup (sorted() em não-strings levanta TypeError).
            if isinstance(canonical, str) and canonical.strip():
                return canonical.lower().strip()
        except Exception:
            pass
        return normalize_drug_name(name or "").lower()

    def _deduplicate_interactions(
        self, interactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate interactions with canonical key and source merge.

        PATTERN: Canonical deduplication with source aggregation
        SKILL: @python-performance-optimization - Efficient dedup with merge

        Key formula: (canonical_drug1, canonical_drug2) — apenas o par
        ordenado. REGRESSÃO CORRIGIDA: a chave antiga incluía o prefixo de
        description/mechanism; como cada fonte descreve o mesmo par com texto
        diferente, o merge "maior severidade por par" nunca acontecia e o
        laudo mostrava a mesma interação duplicada (ex: varfarina+aspirina
        "low" do CSV ao lado do "critical" das regras clínicas).
        - Drug names são canonizados (PT/EN/marcas → mesma chave) e ordenados
        - Sources são fundidas de todas as duplicatas
        - A entrada de maior severidade define severity/description/mechanism

        Returns:
            List of deduplicated interactions with merged sources
        """
        if not interactions:
            return []

        SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}
        seen: Dict[tuple, Dict[str, Any]] = {}

        for item in interactions:
            # Canonical drug names (PT/EN/brands collapse to the same key)
            drug1 = self._canonical_dedup_name(item.get("drug1", ""))
            drug2 = self._canonical_dedup_name(item.get("drug2", ""))

            # Canonical key: sorted pair only (no mechanism prefix)
            drugs = tuple(sorted([drug1, drug2]))
            key = drugs

            if key in seen:
                existing = seen[key]

                # Merge: a entrada mais severa define o conteúdo clínico
                existing_sev = SEVERITY_ORDER.get(
                    existing.get("severity", "unknown"), 0
                )
                new_sev = SEVERITY_ORDER.get(item.get("severity", "unknown"), 0)
                if new_sev > existing_sev:
                    for field in (
                        "severity",
                        "description",
                        "mechanism",
                        "recommendation",
                        "source",
                    ):
                        if item.get(field) is not None:
                            existing[field] = item[field]

                # Merge sources
                new_source = item.get("source", "unknown")
                if "sources" not in existing:
                    existing["sources"] = [existing.get("source", "unknown")]
                if new_source not in existing["sources"]:
                    existing["sources"].append(new_source)

                # Log merge
                logger.debug(
                    f"Merged duplicate: {drugs} (sources: {existing['sources']})"
                )
            else:
                # Initialize sources list
                item["sources"] = [item.get("source", "unknown")]
                seen[key] = item

        deduped = list(seen.values())
        removed = len(interactions) - len(deduped)

        if removed > 0:
            logger.info(
                f"Dedup removed {removed} duplicate interactions (merged sources)"
            )

        return deduped

    def _analyze_interactions(
        self, medication_text: str, patient_data: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Analyze drug interactions using DrugInteractionService

        SKILL: @api-design-principles - Reusing existing service

        Returns:
            Tuple of (interactions, sources_used)
        """
        # LGPD/PHI: avoid logging medication names in plaintext
        logger.info(
            "Analyzing interactions (medication_text_len=%d)",
            len(medication_text or ""),
        )
        sources_used = []

        current_medications = patient_data.get("current_medications", [])

        # Split medication_text if it's comma-separated (legacy format)
        medications_to_check = [
            m.strip() for m in medication_text.split(",") if m.strip()
        ]
        if len(medications_to_check) <= 1:
            medications_to_check = [medication_text]

        # ROOT CAUSE FIX: interações também devem ser checadas ENTRE os
        # medicamentos da própria prescrição (ex: "varfarina, aspirina" no
        # mesmo campo), não apenas contra current_medications. Antes, sem
        # current_medications havia early-return e o par crítico
        # varfarina+aspirina passava despercebido (risco "low").
        def _others_for(drug: str) -> List[str]:
            peers = [m for m in medications_to_check if m != drug]
            return list(current_medications) + peers

        if not current_medications and len(medications_to_check) <= 1:
            logger.info(
                "   Single medication and no current medications - "
                "no interactions to check"
            )
            return [], sources_used

        logger.info(
            "   Checking %d medications against %d current meds (+ pairwise)",
            len(medications_to_check),
            len(current_medications),
        )

        interactions: List[Dict[str, Any]] = []

        # 1) CSV local (rápido) - check each medication
        for drug in medications_to_check:
            csv_interactions = self.interaction_service.find_interactions(
                drug_name=drug, other_drugs=_others_for(drug)
            )
            if csv_interactions:
                for i in csv_interactions:
                    i["source"] = "csv"
                interactions.extend(csv_interactions)
                if "csv" not in sources_used:
                    sources_used.append("csv")

        # 2) RAG / Vector Store (evidências científicas)
        if self.vector_store:
            logger.info("Searching RAG for evidence...")
            rag_evidence = self._get_rag_evidence(medication_text, current_medications)
            if rag_evidence:
                logger.info(f"RAG found {len(rag_evidence)} evidence items")
                interactions.extend(rag_evidence)
                if "rag" not in sources_used:
                    sources_used.append("rag")

        # 3) OpenFDA (external validation)
        # Note: OpenFDA is async, we run it in a thread to avoid event loop issues
        openfda_results = self._run_openfda_sync(medication_text, current_medications)
        if openfda_results:
            logger.info(f"OpenFDA found {len(openfda_results)} interactions")
            for i in openfda_results:
                i["source"] = "openfda"
            interactions.extend(openfda_results)
            if "openfda" not in sources_used:
                sources_used.append("openfda")

        # 4) Regras clínicas determinísticas - SEMPRE executam.
        # ROOT CAUSE FIX: antes rodavam apenas quando nenhuma outra fonte
        # retornava resultados; evidência fraca de RAG/OpenFDA suprimia
        # pares críticos conhecidos (ex: varfarina+aspirina → risco "low").
        # A deduplicação abaixo preserva a maior severidade por par.
        try:
            rule_results: List[Dict[str, Any]] = []
            for drug in medications_to_check:
                rule_results.extend(
                    self.interaction_service._check_known_clinical_rules(
                        drug_name=drug, other_drugs=_others_for(drug)
                    )
                )
            if rule_results:
                logger.info(
                    f"Clinical rules found {len(rule_results)} interactions"
                )
                for i in rule_results:
                    i["source"] = "clinical_rules"
                interactions.extend(rule_results)
                if "clinical_rules" not in sources_used:
                    sources_used.append("clinical_rules")
        except Exception as e:
            logger.warning(f"Regras clínicas determinísticas falharam: {e}")

        # Deduplicar com canonical key e merge de fontes
        interactions = self._deduplicate_interactions(interactions)

        logger.info(
            f"   Found {len(interactions)} interactions from sources: {sources_used}"
        )

        return interactions, sources_used

    def _run_openfda_sync(
        self, medication_text: str, current_medications: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Run OpenFDA query synchronously from sync context.

        Uses asyncio.run() which creates a new event loop, avoiding
        the nest_asyncio hack that was causing issues.
        """
        try:
            from ..services.openfda_service import OpenFDAService

            async def _fetch():
                service = OpenFDAService()
                results = []
                for other_drug in current_medications[
                    :5
                ]:  # Limit to 5 to avoid rate limits
                    try:
                        interaction = await service.check_interaction(
                            medication_text, other_drug
                        )
                        if interaction:
                            results.append(interaction)
                    except Exception as e:
                        # Avoid logging PHI in plaintext; keep only error type
                        logger.debug(
                            "OpenFDA check failed for drug pair: %s", type(e).__name__
                        )
                return results

            # Run in new event loop (safe from sync context)
            return asyncio.run(_fetch())
        except Exception as e:
            logger.warning(f"OpenFDA sync wrapper failed: {e}")
            return []

    def _get_rag_evidence(
        self, drug_name: str, other_drugs: List[str]
    ) -> List[Dict[str, Any]]:
        """Busca evidências no vector store e converte em interações"""
        if not self.vector_store:
            return []

        query = f"drug interaction between {drug_name} and {', '.join(other_drugs)}"
        try:
            evidence_docs = self.vector_store.hybrid_search(
                query=query, k=5, semantic_weight=0.7
            )
        except Exception as e:
            logger.warning(f"Falha ao buscar evidências RAG: {e}")
            return []

        # ANTI-FANTASMA: âncora de nomes do caso (bruto + canônico EN).
        # A busca é SEMÂNTICA: para nomes desconhecidos (ex: "Blorfazina"),
        # ela retorna o vizinho mais próximo do corpus (Flunarizine×
        # Valsartan) e isso virava "interação" real no laudo. Evidência RAG
        # só é aceita se o documento mencionar explicitamente algum
        # medicamento do caso.
        case_names: set = set()
        for raw in [drug_name, *other_drugs]:
            if not raw or not str(raw).strip():
                continue
            case_names.add(str(raw).lower().strip())
            try:
                case_names.add(normalize_drug_name(raw).lower().strip())
            except Exception:  # pragma: no cover - resiliência
                pass
        anchors = {n for n in case_names if len(n) >= 4}

        interactions = []
        for doc in evidence_docs:
            metadata = doc.get("metadata", {})
            doc_text = (
                f"{doc.get('content', '')} {metadata.get('drug_name', '')}"
            ).lower()
            if anchors and not any(n in doc_text for n in anchors):
                logger.debug(
                    "Evidência RAG descartada (não menciona medicamentos do caso)"
                )
                continue
            # FIX (ruído): sem droga parceira identificável (metadata sem
            # drug_name e paciente sem medicamentos em uso), o item virava
            # uma "interação" com drug2 vazio no frontend. Evidência RAG
            # sem par identificado não é interação — pular.
            partner = metadata.get("drug_name") or ", ".join(other_drugs)
            if not partner:
                continue
            interactions.append(
                {
                    "drug1": drug_name,
                    "drug2": partner,
                    "description": doc.get("content", ""),
                    "severity": metadata.get("severity", "medium"),
                    "category": metadata.get("section", "RAG"),
                    "source": metadata.get("source", "vector_store"),
                }
            )

        return interactions

    def _analyze_contraindications(
        self, medication_text: str, patient_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Analyze contraindications based on patient conditions

        SKILL: @debugging-strategies - Comprehensive condition checking
        """
        # LGPD/PHI: avoid logging medication names in plaintext
        logger.info(
            "Analyzing contraindications (medication_text_len=%d)",
            len(medication_text or ""),
        )

        conditions = patient_data.get("conditions", [])
        allergies = patient_data.get("allergies", [])
        pregnant = bool(patient_data.get("pregnant"))

        # ROOT CAUSE FIX: dividir texto separado por vírgula antes de
        # consultar o identificador de drogas. Antes, a string combinada
        # inteira (ex: "varfarina, aspirina") era enviada como um único
        # nome e falhava a identificação ("Medicamento não identificado").
        drugs_to_check = [
            m.strip() for m in medication_text.split(",") if m.strip()
        ]
        if len(drugs_to_check) <= 1:
            drugs_to_check = [medication_text]

        # Use existing DrugInteractionService (por medicamento individual)
        contraindications: List[Dict[str, Any]] = []
        seen: set = set()
        for drug in drugs_to_check:
            for c in self.interaction_service.analyze_contraindications(
                drug_name=drug,
                patient_conditions=conditions,
                allergies=allergies,
                pregnant=pregnant,
            ):
                key = (c.get("type", ""), c.get("description", ""))
                if key in seen:
                    continue
                seen.add(key)
                contraindications.append(c)

        logger.info(f"   Found {len(contraindications)} contraindications")

        return contraindications

    def _derive_interaction_contraindications(
        self,
        interactions: List[Dict[str, Any]],
        existing: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Interações CRÍTICAS com medicamentos em uso são contraindicações
        de bula (ex: aspirina é contraindicada em uso concomitante com
        anticoagulantes). Deriva entradas de contraindicação a partir
        das interações críticas já identificadas, sem duplicar.
        """
        derived: List[Dict[str, Any]] = []
        seen = {
            (c.get("type", ""), c.get("description", "")) for c in existing
        }
        for interaction in interactions:
            if str(interaction.get("severity", "")).lower() != "critical":
                continue
            drug1 = interaction.get("drug1") or "medicamento analisado"
            drug2 = interaction.get("drug2") or "medicamento em uso"
            entry = {
                "type": "Uso Concomitante Contraindicado",
                "description": (
                    f"Uso concomitante de {drug1} com {drug2} é "
                    f"contraindicado: interação crítica identificada"
                ),
                "severity": "critical",
                "source": interaction.get("source", "Base de Interações"),
                "recommendation": interaction.get(
                    "recommendation",
                    "CONTRAINDICADO - Evitar combinação; "
                    "consultar prescritor",
                ),
            }
            key = (entry["type"], entry["description"])
            if key not in seen:
                seen.add(key)
                derived.append(entry)

        if derived:
            logger.info(
                "   Derived %d contraindication(s) from critical "
                "interactions",
                len(derived),
            )
        return derived

    def _find_unidentified_drugs(self, medication_text: str) -> List[str]:
        """Nomes da prescrição que o identificador híbrido NÃO resolveu.

        Uma análise "sem interações" para droga desconhecida é um
        falso-negativo perigoso — o chamador deve escalar para HITL.
        """
        import re as _re

        try:
            from ..services.drug_identifier import IdentificationMethod

            identifier = get_interaction_service().drug_identifier
            names = [
                n.strip()
                for n in _re.split(r"[,;+\n]", medication_text or "")
                if n.strip()
            ]
            return [
                n
                for n in names
                if identifier.identify(n).method == IdentificationMethod.NOT_FOUND
            ]
        except Exception as exc:  # guardrail nunca derruba a análise
            logger.warning(f"Guardrail de identificação falhou: {exc}")
            return []

    def _calculate_risk(
        self,
        interactions: List[Dict[str, Any]],
        contraindications: List[Dict[str, Any]],
    ) -> RiskLevel:
        """
        Calculate overall risk level

        SKILL: @ultrathink - Delegating to existing service logic
        """
        # Use existing DrugInteractionService logic
        risk_str = self.interaction_service.calculate_overall_risk(
            interactions, contraindications
        )

        # Convert string to RiskLevel enum
        risk_map = {
            "critical": RiskLevel.CRITICAL,
            "high": RiskLevel.HIGH,
            "medium": RiskLevel.MEDIUM,
            "low": RiskLevel.LOW,
        }

        return risk_map.get(risk_str, RiskLevel.LOW)

    def _generate_recommendations(
        self,
        state: MedSafeState,
        interactions: List[Dict[str, Any]],
        contraindications: List[Dict[str, Any]],
        risk_level: RiskLevel,
        feedback: str = None,
    ) -> Dict[str, Any]:
        """
        Generate clinical recommendations using LLM

        PATTERN: LLM for synthesis and clinical reasoning
        SKILL: @ultrathink - Combining structured data + LLM reasoning
        """
        # Build context
        patient_data = state["patient_data"]
        medication = state["medication_text"]

        # Anamnese COMPLETA no contexto do LLM — sem ela o modelo não tem
        # como deliberar sobre gravidez, condições e medicamentos em uso.
        context = {
            "Medicamento avaliado": medication,
            "Idade": patient_data.get("age", "não informado"),
            "Peso (kg)": patient_data.get("weight_kg")
            or patient_data.get("weight", "não informado"),
            "Gestante": (
                "sim"
                if patient_data.get("pregnant")
                or patient_data.get("is_pregnant")
                else "não/não informado"
            ),
            "Condições clínicas": ", ".join(patient_data.get("conditions") or [])
            or "nenhuma informada",
            "Alergias": ", ".join(patient_data.get("allergies") or [])
            or "nenhuma informada",
            "Medicamentos em uso": ", ".join(
                patient_data.get("current_medications") or []
            )
            or "nenhum informado",
            "Risco preliminar (rule-based)": risk_level.value,
        }

        # Summarize interactions - with Portuguese severity labels
        severity_pt = {
            "critical": "CRÍTICO",
            "high": "ALTO",
            "medium": "MÉDIO",
            "low": "BAIXO",
        }
        interactions_summary = (
            "\n".join(
                [
                    f"- {i['drug1']} + {i['drug2']}: "
                    f"{severity_pt.get(i['severity'].lower(), i['severity'].upper())} - {i['description'][:150]}"
                    for i in interactions[:5]  # Top 5
                ]
            )
            if interactions
            else "Nenhuma interação identificada"
        )

        # Summarize contraindications
        contraindications_summary = (
            "\n".join(
                [
                    f"- {c['type']}: "
                    f"{severity_pt.get(c['severity'].lower(), c['severity'].upper())} - {c['description'][:150]}"
                    for c in contraindications[:5]  # Top 5
                ]
            )
            if contraindications
            else "Nenhuma contraindicação identificada"
        )

        # Deliberação estruturada: anamnese + achados rule-based → JSON estrito
        prompt = f"""Faça a análise de segurança medicamentosa COMPLETA do caso
descrito na seção CONTEXT (anamnese do paciente e medicamento avaliado).

**Achados das bases de dados (rule-based) — interações:**
{interactions_summary}

**Achados das bases de dados (rule-based) — contraindicações:**
{contraindications_summary}

**Nível de risco preliminar (rule-based):** {risk_level.value.upper()}

DELIBERE clinicamente considerando TODOS os dados da anamnese (idade, peso,
gravidez, condições clínicas, alergias e medicamentos em uso). Complete o que
as bases de dados não cobriram — inclusive contraindicações e interações que
você identificar além das listadas acima.

Responda SOMENTE com um objeto JSON válido (sem markdown, sem texto fora do JSON), neste formato exato:
{{
  "risk_level": "low|medium|high|critical",
  "risk_score": 0,
  "rationale": "raciocínio clínico resumido",
  "contraindications": [{{"type": "absoluta|relativa", "description": "...", "severity": "low|medium|high|critical"}}],
  "interactions": [{{"drug1": "...", "drug2": "...", "severity": "low|medium|high|critical", "description": "..."}}],
  "adverse_reactions": [{{"description": "...", "severity": "low|medium|high|critical"}}],
  "dosage_adjustments": [{{"recommendation": "..."}}]
}}

Regras:
- Tudo em PORTUGUÊS BRASILEIRO.
- "risk_score" é um inteiro de 0 a 100 coerente com "risk_level".
- Liste apenas achados clinicamente relevantes para ESTE paciente; listas vazias ([]) são válidas.
- Não invente fontes; na dúvida, seja conservador em favor da segurança do paciente."""

        # Add feedback if refinement cycle
        if feedback:
            prompt += f"\n\n**Feedback de Reflexão:**\n{feedback}\n\nAborde o feedback nas suas recomendações."

        # Invoke LLM — deliberação estruturada (JSON) com retry único limitado
        raw = self.invoke_llm(prompt, context=context)
        data = self._parse_llm_json(raw)
        if data is None:
            self.agent_logger.progress(
                "Resposta do LLM não era JSON válido — retry único"
            )
            raw_retry = self.invoke_llm(
                prompt
                + "\n\nATENÇÃO: a resposta anterior não era JSON válido. "
                "Responda SOMENTE o objeto JSON.",
                context=context,
            )
            data = self._parse_llm_json(raw_retry)
            if data is not None:
                raw = raw_retry

        if data is None:
            # Fallback: extração por keywords do texto livre (comportamento
            # antigo), agora filtrando cabeçalhos markdown.
            logger.warning(
                "Deliberação estruturada falhou (JSON inválido 2x); "
                "usando extração por texto"
            )
            return {
                "dosage_adjustments": self._extract_dosage_adjustments(raw),
                "adverse_reactions": self._extract_adverse_reactions(raw),
                "recommendations_text": raw,
            }

        return self._normalize_deliberation(data, medication, raw)

    def _generate_fallback_recommendations(
        self,
        interactions: List[Dict[str, Any]],
        contraindications: List[Dict[str, Any]],
        risk_level: RiskLevel,
    ) -> Dict[str, Any]:
        """
        Generate fallback recommendations when LLM is unavailable

        PATTERN: Graceful degradation - rule-based fallback
        SKILL: @debugging-strategies - Resilient error handling
        """
        dosage_adjustments = []
        adverse_reactions = []
        recommendations_parts = []

        # Generate recommendations based on risk level
        if risk_level == RiskLevel.CRITICAL:
            recommendations_parts.append(
                "RISCO CRITICO IDENTIFICADO - Revisao medica obrigatoria antes de administrar."
            )
            dosage_adjustments.append(
                {
                    "recommendation": "NAO ADMINISTRAR sem avaliacao medica especializada",
                    "source": "ClinicalAgent-Fallback",
                }
            )
        elif risk_level == RiskLevel.HIGH:
            recommendations_parts.append(
                "Risco alto detectado - Considerar alternativas terapeuticas."
            )
            dosage_adjustments.append(
                {
                    "recommendation": "Avaliar redução de dose ou alternativa terapêutica",
                    "source": "ClinicalAgent-Fallback",
                }
            )

        # Generate recommendations from interactions
        for interaction in interactions[:5]:  # Top 5
            severity = interaction.get("severity", "unknown").upper()
            drug1 = interaction.get("drug1", "?")
            drug2 = interaction.get("drug2", "?")
            description = interaction.get("description", "")[:200]

            adverse_reactions.append(
                {
                    "description": f"Interação {severity}: {drug1} + {drug2} - {description}",
                    "source": "ClinicalAgent-Fallback",
                }
            )

            if severity in ["CRITICAL", "MAJOR", "SEVERE"]:
                recommendations_parts.append(
                    f"[ALERTA] Interacao {severity} entre {drug1} e {drug2}: {description}"
                )

        # Generate recommendations from contraindications
        for contraind in contraindications[:3]:  # Top 3
            c_type = contraind.get("type", "")
            c_desc = contraind.get("description", "")[:150]
            recommendations_parts.append(
                f"[ATENCAO] Contraindicacao ({c_type}): {c_desc}"
            )

        # Default message if no specific findings
        if not recommendations_parts:
            if interactions or contraindications:
                recommendations_parts.append(
                    "Interações e/ou contraindicações identificadas. Consulte os detalhes acima."
                )
            else:
                recommendations_parts.append(
                    "Nenhuma interação crítica identificada na base de dados. "
                    "Recomenda-se sempre consultar um profissional de saúde."
                )

        return {
            "dosage_adjustments": dosage_adjustments,
            "adverse_reactions": adverse_reactions,
            "recommendations_text": "\n\n".join(recommendations_parts),
        }

    def _extract_dosage_adjustments(self, text: str) -> List[Dict[str, Any]]:
        """Extract dosage adjustments from LLM response (PT/EN)"""
        adjustments = []

        # Keywords in Portuguese and English
        dosage_keywords = [
            "dose",
            "dosage",
            "reduce",
            "increase",
            "adjust",
            "dosagem",
            "reduzir",
            "aumentar",
            "ajustar",
            "mg",
            "ml",
            "intervalo",
            "administração",
            "posologia",
        ]

        for line in text.split("\n"):
            stripped = line.strip().lstrip("-•*#").strip()
            # Cabeçalhos markdown ("1. **Ajustes de Dosagem:**") não são itens
            if re.match(r"^(\d+\.\s*)?\*\*[^*]+\*\*:?\s*$", stripped):
                continue
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in dosage_keywords):
                cleaned = line.strip().lstrip("-•*")
                if cleaned and len(cleaned) > 10:
                    adjustments.append(
                        {
                            "recommendation": cleaned.strip(),
                            "source": "ClinicalAgent-LLM",
                        }
                    )

        return adjustments[:5]  # Top 5

    def _extract_adverse_reactions(self, text: str) -> List[Dict[str, Any]]:
        """Extract adverse reactions from LLM response (PT/EN)"""
        reactions = []

        # Keywords in Portuguese and English
        reaction_keywords = [
            "monitor",
            "watch",
            "side effect",
            "adverse",
            "reaction",
            "monitorar",
            "vigilar",
            "efeito",
            "reação",
            "sintoma",
            "alerta",
            "observar",
            "atenção",
            "risco",
        ]

        for line in text.split("\n"):
            stripped = line.strip().lstrip("-•*#").strip()
            # Cabeçalhos markdown ("2. **Reações Adversas:**") não são itens
            if re.match(r"^(\d+\.\s*)?\*\*[^*]+\*\*:?\s*$", stripped):
                continue
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in reaction_keywords):
                cleaned = line.strip().lstrip("-•*")
                if cleaned and len(cleaned) > 10:
                    reactions.append(
                        {"description": cleaned.strip(), "source": "ClinicalAgent-LLM"}
                    )

        return reactions[:7]  # Top 7

    @staticmethod
    def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
        """Extrai o primeiro objeto JSON da resposta do LLM (tolerante a fences)."""
        if not text:
            return None
        cleaned = re.sub(r"```(?:json)?", "", text)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            return None
        candidate = cleaned[start : end + 1]
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            # Remove vírgulas penduradas comuns em saída de LLM e tenta de novo
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", candidate))
            except json.JSONDecodeError:
                return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _merge_llm_findings(
        base: List[Dict[str, Any]],
        extra: List[Dict[str, Any]],
        key: str = "description",
    ) -> List[Dict[str, Any]]:
        """Anexa achados do LLM sem duplicar os rule-based (dedup por descrição)."""

        def _sig(item: Dict[str, Any]) -> str:
            return re.sub(r"\W+", " ", str(item.get(key, ""))).strip().lower()[:80]

        seen = {_sig(b) for b in base}
        merged = list(base)
        for item in extra:
            s = _sig(item)
            if s and s not in seen:
                seen.add(s)
                merged.append(item)
        return merged

    _RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

    def _reconcile_risk(
        self, rule_level: RiskLevel, llm_level: Optional[str]
    ) -> RiskLevel:
        """LLM só pode ELEVAR o risco rule-based, nunca rebaixar (cautela)."""
        risk_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }
        llm = risk_map.get(str(llm_level or "").strip().lower())
        if llm is None:
            return rule_level
        if self._RISK_ORDER[llm.value] > self._RISK_ORDER[rule_level.value]:
            return llm
        return rule_level

    # Bandas de score por nível: (mínimo, máximo, default sem score do LLM)
    _SCORE_BANDS = {
        "low": (5, 39, 20),
        "medium": (40, 59, 50),
        "high": (60, 79, 70),
        "critical": (80, 100, 90),
    }

    def _score_from_level(
        self, level: RiskLevel, llm_score: Optional[int] = None
    ) -> int:
        """Score numérico coerente com o nível (clampa o score do LLM na banda)."""
        lo, hi, default = self._SCORE_BANDS[level.value]
        if llm_score is None:
            return default
        return max(lo, min(hi, llm_score))

    @staticmethod
    def _patient_risk_factors(patient_data: Dict[str, Any]) -> List[str]:
        """Fatores de risco derivados diretamente da anamnese (para a UI)."""
        factors: List[str] = []
        age = patient_data.get("age")
        if isinstance(age, (int, float)):
            if age >= 65:
                factors.append(f"Idade avançada ({int(age)} anos)")
            elif age < 18:
                factors.append(f"Paciente pediátrico ({int(age)} anos)")
        if patient_data.get("pregnant") or patient_data.get("is_pregnant"):
            factors.append("Gestante")
        for cond in patient_data.get("conditions") or []:
            factors.append(f"Condição: {cond}")
        meds = patient_data.get("current_medications") or []
        if len(meds) >= 3:
            factors.append(f"Polifarmácia ({len(meds)} medicamentos em uso)")
        return factors

    def _normalize_deliberation(
        self, data: Dict[str, Any], medication: str, raw: str
    ) -> Dict[str, Any]:
        """Valida/normaliza o JSON de deliberação do LLM para o shape do state."""
        sev_ok = {"low", "medium", "high", "critical"}

        def _norm_sev(value: Any, default: str = "medium") -> str:
            v = str(value or "").strip().lower()
            return v if v in sev_ok else default

        def _items(key: str, limit: int) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for item in data.get(key) or []:
                if isinstance(item, str):
                    item = {"description": item}
                if isinstance(item, dict):
                    out.append(item)
                if len(out) >= limit:
                    break
            return out

        contraindications = []
        for c in _items("contraindications", 10):
            desc = str(c.get("description") or c.get("reason") or "").strip()
            if desc:
                contraindications.append(
                    {
                        "type": str(c.get("type") or "Contraindicação").strip(),
                        "description": desc,
                        "severity": _norm_sev(c.get("severity"), "high"),
                        "source": "ClinicalAgent-LLM",
                    }
                )

        interactions = []
        for i in _items("interactions", 10):
            desc = str(i.get("description") or "").strip()
            if desc:
                interactions.append(
                    {
                        "drug1": str(i.get("drug1") or medication).strip(),
                        "drug2": str(i.get("drug2") or "medicamento em uso").strip(),
                        "severity": _norm_sev(i.get("severity")),
                        "description": desc,
                        "source": "ClinicalAgent-LLM",
                    }
                )

        adverse_reactions = []
        for r in _items("adverse_reactions", 10):
            desc = str(r.get("description") or "").strip()
            if desc:
                adverse_reactions.append(
                    {
                        "description": desc,
                        "severity": _norm_sev(r.get("severity"), "low"),
                        "source": "ClinicalAgent-LLM",
                    }
                )

        dosage_adjustments = []
        for d in _items("dosage_adjustments", 5):
            rec = str(d.get("recommendation") or d.get("description") or "").strip()
            if rec:
                dosage_adjustments.append(
                    {"recommendation": rec, "source": "ClinicalAgent-LLM"}
                )

        try:
            risk_score: Optional[int] = max(0, min(100, int(data.get("risk_score"))))
        except (TypeError, ValueError):
            risk_score = None

        llm_level = str(data.get("risk_level") or "").strip().lower()
        rationale = str(data.get("rationale") or "").strip()

        return {
            "dosage_adjustments": dosage_adjustments,
            "adverse_reactions": adverse_reactions,
            "recommendations_text": rationale or raw,
            "llm_contraindications": contraindications,
            "llm_interactions": interactions,
            "llm_risk_level": llm_level if llm_level in sev_ok else None,
            "risk_score": risk_score,
            "rationale": rationale,
        }

    def _build_patient_context(self, patient_data: Dict[str, Any]) -> PatientContext:
        """
        Build PatientContext from patient_data dict

        SKILL: @api-design-principles - Clean data transformation
        """
        # Calculate GFR if creatinine is provided
        gfr = patient_data.get("gfr")
        if gfr is None and patient_data.get("creatinine"):
            age = patient_data.get("age")
            weight = patient_data.get("weight")
            creatinine = patient_data.get("creatinine")
            sex = patient_data.get("sex", "M")
            if age and weight and creatinine:
                gfr = calculate_gfr_cockroft_gault(age, weight, creatinine, sex)

        return PatientContext(
            age=patient_data.get("age"),
            weight=patient_data.get("weight"),
            height=patient_data.get("height"),
            sex=patient_data.get("sex"),
            pregnant=patient_data.get("pregnant", False),
            lactating=patient_data.get("lactating", False),
            creatinine=patient_data.get("creatinine"),
            gfr=gfr,
            child_pugh=patient_data.get("child_pugh"),
            conditions=patient_data.get("conditions", []),
            allergies=patient_data.get("allergies", []),
            current_medications=patient_data.get("current_medications", []),
        )

    def _get_primary_category(
        self,
        interactions: List[Dict[str, Any]],
        contraindications: List[Dict[str, Any]],
    ) -> str:
        """
        Determine primary clinical category from findings

        SKILL: @debugging-strategies - Clear categorization logic
        """
        # Priority order for categories
        category_priority = [
            "Cardiovascular",
            "IMAO-Critico",
            "Coagulacao",
            "Renal",
            "Hepatica",
            "Neurologica",
            "Respiratoria",
        ]

        # Collect all categories from interactions
        categories = []
        for interaction in interactions:
            cat = interaction.get("category", "")
            if cat:
                categories.append(cat)

        for contraind in contraindications:
            cat = contraind.get("category", contraind.get("type", ""))
            if cat:
                categories.append(cat)

        # Return highest priority category found
        for priority_cat in category_priority:
            for cat in categories:
                if priority_cat.lower() in cat.lower():
                    return priority_cat

        return "Farmacologica"

    def _calculate_confidence(
        self,
        interactions: List[Dict[str, Any]],
        contraindications: List[Dict[str, Any]],
        state: MedSafeState,
    ) -> float:
        """
        Calculate confidence score for the analysis

        SKILL: @debugging-strategies - Multi-factor confidence scoring
        """
        confidence_factors = []

        # Factor 1: Data completeness
        patient_data = state["patient_data"]
        has_age = bool(patient_data.get("age"))
        has_weight = bool(patient_data.get("weight"))
        has_conditions = bool(patient_data.get("conditions"))
        has_medications = bool(patient_data.get("current_medications"))

        data_completeness = (
            sum([has_age, has_weight, has_conditions, has_medications]) / 4
        )
        confidence_factors.append(data_completeness * 0.3)  # 30% weight

        # Factor 2: Evidence availability
        evidence_score = min(
            len(state.get("evidence", [])) / 3, 1.0
        )  # 3+ evidence = full score
        confidence_factors.append(evidence_score * 0.2)  # 20% weight

        # Factor 3: Interaction clarity — calibrada pela FONTE da evidência.
        # Fontes determinísticas (DB/CSV/regras clínicas) dão confiança alta;
        # evidência probabilística isolada (RAG/OpenFDA) dá confiança menor.
        # A confiança reportada deve refletir a base real do achado.
        deterministic_sources = {"csv", "db", "clinical_rules"}
        if interactions:

            def _item_sources(item: Dict[str, Any]) -> set:
                srcs = set(item.get("sources") or [])
                if item.get("source"):
                    srcs.add(item["source"])
                return srcs

            has_deterministic = any(
                _item_sources(i) & deterministic_sources for i in interactions
            )
            interaction_confidence = 0.95 if has_deterministic else 0.75
        else:
            # No interactions found - could be truly safe or missing data
            interaction_confidence = 0.7 if has_medications else 0.5

        confidence_factors.append(interaction_confidence * 0.3)  # 30% weight

        # Factor 4: Refinement cycles (more cycles = lower confidence in initial analysis)
        refinement_penalty = max(0, 1.0 - (state.get("refinement_count", 0) * 0.1))
        confidence_factors.append(refinement_penalty * 0.2)  # 20% weight

        # Total confidence
        total_confidence = sum(confidence_factors)

        return min(total_confidence, 1.0)


# Factory function
def create_clinical_agent() -> ClinicalAgent:
    """Create ClinicalAgent instance"""
    return ClinicalAgent()
