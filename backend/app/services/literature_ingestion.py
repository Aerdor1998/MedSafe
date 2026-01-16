"""
Literature Ingestion Service - Medical Knowledge Base Builder

PATTERN: Data pipeline for RAG knowledge base construction
SKILLS: @ultrathink, @api-design-principles, @python-performance-optimization

This service ingests medical literature from multiple sources:
1. ANVISA (Brazilian drug regulatory agency) - Bulas
2. FDA (US Food and Drug Administration) - Drug Labels
3. PubMed (NLM) - Medical literature abstracts
4. DrugBank - Comprehensive drug information
5. Local files (PDFs, TXT, JSON)

REFERENCE: Antonio Gulli "RAG Implementation" Chapter 14, pg 281-310
"""

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from ..config import settings
from ..db.database import get_db_context
from ..db.models import Document, IngestJob
from ..db.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """Supported data sources for ingestion"""

    ANVISA = "anvisa"
    FDA = "fda"
    PUBMED = "pubmed"
    DRUGBANK = "drugbank"
    LOCAL_FILE = "local_file"
    CUSTOM_URL = "custom_url"


@dataclass
class MedicalDocument:
    """
    Structured medical document for ingestion

    SKILL: @ultrathink - Type-safe document representation
    """

    drug_name: str
    section: str  # e.g., "contraindications", "interactions", "warnings"
    text: str
    source: str  # ANVISA, FDA, PubMed, etc.
    source_url: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

        # Normalize drug name
        self.drug_name = self.drug_name.lower().strip()
        self.section = self.section.lower().strip()

        # Add document hash for deduplication
        self.metadata["doc_hash"] = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute content hash for deduplication"""
        content = f"{self.drug_name}:{self.section}:{self.text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for vector store"""
        return {
            "drug_name": self.drug_name,
            "section": self.section,
            "text": self.text,
            "source": self.source,
            "metadata": {
                **self.metadata,
                "drug_name": self.drug_name,
                "section": self.section,
                "source": self.source,
                "source_url": self.source_url,
            },
        }


class LiteratureIngestionService:
    """
    Service for ingesting medical literature into vector store

    ARCHITECTURE: Pipeline pattern with pluggable data sources
    PATTERN: Extract → Transform → Load (ETL)

    SKILLS APPLIED:
    - @ultrathink: Clean ETL pipeline abstraction
    - @api-design-principles: Extensible source adapters
    - @python-performance-optimization: Batch processing
    """

    def __init__(self):
        """Initialize ingestion service"""
        self.vector_store = get_vector_store()
        self.http_client = httpx.Client(timeout=30.0)
        self.processed_hashes = set()  # For deduplication in session

        logger.info("LiteratureIngestionService initialized")

    def ingest_from_source(
        self,
        source: DataSource,
        query: Optional[str] = None,
        max_results: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Ingest documents from a specific source

        PATTERN: Strategy pattern for different sources

        Args:
            source: Data source to ingest from
            query: Search query (for ANVISA, FDA, PubMed)
            max_results: Maximum number of documents to ingest
            **kwargs: Source-specific parameters

        Returns:
            Ingestion result with stats
        """
        try:
            logger.info(f"📥 Starting ingestion from {source.value}")
            start_time = datetime.now()

            # Create ingestion job
            job = self._create_ingest_job(source, query, max_results)

            # Dispatch to appropriate ingester
            if source == DataSource.ANVISA:
                documents = self._ingest_anvisa(query, max_results)
            elif source == DataSource.FDA:
                documents = self._ingest_fda(query, max_results)
            elif source == DataSource.PUBMED:
                documents = self._ingest_pubmed(query, max_results)
            elif source == DataSource.DRUGBANK:
                documents = self._ingest_drugbank(query, max_results)
            elif source == DataSource.LOCAL_FILE:
                file_path = kwargs.get("file_path")
                documents = self._ingest_local_file(file_path)
            elif source == DataSource.CUSTOM_URL:
                url = kwargs.get("url")
                documents = self._ingest_custom_url(url)
            else:
                raise ValueError(f"Unsupported source: {source}")

            # Deduplicate
            unique_documents = self._deduplicate(documents)

            # Add to vector store
            if unique_documents:
                chunks_created = self.vector_store.add_documents(
                    [doc.to_dict() for doc in unique_documents]
                )
            else:
                chunks_created = 0

            # Update job
            duration = (datetime.now() - start_time).total_seconds()
            result = {
                "job_id": str(job.id),
                "source": source.value,
                "query": query,
                "total_fetched": len(documents),
                "unique_documents": len(unique_documents),
                "chunks_created": chunks_created,
                "duration_seconds": duration,
                "status": "completed",
            }

            self._update_ingest_job(job, result)

            logger.info(
                f"Ingestion completed: {len(unique_documents)} docs, "
                f"{chunks_created} chunks in {duration:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
            }

    def _ingest_anvisa(self, query: str, max_results: int) -> List[MedicalDocument]:
        """
        Ingest documents from ANVISA (Brazilian drug regulatory agency)

        NOTE: This is a placeholder implementation. Real ANVISA scraping
        requires handling their website structure and rate limiting.

        PATTERN: Web scraping with BeautifulSoup
        """
        logger.info(f"🇧🇷 Ingesting from ANVISA: query='{query}', max={max_results}")

        documents = []

        # PLACEHOLDER: In production, implement actual ANVISA scraping
        # For now, return example structure
        logger.warning(
            " ANVISA ingestion not fully implemented. "
            "This requires scraping https://consultas.anvisa.gov.br/ "
            "or using ANVISA's official API if available."
        )

        # Example document structure (would come from actual scraping)
        example_doc = MedicalDocument(
            drug_name=query or "example_drug",
            section="bula_completa",
            text="Conteúdo da bula ANVISA aqui...",
            source="ANVISA",
            source_url="https://consultas.anvisa.gov.br/#/medicamentos/...",
            metadata={
                "country": "BR",
                "regulatory_agency": "ANVISA",
                "document_type": "bula",
            },
        )

        # documents.append(example_doc)  # Uncomment when implementing

        return documents

    def _ingest_fda(self, query: str, max_results: int) -> List[MedicalDocument]:
        """
        Ingest drug labels from FDA OpenFDA API

        API: https://open.fda.gov/apis/drug/label/
        PATTERN: REST API integration

        REFERENCE: https://open.fda.gov/apis/drug/label/
        """
        logger.info(f"🇺🇸 Ingesting from FDA: query='{query}', max={max_results}")

        documents = []

        try:
            # FDA OpenFDA API endpoint
            url = "https://api.fda.gov/drug/label.json"

            params = {
                "search": f'openfda.brand_name:"{query}"',
                "limit": min(max_results, 100),  # FDA limit is 100
            }

            response = self.http_client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            logger.info(f"   FDA returned {len(results)} results")

            for result in results:
                # Extract drug name
                brand_names = result.get("openfda", {}).get("brand_name", [])
                drug_name = brand_names[0] if brand_names else query

                # Extract sections
                sections_map = {
                    "contraindications": result.get("contraindications", []),
                    "warnings": result.get("warnings", []),
                    "drug_interactions": result.get("drug_interactions", []),
                    "adverse_reactions": result.get("adverse_reactions", []),
                    "dosage_and_administration": result.get(
                        "dosage_and_administration", []
                    ),
                }

                for section_name, section_content in sections_map.items():
                    if section_content:
                        text = (
                            "\n".join(section_content)
                            if isinstance(section_content, list)
                            else section_content
                        )

                        if text.strip():
                            doc = MedicalDocument(
                                drug_name=drug_name,
                                section=section_name,
                                text=text,
                                source="FDA",
                                source_url=f"https://www.accessdata.fda.gov/scripts/cder/daf/",
                                metadata={
                                    "country": "US",
                                    "regulatory_agency": "FDA",
                                    "document_type": "drug_label",
                                },
                            )
                            documents.append(doc)

            logger.info(f"   Created {len(documents)} documents from FDA")

        except Exception as e:
            logger.error(f"FDA ingestion failed: {e}")

        return documents

    def _ingest_pubmed(self, query: str, max_results: int) -> List[MedicalDocument]:
        """
        Ingest abstracts from PubMed (NLM E-utilities API)

        API: https://www.ncbi.nlm.nih.gov/books/NBK25501/
        PATTERN: Two-step API (search → fetch)

        REFERENCE: PubMed E-utilities documentation
        """
        logger.info(f"📚 Ingesting from PubMed: query='{query}', max={max_results}")

        documents = []

        try:
            # Step 1: Search for article IDs
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                "db": "pubmed",
                "term": f'{query}[Title/Abstract] AND "drug interactions"[MeSH Terms]',
                "retmax": max_results,
                "retmode": "json",
            }

            response = self.http_client.get(search_url, params=search_params)
            response.raise_for_status()

            search_data = response.json()
            pmids = search_data.get("esearchresult", {}).get("idlist", [])

            logger.info(f"   PubMed search returned {len(pmids)} article IDs")

            if not pmids:
                return documents

            # Step 2: Fetch article details
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
            }

            response = self.http_client.get(fetch_url, params=fetch_params)
            response.raise_for_status()

            # Parse XML (simplified - in production, use proper XML parsing)
            soup = BeautifulSoup(response.text, "xml")
            articles = soup.find_all("PubmedArticle")

            for article in articles:
                # Extract title
                title_elem = article.find("ArticleTitle")
                title = title_elem.text if title_elem else "Untitled"

                # Extract abstract
                abstract_elem = article.find("AbstractText")
                abstract = abstract_elem.text if abstract_elem else ""

                # Extract PMID
                pmid_elem = article.find("PMID")
                pmid = pmid_elem.text if pmid_elem else "unknown"

                if abstract:
                    doc = MedicalDocument(
                        drug_name=query,
                        section="research_abstract",
                        text=f"{title}\n\n{abstract}",
                        source="PubMed",
                        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        metadata={
                            "pmid": pmid,
                            "title": title,
                            "document_type": "research_abstract",
                        },
                    )
                    documents.append(doc)

            logger.info(f"   Created {len(documents)} documents from PubMed")

        except Exception as e:
            logger.error(f"PubMed ingestion failed: {e}")

        return documents

    def _ingest_drugbank(self, query: str, max_results: int) -> List[MedicalDocument]:
        """
        Ingest from DrugBank

        NOTE: DrugBank requires API key and subscription
        This is a placeholder for future implementation

        REFERENCE: https://docs.drugbank.com/
        """
        logger.warning(
            " DrugBank ingestion requires API key. "
            "Sign up at https://go.drugbank.com/releases/latest"
        )
        return []

    def _ingest_local_file(self, file_path: str) -> List[MedicalDocument]:
        """
        Ingest from local file (JSON, TXT, PDF)

        PATTERN: File format dispatch

        Args:
            file_path: Path to local file

        Returns:
            List of documents
        """
        logger.info(f"📁 Ingesting local file: {file_path}")

        documents = []
        path = Path(file_path)

        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return documents

        try:
            if path.suffix == ".json":
                documents = self._ingest_json_file(path)
            elif path.suffix == ".txt":
                documents = self._ingest_text_file(path)
            elif path.suffix == ".pdf":
                documents = self._ingest_pdf_file(path)
            else:
                logger.warning(f" Unsupported file format: {path.suffix}")

            logger.info(f"   Loaded {len(documents)} documents from {path.name}")

        except Exception as e:
            logger.error(f"Failed to ingest file: {e}")

        return documents

    def _ingest_json_file(self, path: Path) -> List[MedicalDocument]:
        """Ingest from JSON file"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        documents = []

        # Support both single doc and list of docs
        if isinstance(data, list):
            docs_data = data
        else:
            docs_data = [data]

        for doc_data in docs_data:
            doc = MedicalDocument(
                drug_name=doc_data.get("drug_name", "unknown"),
                section=doc_data.get("section", "general"),
                text=doc_data.get("text", doc_data.get("content", "")),
                source=doc_data.get("source", "local_file"),
                source_url=doc_data.get("url", ""),
                metadata=doc_data.get("metadata", {}),
            )
            documents.append(doc)

        return documents

    def _ingest_text_file(self, path: Path) -> List[MedicalDocument]:
        """Ingest from plain text file"""
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        # Try to extract drug name from filename
        drug_name = path.stem.replace("_", " ").replace("-", " ")

        doc = MedicalDocument(
            drug_name=drug_name,
            section="general",
            text=text,
            source="local_file",
            source_url=str(path),
            metadata={"filename": path.name},
        )

        return [doc]

    def _ingest_pdf_file(self, path: Path) -> List[MedicalDocument]:
        """
        Ingest from PDF file

        NOTE: Requires PyPDF2 or pdfplumber
        This is a placeholder for future implementation
        """
        logger.warning(" PDF ingestion requires PyPDF2 or pdfplumber installation")

        # PLACEHOLDER: Install PyPDF2 or pdfplumber and implement
        # from PyPDF2 import PdfReader
        # reader = PdfReader(path)
        # text = '\n'.join([page.extract_text() for page in reader.pages])

        return []

    def _ingest_custom_url(self, url: str) -> List[MedicalDocument]:
        """
        Ingest from custom URL

        PATTERN: Generic web scraping

        Args:
            url: URL to scrape

        Returns:
            List of documents
        """
        logger.info(f"🌐 Ingesting from URL: {url}")

        documents = []

        try:
            response = self.http_client.get(url)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract text (basic implementation)
            text = soup.get_text(separator="\n", strip=True)

            # Try to extract drug name from title or URL
            title = soup.find("title")
            drug_name = title.text if title else Path(url).stem

            doc = MedicalDocument(
                drug_name=drug_name,
                section="web_content",
                text=text,
                source="custom_url",
                source_url=url,
                metadata={"url": url},
            )

            documents.append(doc)

        except Exception as e:
            logger.error(f"Failed to ingest URL: {e}")

        return documents

    def _deduplicate(self, documents: List[MedicalDocument]) -> List[MedicalDocument]:
        """
        Remove duplicate documents based on content hash

        SKILL: @python-performance-optimization - Efficient deduplication
        """
        unique_docs = []
        seen_hashes = set()

        for doc in documents:
            doc_hash = doc.metadata.get("doc_hash")
            if doc_hash and doc_hash not in seen_hashes:
                seen_hashes.add(doc_hash)
                unique_docs.append(doc)

        duplicates_removed = len(documents) - len(unique_docs)
        if duplicates_removed > 0:
            logger.info(f"   Removed {duplicates_removed} duplicate documents")

        return unique_docs

    def _create_ingest_job(
        self, source: DataSource, query: Optional[str], max_results: int
    ) -> IngestJob:
        """Create ingestion job record in database"""
        with get_db_context() as db:
            job = IngestJob(
                source=source.value,
                data_type="medical_literature",
                query=query,
                max_results=max_results,
                status="running",
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            return job

    def _update_ingest_job(self, job: IngestJob, result: Dict[str, Any]):
        """Update ingestion job with results"""
        with get_db_context() as db:
            job.status = result.get("status", "completed")
            job.total_processed = result.get("total_fetched", 0)
            job.successful = result.get("unique_documents", 0)
            job.processing_time = result.get("duration_seconds", 0.0)

            db.add(job)
            db.commit()

    def bulk_ingest_drugs(
        self,
        drug_names: List[str],
        sources: List[DataSource],
        max_results_per_drug: int = 10,
    ) -> Dict[str, Any]:
        """
        Bulk ingest multiple drugs from multiple sources

        PATTERN: Batch processing for efficiency

        Args:
            drug_names: List of drug names to ingest
            sources: List of sources to query
            max_results_per_drug: Max results per drug per source

        Returns:
            Aggregated results
        """
        logger.info(
            f"📥 Bulk ingestion: {len(drug_names)} drugs × {len(sources)} sources"
        )

        results = {
            "total_drugs": len(drug_names),
            "total_sources": len(sources),
            "per_drug_results": {},
            "aggregated": {
                "total_documents": 0,
                "total_chunks": 0,
                "duration_seconds": 0.0,
            },
        }

        start_time = datetime.now()

        for drug_name in drug_names:
            drug_results = []

            for source in sources:
                try:
                    result = self.ingest_from_source(
                        source=source, query=drug_name, max_results=max_results_per_drug
                    )
                    drug_results.append(result)

                    # Aggregate
                    results["aggregated"]["total_documents"] += result.get(
                        "unique_documents", 0
                    )
                    results["aggregated"]["total_chunks"] += result.get(
                        "chunks_created", 0
                    )

                except Exception as e:
                    logger.error(f"Failed to ingest {drug_name} from {source}: {e}")

            results["per_drug_results"][drug_name] = drug_results

        results["aggregated"]["duration_seconds"] = (
            datetime.now() - start_time
        ).total_seconds()

        logger.info(
            f"Bulk ingestion completed: "
            f"{results['aggregated']['total_documents']} docs, "
            f"{results['aggregated']['total_chunks']} chunks"
        )

        return results


# Singleton instance
_ingestion_service: Optional[LiteratureIngestionService] = None


def get_ingestion_service() -> LiteratureIngestionService:
    """Get or create singleton ingestion service"""
    global _ingestion_service

    if _ingestion_service is None:
        _ingestion_service = LiteratureIngestionService()

    return _ingestion_service
