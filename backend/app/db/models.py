"""
Modelos SQLAlchemy para o MedSafe
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from .database import Base

# Importação condicional de tipos PostgreSQL
try:
    from sqlalchemy.dialects.postgresql import UUID
    from pgvector.sqlalchemy import Vector as VECTOR

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

    # Para SQLite, usar String para UUIDs
    def UUID(as_uuid=False):
        return String(36)

    VECTOR = None

# Determinar qual tipo UUID usar baseado no engine
import os

USE_POSTGRES = "postgresql" in os.getenv("DATABASE_URL", "")


class Triage(Base):
    """Modelo para triagem de pacientes"""

    __tablename__ = "triage"

    # UUID: usar UUID nativo do PostgreSQL ou String para SQLite
    id = Column(
        UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36),
        primary_key=True,
        default=uuid.uuid4 if not USE_POSTGRES else None,
    )
    user_id = Column(String, nullable=True, index=True)

    # Dados demográficos
    age = Column(Integer, nullable=False)
    weight = Column(Float, nullable=True)
    pregnant = Column(Boolean, default=False)

    # Comorbidades e medicamentos
    cid_codes = Column(JSON, default=list)
    meds_in_use = Column(JSON, default=list)
    allergies = Column(JSON, default=list)

    # Função renal e hepática
    renal_function = Column(JSON, nullable=True)
    hepatic_function = Column(JSON, nullable=True)

    # Notas e status
    notes = Column(Text, nullable=True)
    status = Column(String, default="pending")
    job_id = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # LGPD: Soft delete para compliance
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(36), nullable=True)
    deletion_reason = Column(String(255), nullable=True)

    # Relacionamentos
    # Fase 1.5 (N+1): prefer selectin loading for collections
    reports = relationship("Report", back_populates="triage", lazy="selectin")

    def __repr__(self):
        return f"<Triage(id={self.id}, age={self.age}, status={self.status})>"


class Report(Base):
    """Modelo para relatórios de análise"""

    __tablename__ = "reports"

    id = Column(
        UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36),
        primary_key=True,
        default=uuid.uuid4 if not USE_POSTGRES else None,
    )
    triage_id = Column(
        UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36), ForeignKey("triage.id"), nullable=False
    )
    vision_id = Column(UUID(as_uuid=True), nullable=True)

    # Resultados da análise
    risk_level = Column(String, nullable=False, index=True)
    contraindications = Column(JSON, default=list)
    interactions = Column(JSON, default=list)
    dosage_adjustments = Column(JSON, default=list)
    adverse_reactions = Column(JSON, default=list)
    evidence_links = Column(JSON, default=list)

    # Metadados
    model_used = Column(String, nullable=False)
    confidence_score = Column(Float, nullable=True)
    analysis_notes = Column(Text, nullable=True)
    status = Column(String, default="draft")
    is_final = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # LGPD: Soft delete para compliance
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(36), nullable=True)

    # Relacionamentos
    # Fase 1.5 (N+1): prefer selectin loading for many-to-one
    triage = relationship("Triage", back_populates="reports", lazy="selectin")

    def __repr__(self):
        return f"<Report(id={self.id}, triage_id={self.triage_id}, risk_level={self.risk_level})>"


class Document(Base):
    """Modelo para documentos (bulas, datasets)"""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36), primary_key=True, default=uuid.uuid4)

    # Metadados do documento
    source = Column(String, nullable=False, index=True)  # ANVISA, SIDER, DrugCentral
    source_url = Column(String, nullable=True)
    drug_name = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False, index=True)  # contraindicações, advertências, etc.

    # Conteúdo
    text = Column(Text, nullable=False)
    meta = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # LGPD: Soft delete para compliance
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    # Fase 1.5 (N+1): prefer selectin loading for collections
    embeddings = relationship("Embedding", back_populates="document", lazy="selectin")

    def __repr__(self):
        return f"<Document(id={self.id}, drug_name={self.drug_name}, section={self.section})>"


class Embedding(Base):
    """Modelo para embeddings de documentos (pgvector)"""

    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36), ForeignKey("documents.id"), nullable=False
    )

    # Vetor de embedding (pgvector ou Text para SQLite)
    if POSTGRES_AVAILABLE and VECTOR:
        vector = Column(VECTOR(1024), nullable=False)  # Dimensão configurável
    else:
        # Para SQLite, armazenar como JSON text
        vector = Column(Text, nullable=False)  # Serializado como JSON

    # Metadados do chunk
    chunk_idx = Column(Integer, nullable=False)
    meta = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    # Fase 1.5 (N+1): prefer selectin loading for many-to-one
    document = relationship("Document", back_populates="embeddings", lazy="selectin")

    def __repr__(self):
        return f"<Embedding(id={self.id}, document_id={self.document_id}, chunk_idx={self.chunk_idx})>"


class IngestJob(Base):
    """Modelo para jobs de ingestão de dados"""

    __tablename__ = "ingest_jobs"

    id = Column(UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36), primary_key=True, default=uuid.uuid4)

    # Configuração da ingestão
    source = Column(String, nullable=False, index=True)
    data_type = Column(String, nullable=False)
    query = Column(String, nullable=True)
    max_results = Column(Integer, nullable=True)

    # URLs e arquivos
    urls = Column(JSON, default=list)
    file_paths = Column(JSON, default=list)

    # Configurações
    force_reprocess = Column(Boolean, default=False)
    chunk_size = Column(Integer, nullable=True)

    # Status e progresso
    status = Column(String, default="pending")  # pending, running, completed, failed
    progress = Column(Float, default=0.0)
    current_step = Column(String, nullable=True)
    estimated_completion = Column(DateTime(timezone=True), nullable=True)

    # Resultados
    total_processed = Column(Integer, default=0)
    successful = Column(Integer, default=0)
    failed = Column(Integer, default=0)

    # Detalhes e erros
    processed_items = Column(JSON, default=list)
    errors = Column(JSON, default=list)

    # Metadados
    description = Column(Text, nullable=True)
    tags = Column(JSON, default=list)
    processing_time = Column(Float, nullable=True)
    model_used = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<IngestJob(id={self.id}, source={self.source}, status={self.status})>"


class AnalysisJob(Base):
    """
    Durable analysis job for long-running LangGraph workflows.

    This is the source of truth for:
    - async execution status (pending/running/completed/failed/awaiting_review)
    - last known workflow state (JSON) for status polling and HITL resume
    - error details and retry counters
    """

    __tablename__ = "analysis_jobs"

    id = Column(
        UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36),
        primary_key=True,
        default=uuid.uuid4 if not USE_POSTGRES else None,
    )

    # Identifiers
    session_id = Column(String, nullable=False, unique=True, index=True)
    triage_id = Column(UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36), ForeignKey("triage.id"), nullable=True, index=True)
    user_id = Column(String, nullable=True, index=True)

    # Status lifecycle
    status = Column(String, default="pending", index=True)
    retries = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Payload and state
    payload = Column(JSON, default=dict)  # request snapshot used by worker
    state = Column(JSON, default=dict)  # latest workflow state (for status + HITL)

    # Error details
    last_error = Column(Text, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # LGPD: Soft delete para compliance
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<AnalysisJob(id={self.id}, session_id={self.session_id}, status={self.status})>"


class HITLReview(Base):
    """Audit log for Human-in-the-Loop (HITL) decisions."""

    __tablename__ = "hitl_reviews"

    id = Column(
        UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36),
        primary_key=True,
        default=uuid.uuid4 if not USE_POSTGRES else None,
    )

    session_id = Column(String, nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36), ForeignKey("analysis_jobs.id"), nullable=True, index=True)
    triage_id = Column(UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36), ForeignKey("triage.id"), nullable=True, index=True)

    reviewer_id = Column(String, nullable=False, index=True)
    approved = Column(Boolean, nullable=False)
    physician_notes = Column(Text, nullable=True)
    modifications = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # LGPD: Soft delete para compliance (auditoria médica)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<HITLReview(id={self.id}, session_id={self.session_id}, approved={self.approved})>"


class DrugInteraction(Base):
    """
    Persisted drug interactions table (migrated from CSV).

    This is optimized for lookup by canonical drug pair:
    - drug_a_norm + drug_b_norm are canonical, sorted keys for indexing
    """

    __tablename__ = "drug_interactions"

    id = Column(
        UUID(as_uuid=True) if POSTGRES_AVAILABLE else String(36),
        primary_key=True,
        default=uuid.uuid4 if not USE_POSTGRES else None,
    )

    drug_a = Column(String, nullable=False)
    drug_b = Column(String, nullable=False)
    drug_a_norm = Column(String, nullable=False, index=True)
    drug_b_norm = Column(String, nullable=False, index=True)

    interaction_type = Column(String, nullable=True)
    severity = Column(String, nullable=True, index=True)
    mechanism = Column(Text, nullable=True)
    clinical_effect = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    source = Column(String, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<DrugInteraction(id={self.id}, a={self.drug_a_norm}, b={self.drug_b_norm}, severity={self.severity})>"


# Índices adicionais para otimização
Index("idx_documents_source_drug", Document.source, Document.drug_name)
Index("idx_embeddings_document_chunk", Embedding.document_id, Embedding.chunk_idx)
Index("idx_ingest_jobs_status_created", IngestJob.status, IngestJob.created_at)
Index("idx_analysis_jobs_status_created", AnalysisJob.status, AnalysisJob.created_at)
Index("idx_hitl_reviews_created", HITLReview.created_at)
Index("idx_drug_interactions_pair", DrugInteraction.drug_a_norm, DrugInteraction.drug_b_norm)
