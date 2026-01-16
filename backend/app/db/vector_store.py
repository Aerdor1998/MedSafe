"""
Vector Store Manager with PGVector for Medical Literature RAG

PATTERN: Retrieval-Augmented Generation (RAG) with semantic search
SKILLS: @ultrathink, @api-design-principles, @python-performance-optimization

This module provides:
1. Semantic search over medical literature using pgvector
2. Hybrid search combining semantic + keyword (BM25)
3. Document chunking strategies for embeddings
4. Reranking for precision

REFERENCE: Antonio Gulli "Agentic Design Patterns" Chapter 14 (RAG)
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document as LangChainDocument
from langchain_ollama import OllamaEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..config import settings
from ..utils.cache import rag_search_cache
from .database import engine, get_db_context
from .models import Document, Embedding

logger = logging.getLogger(__name__)


class MedicalVectorStore:
    """
    Vector Store Manager for Medical Literature

    ARCHITECTURE: Semantic search with pgvector + LangChain integration
    PATTERN: Hybrid retrieval (semantic + keyword) + Reranking

    SKILLS APPLIED:
    - @ultrathink: Clean abstraction over complex RAG pipeline
    - @api-design-principles: Simple interface for retrieval
    - @python-performance-optimization: Efficient embedding and search
    """

    def __init__(self):
        """Initialize vector store with Ollama embeddings"""

        # Initialize embeddings model from settings
        # qwen3-embedding:0.6b produces 1024-dim embeddings
        embedding_model = getattr(settings, "embedding_model", "qwen3-embedding:0.6b")
        self.embeddings = OllamaEmbeddings(
            base_url=settings.ollama_host,
            model=embedding_model,
        )
        logger.info(f"Using embedding model: {embedding_model}")

        # Connection string for pgvector (use psycopg3 driver)
        # Format: postgresql+psycopg:// for psycopg3 compatibility
        base_url = settings.database_url_safe
        if base_url.startswith("postgresql://"):
            self.connection_string = base_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        else:
            self.connection_string = base_url

        # Collection name in pgvector
        self.collection_name = "medical_literature"

        # Initialize PGVector store
        self._init_vector_store()

        # Text splitter for chunking documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # 1000 chars per chunk
            chunk_overlap=200,  # 200 char overlap for context
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

        logger.info(
            f"MedicalVectorStore initialized: collection={self.collection_name}"
        )

    def _init_vector_store(self):
        """Initialize PGVector store with LangChain"""
        try:
            # Ensure pgvector extension exists
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()

            # Initialize PGVector store (creates table if not exists)
            # langchain-postgres uses 'connection' and 'embeddings' parameters
            self.vector_store = PGVector(
                connection=self.connection_string,
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                distance_strategy="cosine",  # Cosine similarity
                pre_delete_collection=False,  # Don't delete existing data
                use_jsonb=True,  # Use JSONB for metadata storage
            )

            logger.info("PGVector store initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize PGVector: {e}")
            raise

    def add_documents(
        self, documents: List[Dict[str, Any]], batch_size: int = 100
    ) -> int:
        """
        Add documents to vector store with embeddings

        PATTERN: Batch processing for efficiency
        SKILL: @python-performance-optimization - Batch embeddings

        Args:
            documents: List of document dicts with 'text', 'metadata'
            batch_size: Number of documents to process at once

        Returns:
            Number of chunks created
        """
        try:
            total_chunks = 0

            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]

                # Prepare LangChain documents with chunking
                langchain_docs = []

                for doc in batch:
                    # Split text into chunks
                    chunks = self.text_splitter.split_text(doc["text"])

                    for chunk_idx, chunk in enumerate(chunks):
                        # Create LangChain document with metadata
                        metadata = {
                            **doc.get("metadata", {}),
                            "chunk_idx": chunk_idx,
                            "total_chunks": len(chunks),
                            "drug_name": doc.get("drug_name", ""),
                            "source": doc.get("source", ""),
                            "section": doc.get("section", ""),
                        }

                        langchain_docs.append(
                            LangChainDocument(page_content=chunk, metadata=metadata)
                        )

                # Add batch to vector store (embeddings created automatically)
                if langchain_docs:
                    self.vector_store.add_documents(langchain_docs)
                    total_chunks += len(langchain_docs)

                    logger.info(
                        f"   Added batch {i//batch_size + 1}: {len(langchain_docs)} chunks"
                    )

            logger.info(f"Added {total_chunks} chunks from {len(documents)} documents")
            return total_chunks

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    def semantic_search(
        self, query: str, k: int = 5, filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search using cosine similarity

        PATTERN: Dense retrieval with embeddings
        SKILL: @ultrathink - Clean search abstraction

        Args:
            query: Search query
            k: Number of results to return
            filter_dict: Optional metadata filters (e.g., {'drug_name': 'aspirin'})

        Returns:
            List of documents with scores
        """
        try:
            logger.info(f"Semantic search: '{query}' (k={k})")

            # Perform similarity search
            results = self.vector_store.similarity_search_with_score(
                query=query, k=k, filter=filter_dict
            )

            # Format results
            formatted_results = []
            for doc, score in results:
                formatted_results.append(
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "score": float(score),
                        "relevance": self._score_to_relevance(score),
                    }
                )

            logger.info(f"   Found {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def hybrid_search(
        self,
        query: str,
        k: int = 5,
        semantic_weight: float = 0.7,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic + keyword (BM25-like)

        PATTERN: Hybrid retrieval for improved precision
        REFERENCE: Antonio Gulli "RAG" Chapter 14, pg 285-290

        CACHING: Uses TTL cache (30min) to avoid repeated embedding computation

        Args:
            query: Search query
            k: Number of results
            semantic_weight: Weight for semantic scores (1-semantic_weight = keyword weight)
            filter_dict: Optional metadata filters

        Returns:
            List of documents with combined scores
        """
        # Generate cache key from query + params
        filter_str = json.dumps(filter_dict, sort_keys=True) if filter_dict else ""
        cache_key = hashlib.md5(
            f"{query.lower().strip()}|k={k}|sw={semantic_weight}|f={filter_str}".encode()
        ).hexdigest()

        # Check cache first
        cached = rag_search_cache.get(cache_key)
        if cached is not None:
            logger.info(
                f"RAG cache hit: '{query[:50]}...' (saved embedding computation)"
            )
            return cached

        try:
            logger.info(f"Hybrid search: '{query}' (semantic_weight={semantic_weight})")

            # 1. Semantic search
            semantic_results = self.semantic_search(
                query, k=k * 2, filter_dict=filter_dict
            )

            # 2. Keyword search (PostgreSQL full-text search)
            keyword_results = self._keyword_search(
                query, k=k * 2, filter_dict=filter_dict
            )

            # Se a busca semântica falhar, usar apenas keyword
            if not semantic_results and keyword_results:
                logger.info("Semantic search empty, using keyword-only results")
                results = keyword_results[:k]
                rag_search_cache.set(cache_key, results)
                return results

            # 3. Combine scores (Reciprocal Rank Fusion)
            combined = self._reciprocal_rank_fusion(
                semantic_results, keyword_results, semantic_weight=semantic_weight
            )

            # 4. Return top k
            top_k = combined[:k]

            logger.info(
                f"   Combined {len(semantic_results)} semantic + {len(keyword_results)} keyword → {len(top_k)} results"
            )

            # Cache results
            rag_search_cache.set(cache_key, top_k)
            logger.debug(f"RAG cached: '{query[:30]}...'")

            return top_k

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            # Fallback to semantic only (don't cache errors)
            return self.semantic_search(query, k=k, filter_dict=filter_dict)

    def _keyword_search(
        self, query: str, k: int = 5, filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Keyword search using PostgreSQL full-text search

        PATTERN: Sparse retrieval (BM25-like)
        """
        try:
            with get_db_context() as db:
                # Build filter conditions SAFELY (no string interpolation).
                #
                # IMPORTANT:
                # - `filter_dict` is untrusted input.
                # - Never concatenate values into SQL (SQL injection).
                #
                # We allow only a small whitelist of metadata keys and bind both the key and value.
                allowed_filter_keys = {
                    "drug_name",
                    "source",
                    "section",
                    "chunk_idx",
                    "total_chunks",
                }

                where_clauses: list[str] = []
                params: Dict[str, Any] = {"query": query, "k": k}

                if filter_dict:
                    for idx, (raw_key, raw_value) in enumerate(filter_dict.items()):
                        if raw_key not in allowed_filter_keys:
                            # Ignore unknown keys instead of risking injection or unexpected scans.
                            continue
                        if raw_value is None:
                            continue

                        # We query the jsonb metadata stored in `cmetadata`.
                        # `->>` extracts text; bind both key and value.
                        k_param = f"fk_{idx}"
                        v_param = f"fv_{idx}"
                        where_clauses.append(f"(cmetadata ->> :{k_param}) = :{v_param}")
                        params[k_param] = str(raw_key)
                        params[v_param] = str(raw_value)

                where_clause = (
                    (" AND " + " AND ".join(where_clauses)) if where_clauses else ""
                )

                # Full-text search query
                query_sql = f"""
                    SELECT
                        document,
                        cmetadata as metadata,
                        ts_rank(to_tsvector('english', document), plainto_tsquery('english', :query)) as score
                    FROM langchain_pg_embedding
                    WHERE to_tsvector('english', document) @@ plainto_tsquery('english', :query)
                    {where_clause}
                    ORDER BY score DESC
                    LIMIT :k
                """

                result = db.execute(text(query_sql), params)

                results = []
                for row in result:
                    results.append(
                        {
                            "content": row[0],
                            "metadata": row[1],
                            "score": float(row[2]),
                            "relevance": self._score_to_relevance(row[2]),
                        }
                    )

                return results

        except Exception as e:
            logger.warning(f" Keyword search failed: {e}")
            return []

    def _reciprocal_rank_fusion(
        self,
        semantic_results: List[Dict],
        keyword_results: List[Dict],
        semantic_weight: float = 0.7,
        k: int = 60,  # RRF constant
    ) -> List[Dict]:
        """
        Combine results using Reciprocal Rank Fusion (RRF)

        REFERENCE: "Reciprocal Rank Fusion outperforms Condorcet and individual rank learning"
        PATTERN: Rank fusion for hybrid retrieval

        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            semantic_weight: Weight for semantic scores
            k: RRF constant (default 60)

        Returns:
            Combined and re-ranked results
        """
        # Create score map by content hash
        score_map = {}

        # Add semantic scores with RRF
        for rank, doc in enumerate(semantic_results, 1):
            content_hash = hash(doc["content"])
            if content_hash not in score_map:
                score_map[content_hash] = {"doc": doc, "score": 0.0}
            score_map[content_hash]["score"] += semantic_weight * (1.0 / (k + rank))

        # Add keyword scores with RRF
        keyword_weight = 1.0 - semantic_weight
        for rank, doc in enumerate(keyword_results, 1):
            content_hash = hash(doc["content"])
            if content_hash not in score_map:
                score_map[content_hash] = {"doc": doc, "score": 0.0}
            score_map[content_hash]["score"] += keyword_weight * (1.0 / (k + rank))

        # Sort by combined score
        combined = sorted(score_map.values(), key=lambda x: x["score"], reverse=True)

        # Return documents with updated scores
        return [
            {
                **item["doc"],
                "score": item["score"],
                "relevance": self._score_to_relevance(item["score"]),
            }
            for item in combined
        ]

    def _score_to_relevance(self, score: float) -> str:
        """
        Convert similarity score to relevance label

        SKILL: @ultrathink - Human-readable relevance

        NOTE: Thresholds adjusted for Ollama embeddings (nomic-embed-text, qwen3-embedding)
        which typically produce lower cosine similarity scores than OpenAI embeddings.
        """
        if score >= 0.8:
            return "VERY_HIGH"
        elif score >= 0.6:
            return "HIGH"
        elif score >= 0.4:
            return "MEDIUM"
        elif score >= 0.2:
            return "LOW"
        else:
            return "VERY_LOW"

    def search_by_drug(
        self, drug_name: str, section: Optional[str] = None, k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for drug-specific information

        PATTERN: Filtered semantic search

        Args:
            drug_name: Drug name to search
            section: Optional section filter (e.g., "contraindications")
            k: Number of results

        Returns:
            List of relevant documents
        """
        # Build filter
        filter_dict = {"drug_name": drug_name.lower()}
        if section:
            filter_dict["section"] = section.lower()

        # Semantic search with filter
        query = f"drug interactions and safety information for {drug_name}"
        if section:
            query += f" in {section} section"

        return self.semantic_search(query, k=k, filter_dict=filter_dict)

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store collection

        SKILL: @debugging-strategies - Observability
        """
        try:
            with get_db_context() as db:
                # Count total embeddings
                count_query = text(
                    """
                    SELECT COUNT(*) as total_embeddings,
                           COUNT(DISTINCT cmetadata->>'drug_name') as unique_drugs,
                           COUNT(DISTINCT cmetadata->>'source') as unique_sources
                    FROM langchain_pg_embedding
                    WHERE collection_id = (
                        SELECT uuid FROM langchain_pg_collection
                        WHERE name = :collection_name
                    )
                """
                )

                result = db.execute(
                    count_query, {"collection_name": self.collection_name}
                )
                row = result.fetchone()

                if row:
                    embedding_model = getattr(
                        settings, "embedding_model", "qwen3-embedding:0.6b"
                    )
                    return {
                        "collection_name": self.collection_name,
                        "total_embeddings": row[0],
                        "unique_drugs": row[1],
                        "unique_sources": row[2],
                        "embedding_model": embedding_model,
                        "distance_strategy": "cosine",
                    }
                else:
                    return {
                        "collection_name": self.collection_name,
                        "total_embeddings": 0,
                        "unique_drugs": 0,
                        "unique_sources": 0,
                    }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

    def delete_collection(self) -> bool:
        """
        Delete entire collection (use with caution!)

        WARNING: This will delete all embeddings in the collection
        """
        try:
            logger.warning(f" Deleting collection: {self.collection_name}")

            with get_db_context() as db:
                delete_query = text(
                    """
                    DELETE FROM langchain_pg_embedding
                    WHERE collection_id = (
                        SELECT uuid FROM langchain_pg_collection
                        WHERE name = :collection_name
                    )
                """
                )
                db.execute(delete_query, {"collection_name": self.collection_name})
                db.commit()

            logger.info("Collection deleted")
            return True

        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False


# Singleton instance
_vector_store_instance: Optional[MedicalVectorStore] = None


def get_vector_store() -> MedicalVectorStore:
    """
    Get or create singleton vector store instance

    PATTERN: Singleton for shared resource
    """
    global _vector_store_instance

    if _vector_store_instance is None:
        _vector_store_instance = MedicalVectorStore()

    return _vector_store_instance
