"""
DocumentAgent - Step 2: "Scan the Scene" - TRUE RAG IMPLEMENTATION

PATTERN: Retrieval-Augmented Generation (RAG) with pgvector
SKILLS: @ultrathink, @api-design-principles, @debugging-strategies

ARCHITECTURE: Semantic search → Hybrid retrieval → Reranking → Evidence extraction

This is a PRODUCTION RAG implementation using:
1. PGVector for semantic search over medical literature
2. Hybrid search (semantic + keyword) for precision
3. Evidence extraction with citations
4. Fallback strategies with clear warnings

REFERENCE:
- Antonio Gulli "Agentic Design Patterns" Chapter 14 (RAG), pg 281-310
- Google "Introduction to Agents" pg 21 (Evidence Retrieval)

CRITICAL: For medical systems, evidence MUST be real and verifiable.
No LLM synthesis without explicit warning to downstream agents.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..db.vector_store import MedicalVectorStore, get_vector_store
from ..services.drug_interactions import normalize_drug_name
from .base_agent import BaseAgent
from .state import MedSafeState

logger = logging.getLogger(__name__)


class DocumentAgent(BaseAgent):
    """
    DocumentAgent: Evidence retrieval for clinical analysis using TRUE RAG

    MISSION: "Scan the Scene" - Gather REAL medical evidence (not synthesized)
    PATTERN: Retrieval-Augmented Generation with pgvector

    CRITICAL CHANGE: This agent NO LONGER synthesizes evidence with LLM.
    All evidence comes from indexed medical literature in vector store.

    SKILLS APPLIED:
    - @ultrathink: Production-grade RAG architecture
    - @api-design-principles: Clean retrieval interface
    - @debugging-strategies: Comprehensive evidence logging and fallback strategies
    """

    def __init__(self):
        super().__init__(agent_name="DocumentAgent")

        # Initialize vector store for semantic search
        self.vector_store: MedicalVectorStore = get_vector_store()

        # Retrieval configuration
        # NOTE: Lowered min_relevance_score from 0.3 to 0.15 for better recall
        # Medical RAG should prioritize recall over precision - ClinicalAgent will filter
        self.top_k_semantic = (
            15  # Retrieve top 15 from semantic search (increased from 10)
        )
        self.top_k_final = 8  # Return top 8 after reranking (increased from 5)
        self.min_relevance_score = 0.15  # Minimum cosine similarity (lowered from 0.3)

        # Fallback mode flags
        self.allow_llm_fallback = False  # CRITICAL: Set to False for production
        self.warn_on_low_evidence = True

        logger.info(
            f"📚 DocumentAgent initialized with TRUE RAG: "
            f"vector_store={self.vector_store.collection_name}, "
            f"llm_fallback={self.allow_llm_fallback}"
        )

    def get_system_prompt(self) -> str:
        """
        System prompt for DocumentAgent

        PATTERN: Evidence-focused retrieval specialist
        """
        return """Você é o DocumentAgent do MedSafe, um especialista em recuperação de evidências médicas.

Sua função é analisar literatura médica recuperada e extrair informações-chave:
1. Identificar as passagens mais relevantes para a questão clínica
2. Extrair alertas de interações medicamentosas e contraindicações
3. Resumir mecanismos farmacológicos
4. Destacar avisos de segurança e reações adversas
5. Fornecer citações claras aos documentos fonte

REQUISITOS CRÍTICOS:
- Trabalhe apenas com as evidências fornecidas (NÃO invente informações)
- Cite claramente as fontes para todas as afirmações
- Sinalize quando as evidências forem insuficientes ou contraditórias
- Priorize fontes autorizadas (FDA, ANVISA, pesquisas revisadas por pares)

IMPORTANTE: Todas as suas respostas devem ser em PORTUGUÊS BRASILEIRO.
Use terminologia médica em português quando possível.

Sua saída informará a análise de segurança do ClinicalAgent.
Precisão médica é fundamental - em caso de dúvida, sinalize para revisão humana.
"""

    def process(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Retrieve medical evidence using TRUE RAG

        PATTERN: Think → Act → Observe (PDF pg 10-13, step 2)

        WORKFLOW:
        1. Extract medications from state
        2. Semantic search in vector store for each medication
        3. Hybrid search (semantic + keyword) for precision
        4. Aggregate and deduplicate evidence
        5. Extract citations and metadata
        6. Return structured evidence to state

        Args:
            state: Current MedSafeState

        Returns:
            Dict with evidence, citations, and metadata
        """
        try:
            start_time = datetime.now()
            if "timestamps" not in state:
                state["timestamps"] = {}
            self.log_step(state, "Starting TRUE RAG evidence retrieval")

            medication_text = state.get("medication_text", "")
            patient_data = state.get("patient_data", {})

            # Extract individual medications
            medications = self._extract_medications(medication_text, patient_data)

            # LGPD/PHI: avoid logging medication names in plaintext
            logger.info("📋 Extracted %d medications for retrieval", len(medications))

            # Retrieve evidence for all medications
            all_evidence = []
            retrieval_stats = {
                "medications_searched": len(medications),
                "total_documents_retrieved": 0,
                "high_relevance_count": 0,
                "medium_relevance_count": 0,
                "low_relevance_count": 0,
                "sources_used": set(),
            }

            for idx, medication in enumerate(medications, start=1):
                # LGPD/PHI: avoid logging medication names in plaintext
                logger.info(
                    "Searching evidence for medication %d/%d", idx, len(medications)
                )

                # Hybrid search (semantic + keyword)
                evidence_docs = self._retrieve_evidence_for_drug(
                    medication, patient_data
                )

                # Update stats
                retrieval_stats["total_documents_retrieved"] += len(evidence_docs)

                for doc in evidence_docs:
                    relevance = doc.get("relevance", "UNKNOWN")
                    if relevance == "HIGH" or relevance == "VERY_HIGH":
                        retrieval_stats["high_relevance_count"] += 1
                    elif relevance == "MEDIUM":
                        retrieval_stats["medium_relevance_count"] += 1
                    else:
                        retrieval_stats["low_relevance_count"] += 1

                    source = doc.get("metadata", {}).get("source", "unknown")
                    retrieval_stats["sources_used"].add(source)

                all_evidence.extend(evidence_docs)

            # Deduplicate and rank
            unique_evidence = self._deduplicate_evidence(all_evidence)

            # Check if we have sufficient evidence
            evidence_quality = self._assess_evidence_quality(unique_evidence)

            # Extract citations
            evidence_links = self._extract_citations(unique_evidence)

            # Generate evidence summary using LLM
            evidence_summary = self._summarize_evidence(unique_evidence, medications)

            # Update state
            updates = {
                "evidence": unique_evidence,
                "evidence_links": evidence_links,
                "evidence_summary": evidence_summary,
                "evidence_quality": evidence_quality,
                "retrieval_stats": {
                    **retrieval_stats,
                    "sources_used": list(retrieval_stats["sources_used"]),
                },
            }

            # Update timestamps
            if "timestamps" not in state:
                updates["timestamps"] = {}
            else:
                updates["timestamps"] = state.get("timestamps", {}).copy()
            updates["timestamps"]["evidence_retrieval_end"] = datetime.now()

            # Log results
            duration = (datetime.now() - start_time).total_seconds()

            logger.info(
                f"Evidence retrieval completed: "
                f"{len(unique_evidence)} documents "
                f"({retrieval_stats['high_relevance_count']} high relevance) "
                f"in {duration:.2f}s"
            )

            # Log top evidence
            logger.info("📚 Top evidence documents:")
            for i, doc in enumerate(unique_evidence[:3], 1):
                metadata = doc.get("metadata", {})
                logger.info(
                    f"   {i}. [{doc.get('relevance', 'UNKNOWN')}] "
                    f"{metadata.get('drug_name', 'unknown')} - "
                    f"{metadata.get('section', 'unknown')} "
                    f"(source: {metadata.get('source', 'unknown')})"
                )

            # Warning if low evidence quality
            if evidence_quality["status"] in ["LOW", "INSUFFICIENT"]:
                warning = (
                    f" Evidence quality is {evidence_quality['status']}: "
                    f"Only {len(unique_evidence)} documents retrieved. "
                    f"Clinical analysis may be incomplete."
                )
                logger.warning(warning)
                updates["warnings"] = state.get("warnings", []) + [warning]

            self.log_step(
                state,
                f"Evidence retrieval completed: {len(unique_evidence)} docs, "
                f"quality={evidence_quality['status']}",
            )

            return updates

        except Exception as e:
            return self.handle_error(state, e, "Failed to retrieve evidence")

    def _extract_medications(
        self, medication_text: str, patient_data: Dict[str, Any]
    ) -> List[str]:
        """
        Extract individual medication names from text and patient data

        PATTERN: Medication extraction with normalization
        """
        medications = []

        # Extract from medication_text (comma-separated)
        if medication_text:
            meds = [med.strip() for med in medication_text.split(",")]
            medications.extend(meds)

        # Extract from patient_data
        if "current_medications" in patient_data:
            medications.extend(patient_data["current_medications"])

        if "meds_in_use" in patient_data:
            medications.extend(patient_data["meds_in_use"])

        # Normalize and deduplicate
        normalized = []
        seen = set()

        for med in medications:
            if med:
                # Normalize drug name (convert to scientific name)
                normalized_name = normalize_drug_name(med)
                if normalized_name and normalized_name not in seen:
                    seen.add(normalized_name)
                    normalized.append(normalized_name)

        return normalized

    def _retrieve_evidence_for_drug(
        self, drug_name: str, patient_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Retrieve evidence for a specific drug using hybrid search

        PATTERN: Hybrid retrieval (semantic + keyword) for precision
        REFERENCE: Antonio Gulli Chapter 14, pg 285-290

        Args:
            drug_name: Drug name to search
            patient_data: Patient context for query enrichment

        Returns:
            List of evidence documents with scores
        """
        # Build context-aware query
        query = self._build_search_query(drug_name, patient_data)

        # Perform hybrid search
        try:
            evidence = self.vector_store.hybrid_search(
                query=query,
                k=self.top_k_final,
                semantic_weight=0.7,  # 70% semantic, 30% keyword
                filter_dict=None,  # No filter - search all documents
            )

            # Filter by minimum relevance
            filtered_evidence = [
                doc
                for doc in evidence
                if doc.get("score", 0.0) >= self.min_relevance_score
            ]

            # FALLBACK: If nothing passes threshold but we have results, return top docs with warning
            if not filtered_evidence and evidence:
                logger.warning(
                    f" No documents passed min_score={self.min_relevance_score}. "
                    f"Returning top {min(3, len(evidence))} results for manual review."
                )
                # Return top 3 regardless of score, but mark them as low confidence
                filtered_evidence = evidence[:3]
                for doc in filtered_evidence:
                    doc["low_confidence"] = True

            logger.info(
                f"   Retrieved {len(evidence)} docs, "
                f"filtered to {len(filtered_evidence)} (min_score={self.min_relevance_score})"
            )

            return filtered_evidence

        except Exception as e:
            logger.error(f"Hybrid search failed for {drug_name}: {e}")

            # Fallback to semantic-only search
            try:
                evidence = self.vector_store.semantic_search(
                    query=query,
                    k=self.top_k_final,
                )
                logger.warning(
                    f" Fallback to semantic-only search: {len(evidence)} docs"
                )
                return evidence

            except Exception as e2:
                logger.error(f"Semantic search also failed: {e2}")
                return []

    def _build_search_query(self, drug_name: str, patient_data: Dict[str, Any]) -> str:
        """
        Build context-enriched search query

        PATTERN: Query enrichment with patient context
        """
        # Base query
        query = f"drug interactions contraindications adverse reactions for {drug_name}"

        # Add patient conditions if present
        conditions = patient_data.get("conditions", [])
        if conditions:
            query += f" in patients with {', '.join(conditions[:3])}"

        # Add special populations
        if patient_data.get("pregnant"):
            query += " in pregnancy"

        age = patient_data.get("age")
        if age and age >= 65:
            query += " in elderly patients"
        elif age and age < 18:
            query += " in pediatric patients"

        return query

    def _deduplicate_evidence(
        self, evidence: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate evidence by content hash and rank by relevance

        SKILL: @python-performance-optimization - Efficient deduplication
        """
        seen_content = set()
        unique = []

        # Sort by score first (highest to lowest)
        sorted_evidence = sorted(
            evidence, key=lambda x: x.get("score", 0.0), reverse=True
        )

        for doc in sorted_evidence:
            # Create content hash (first 200 chars)
            content = doc.get("content", "")
            content_hash = hash(content[:200])

            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique.append(doc)

        duplicates_removed = len(evidence) - len(unique)
        if duplicates_removed > 0:
            logger.info(f"   Removed {duplicates_removed} duplicate documents")

        return unique

    def _assess_evidence_quality(
        self, evidence: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Assess quality and sufficiency of retrieved evidence

        PATTERN: Evidence quality assessment for medical RAG
        """
        total_docs = len(evidence)

        # Count by relevance
        high_relevance = sum(
            1 for doc in evidence if doc.get("relevance") in ["HIGH", "VERY_HIGH"]
        )

        # Count authoritative sources
        authoritative_sources = {"FDA", "ANVISA", "PubMed", "DrugBank"}
        authoritative_count = sum(
            1
            for doc in evidence
            if doc.get("metadata", {}).get("source") in authoritative_sources
        )

        # Determine status
        if total_docs == 0:
            status = "INSUFFICIENT"
            message = "No evidence found in knowledge base"
        elif high_relevance >= 3 and authoritative_count >= 2:
            status = "EXCELLENT"
            message = f"{high_relevance} high-relevance docs from authoritative sources"
        elif high_relevance >= 1 and total_docs >= 3:
            status = "GOOD"
            message = (
                f"{total_docs} documents retrieved with {high_relevance} high-relevance"
            )
        elif total_docs >= 2:
            status = "MODERATE"
            message = f"{total_docs} documents but low relevance scores"
        else:
            status = "LOW"
            message = f"Only {total_docs} document(s) retrieved"

        return {
            "status": status,
            "message": message,
            "total_documents": total_docs,
            "high_relevance_count": high_relevance,
            "authoritative_count": authoritative_count,
        }

    def _summarize_evidence(
        self, evidence: List[Dict[str, Any]], medications: List[str]
    ) -> str:
        """
        Use LLM to summarize retrieved evidence

        PATTERN: LLM as summarizer (NOT as knowledge source)

        CRITICAL: LLM only summarizes EXISTING evidence, does not generate new info
        """
        if not evidence:
            return "No evidence retrieved from knowledge base."

        # Prepare evidence context
        evidence_text = ""
        for i, doc in enumerate(evidence[:5], 1):  # Top 5 only
            metadata = doc.get("metadata", {})
            evidence_text += f"\n\n=== DOCUMENT {i} ===\n"
            evidence_text += f"Drug: {metadata.get('drug_name', 'unknown')}\n"
            evidence_text += f"Section: {metadata.get('section', 'unknown')}\n"
            evidence_text += f"Source: {metadata.get('source', 'unknown')}\n"
            evidence_text += f"Relevance: {doc.get('relevance', 'UNKNOWN')}\n"
            evidence_text += f"Content:\n{doc.get('content', '')}\n"

        # LLM prompt for summarization
        prompt = f"""Analyze the following medical evidence for medications: {', '.join(medications)}

Extract and summarize:
1. Key drug interactions
2. Contraindications
3. Warnings and adverse reactions
4. Special population considerations (elderly, pediatric, pregnancy)

{evidence_text}

Provide a concise clinical summary focusing on safety-critical information.
Only include information explicitly stated in the evidence above.
If evidence is insufficient for a particular aspect, state this clearly.
"""

        try:
            summary = self.invoke_llm(prompt, context={"medications": medications})
            return summary
        except Exception as e:
            logger.error(f"Evidence summarization failed: {e}")
            return "Evidence summarization failed. Raw evidence available in evidence field."

    def _extract_citations(self, evidence: List[Dict[str, Any]]) -> List[str]:
        """
        Extract citation URLs and source references from evidence

        SKILL: @code-review-excellence - Clean citation extraction
        """
        citations = []

        for doc in evidence:
            metadata = doc.get("metadata", {}) or {}
            source = (metadata.get("source") or "").strip()
            source_url = (metadata.get("source_url") or "").strip()
            drug_name = (metadata.get("drug_name") or "").strip()
            section = (metadata.get("section") or "").strip()

            # Metadata vazio produzia lixo ":  - " na UI — pula documentos
            # sem qualquer informação citável.
            details = " - ".join(p for p in (drug_name, section) if p)
            if not (source or details or source_url):
                continue

            citation = f"{source or 'Fonte'}: {details}" if details else source
            if source_url:
                citation = f"[{citation or source_url}]({source_url})"

            if citation:
                citations.append(citation)

        return citations


# Factory function
def create_document_agent() -> DocumentAgent:
    """Create DocumentAgent instance with TRUE RAG"""
    return DocumentAgent()
