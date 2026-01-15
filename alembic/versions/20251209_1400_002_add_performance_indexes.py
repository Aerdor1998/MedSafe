"""Add performance indexes for optimization

Revision ID: 002
Revises: 001
Create Date: 2025-12-09 14:00:00.000000

This migration adds additional indexes recommended by the optimization framework:
1. Composite indexes for common query patterns
2. Partial indexes for filtered queries
3. GIN indexes for JSON columns

PATTERN: Performance optimization via strategic indexing
SKILLS: @prometheus-configuration, @python-performance-optimization
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add performance-optimized indexes based on query patterns analysis

    These indexes are designed to optimize:
    1. Triage queries by status and date
    2. Reports queries by risk level and triage
    3. Document queries for RAG retrieval
    4. JSON field queries for medical data
    """
    print("Adding performance indexes...")

    # ===================================================================
    # TRIAGE TABLE INDEXES
    # ===================================================================

    # Composite index for status + created_at (common filter pattern)
    print("Creating idx_triage_status_created...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_triage_status_created
        ON triage (status, created_at DESC)
    """)

    # Partial index for pending triages only (HITL queue)
    print("Creating idx_triage_pending_hitl...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_triage_pending_hitl
        ON triage (created_at DESC)
        WHERE status = 'pending'
    """)

    # Partial index for completed triages
    print("Creating idx_triage_completed...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_triage_completed
        ON triage (created_at DESC)
        WHERE status = 'completed'
    """)

    # ===================================================================
    # REPORTS TABLE INDEXES
    # ===================================================================

    # Composite index for triage + risk level (common join pattern)
    print("Creating idx_reports_triage_risk...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_reports_triage_risk
        ON reports (triage_id, risk_level)
    """)

    # Partial index for critical/high risk reports (alerts)
    print("Creating idx_reports_high_risk...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_reports_high_risk
        ON reports (created_at DESC)
        WHERE risk_level IN ('critical', 'high')
    """)

    # Index for confidence score filtering
    print("Creating idx_reports_confidence...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_reports_confidence
        ON reports (confidence_score DESC)
        WHERE confidence_score IS NOT NULL
    """)

    # ===================================================================
    # DOCUMENTS TABLE INDEXES
    # ===================================================================

    # Composite index for drug + section (RAG retrieval pattern)
    print("Creating idx_documents_drug_section...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_drug_section
        ON documents (drug_name, section)
    """)

    # Full-text search index for document text (PostgreSQL specific)
    print("Creating idx_documents_text_search...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_text_search
        ON documents USING GIN (to_tsvector('portuguese', text))
    """)

    # ===================================================================
    # EMBEDDINGS TABLE INDEXES
    # ===================================================================

    # Index for document_id foreign key (faster joins)
    print("Creating idx_embeddings_document_id...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_document_id
        ON embeddings (document_id)
    """)

    # ===================================================================
    # INGEST JOBS TABLE INDEXES
    # ===================================================================

    # Composite index for source + status (job monitoring)
    print("Creating idx_ingest_jobs_source_status...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ingest_jobs_source_status
        ON ingest_jobs (source, status)
    """)

    # Partial index for running jobs (dashboard monitoring)
    print("Creating idx_ingest_jobs_running...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ingest_jobs_running
        ON ingest_jobs (created_at DESC)
        WHERE status = 'running'
    """)

    print("All performance indexes created successfully!")


def downgrade() -> None:
    """
    Remove performance indexes

    Note: This only removes the indexes added in this migration,
    not the original indexes from migration 001
    """
    print("Removing performance indexes...")

    # Triage indexes
    op.execute("DROP INDEX IF EXISTS idx_triage_status_created")
    op.execute("DROP INDEX IF EXISTS idx_triage_pending_hitl")
    op.execute("DROP INDEX IF EXISTS idx_triage_completed")

    # Reports indexes
    op.execute("DROP INDEX IF EXISTS idx_reports_triage_risk")
    op.execute("DROP INDEX IF EXISTS idx_reports_high_risk")
    op.execute("DROP INDEX IF EXISTS idx_reports_confidence")

    # Documents indexes
    op.execute("DROP INDEX IF EXISTS idx_documents_drug_section")
    op.execute("DROP INDEX IF EXISTS idx_documents_text_search")

    # Embeddings indexes
    op.execute("DROP INDEX IF EXISTS idx_embeddings_document_id")

    # Ingest jobs indexes
    op.execute("DROP INDEX IF EXISTS idx_ingest_jobs_source_status")
    op.execute("DROP INDEX IF EXISTS idx_ingest_jobs_running")

    print("All performance indexes removed!")
