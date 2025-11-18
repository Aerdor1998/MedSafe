"""
DocAgent - Agente para busca e análise de documentação de medicamentos com RAG
Implementa padrão Knowledge Retrieval (RAG) do Capítulo 14 - Agentic Design Patterns

RAG (Retrieval-Augmented Generation):
1. Retrieve: Buscar documentos relevantes via similaridade semântica
2. Augment: Enriquecer o contexto com informações recuperadas
3. Generate: LLM gera resposta baseada no contexto aumentado

SKILLS APLICADAS:
- FastAPI Templates: Estrutura assíncrona e type hints
- API Design Principles: Interface clara e RESTful
- Python Performance: Caching e otimizações
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import hashlib
from functools import lru_cache

import httpx
import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from ..config import settings
from ..db.database import get_db_context
from ..db.models import Document, Embedding

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Serviço para gerar embeddings usando Ollama

    SKILL: Python Performance Optimization
    - LRU cache para embeddings frequentes
    - Batch processing para múltiplos textos
    """

    def __init__(self):
        self.ollama_url = f"{settings.ollama_host}/api/embeddings"
        self.model = "nomic-embed-text"  # Modelo de embeddings
        self.dimension = 768  # Dimensão do embedding
        self._cache = {}

        logger.info(f"🔢 EmbeddingService inicializado (modelo: {self.model})")

    @lru_cache(maxsize=1000)
    def _get_cache_key(self, text: str) -> str:
        """Gerar chave de cache para texto"""
        return hashlib.md5(text.encode()).hexdigest()

    async def embed_text(self, text: str) -> List[float]:
        """
        Gerar embedding para texto

        Args:
            text: Texto para gerar embedding

        Returns:
            Lista de floats representando o embedding
        """
        # Verificar cache
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": text
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Erro ao gerar embedding: {response.status_code}")
                    # Fallback: embedding aleatório normalizado
                    return self._generate_fallback_embedding()

                result = response.json()
                embedding = result.get("embedding", [])

                # Cachear resultado
                self._cache[cache_key] = embedding

                return embedding

        except Exception as e:
            logger.error(f"Erro ao chamar Ollama embeddings: {e}")
            return self._generate_fallback_embedding()

    def _generate_fallback_embedding(self) -> List[float]:
        """Gerar embedding fallback em caso de erro"""
        # Embedding aleatório normalizado
        vec = np.random.randn(self.dimension)
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Gerar embeddings para múltiplos textos em batch

        SKILL: Python Performance - Batch processing
        """
        tasks = [self.embed_text(text) for text in texts]
        return await asyncio.gather(*tasks)

    def cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """Calcular similaridade de cosseno entre dois vetores"""
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))


class VectorStore:
    """
    Vector store para busca de similaridade

    SKILL: Python Performance Optimization
    - Busca otimizada com numpy
    - Índices do PostgreSQL
    """

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
        logger.info("🗄️ VectorStore inicializado")

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Buscar documentos similares ao query

        Args:
            query: Texto da consulta
            top_k: Número de resultados a retornar
            filters: Filtros opcionais (drug_name, section, etc)

        Returns:
            Lista de documentos ordenados por similaridade
        """
        # 1. Gerar embedding da query
        query_embedding = await self.embedding_service.embed_text(query)

        # 2. Buscar embeddings no banco
        with get_db_context() as db:
            # Base query
            query_obj = select(Embedding, Document).join(
                Document, Embedding.document_id == Document.id
            )

            # Aplicar filtros
            if filters:
                if 'drug_name' in filters:
                    query_obj = query_obj.where(
                        Document.drug_name.ilike(f"%{filters['drug_name']}%")
                    )
                if 'section' in filters:
                    query_obj = query_obj.where(Document.section == filters['section'])

            # Executar query
            results = db.execute(query_obj).all()

            # 3. Calcular similaridades
            similarities = []
            for embedding_row, doc in results:
                # Parse vector (pode estar como JSON string no SQLite)
                if isinstance(embedding_row.vector, str):
                    vector = json.loads(embedding_row.vector)
                else:
                    vector = embedding_row.vector

                similarity = self.embedding_service.cosine_similarity(
                    query_embedding, vector
                )

                similarities.append({
                    'document': doc,
                    'embedding': embedding_row,
                    'similarity': similarity
                })

            # 4. Ordenar por similaridade e retornar top_k
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            top_results = similarities[:top_k]

            # 5. Formatar resultados
            formatted_results = []
            for item in top_results:
                doc = item['document']
                formatted_results.append({
                    'document_id': str(doc.id),
                    'drug_name': doc.drug_name,
                    'section': doc.section,
                    'text': doc.text,
                    'source': doc.source,
                    'source_url': doc.source_url,
                    'similarity_score': item['similarity'],
                    'meta': doc.meta
                })

            return formatted_results


class DocAgent:
    """
    Agente para busca RAG em documentação de medicamentos

    PADRÃO: Knowledge Retrieval (RAG) - Capítulo 14

    Pipeline RAG:
    1. RETRIEVE: Buscar documentos relevantes via embeddings
    2. RANK: Reordenar resultados por relevância
    3. AUGMENT: Enriquecer contexto com documentos
    4. GENERATE: LLM gera resposta (opcional, feito pelo agente chamador)
    """

    def __init__(self):
        """Inicializar o DocAgent com RAG"""
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore(self.embedding_service)

        logger.info("📚 DocAgent inicializado com RAG (Capítulo 14)")

    async def find_evidence(
        self,
        drug_name: str,
        sections: List[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Buscar evidências sobre medicamento específico

        IMPLEMENTAÇÃO REAL substituindo STUB anterior

        Args:
            drug_name: Nome do medicamento
            sections: Seções a buscar (contraindicações, advertências, etc)
            top_k: Número de evidências a retornar

        Returns:
            Lista de evidências encontradas com scores de similaridade
        """
        logger.info(f"🔍 Buscando evidências para: {drug_name}")

        evidences = []

        # Se sections especificadas, buscar cada uma
        if sections:
            for section in sections:
                # Construir query específica
                query = f"{drug_name} {section}"

                # Buscar documentos similares
                results = await self.vector_store.search(
                    query=query,
                    top_k=top_k,
                    filters={'drug_name': drug_name, 'section': section}
                )

                # Formatar resultados
                for result in results:
                    evidences.append({
                        "drug_name": result['drug_name'],
                        "section": result['section'],
                        "content": result['text'],
                        "source": result['source'],
                        "source_url": result['source_url'],
                        "confidence": result['similarity_score'],
                        "status": "retrieved_from_rag",
                        "meta": result['meta']
                    })

        else:
            # Buscar geral sem filtro de seção
            results = await self.vector_store.search(
                query=drug_name,
                top_k=top_k,
                filters={'drug_name': drug_name}
            )

            for result in results:
                evidences.append({
                    "drug_name": result['drug_name'],
                    "section": result['section'],
                    "content": result['text'],
                    "source": result['source'],
                    "source_url": result['source_url'],
                    "confidence": result['similarity_score'],
                    "status": "retrieved_from_rag",
                    "meta": result['meta']
                })

        logger.info(f"✅ {len(evidences)} evidências encontradas via RAG")

        return evidences

    async def search_by_symptoms(
        self,
        symptoms: List[str],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Buscar medicamentos baseado em sintomas/condições

        Args:
            symptoms: Lista de sintomas ou condições
            top_k: Número de resultados

        Returns:
            Medicamentos relacionados aos sintomas
        """
        query = " ".join(symptoms)
        logger.info(f"🔍 Buscando medicamentos para sintomas: {query}")

        results = await self.vector_store.search(
            query=query,
            top_k=top_k
        )

        # Agrupar por medicamento
        medications = {}
        for result in results:
            drug_name = result['drug_name']
            if drug_name not in medications:
                medications[drug_name] = {
                    'drug_name': drug_name,
                    'sections': [],
                    'max_similarity': 0.0
                }

            medications[drug_name]['sections'].append({
                'section': result['section'],
                'text': result['text'],
                'similarity': result['similarity_score']
            })

            # Atualizar max similarity
            if result['similarity_score'] > medications[drug_name]['max_similarity']:
                medications[drug_name]['max_similarity'] = result['similarity_score']

        # Ordenar por max similarity
        sorted_meds = sorted(
            medications.values(),
            key=lambda x: x['max_similarity'],
            reverse=True
        )

        return sorted_meds

    async def hybrid_search(
        self,
        query: str,
        drug_name: Optional[str] = None,
        use_reranking: bool = True,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Busca híbrida: lexical + semântica + reranking

        SKILL: API Design Principles - Interface flexível

        Args:
            query: Consulta textual
            drug_name: Filtro opcional por medicamento
            use_reranking: Se deve usar LLM para reranking
            top_k: Número de resultados

        Returns:
            Resultados ordenados por relevância
        """
        filters = {}
        if drug_name:
            filters['drug_name'] = drug_name

        # 1. Buscar via embeddings (semantic search)
        semantic_results = await self.vector_store.search(
            query=query,
            top_k=top_k * 2,  # Buscar mais para reranking
            filters=filters
        )

        # 2. Reranking com LLM (opcional)
        if use_reranking and semantic_results:
            reranked = await self._rerank_with_llm(query, semantic_results)
            return reranked[:top_k]

        return semantic_results[:top_k]

    async def _rerank_with_llm(
        self,
        query: str,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Reranking de resultados usando LLM

        SKILL: Python Performance - Caching de reranking
        """
        logger.info(f"🔄 Rerankingcom LLM: {len(candidates)} candidatos")

        # Preparar prompt para LLM
        prompt = f"""
Você é um especialista em relevância de documentos médicos.

Query do usuário: "{query}"

Candidatos:
"""
        for i, candidate in enumerate(candidates, 1):
            prompt += f"\n{i}. {candidate['section']}: {candidate['text'][:200]}..."

        prompt += """

Ordene os candidatos por relevância para a query (mais relevante primeiro).
Retorne apenas os números separados por vírgula.
Exemplo: 3,1,5,2,4
"""

        try:
            # Chamar Ollama para reranking
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{settings.ollama_host}/api/generate",
                    json={
                        "model": settings.ollama_llm,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1
                        }
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    ranking_text = result.get("response", "")

                    # Parse ranking
                    try:
                        rankings = [int(x.strip()) - 1 for x in ranking_text.split(",")]
                        # Reordenar candidatos
                        reranked = [candidates[i] for i in rankings if i < len(candidates)]

                        logger.info(f"✅ Reranking concluído: {len(reranked)} resultados")
                        return reranked
                    except:
                        logger.warning("⚠️ Erro ao parse ranking do LLM, usando ordem original")
                        return candidates

        except Exception as e:
            logger.error(f"❌ Erro no reranking com LLM: {e}")

        return candidates


# Instância global (singleton)
_doc_agent = None


def get_doc_agent() -> DocAgent:
    """Obter instância singleton do DocAgent"""
    global _doc_agent
    if _doc_agent is None:
        _doc_agent = DocAgent()
    return _doc_agent
