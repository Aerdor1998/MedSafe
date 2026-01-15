"""Initialize pgvector extension and create base tables

Revision ID: 001
Revises:
Create Date: 2025-11-27 18:00:00.000000

This migration:
1. Creates the pgvector extension for vector similarity search
2. Creates all base tables (triage, reports, documents, embeddings, ingest_jobs)
3. Creates necessary indexes for performance
4. Sets up HNSW index for vector similarity search

PATTERN: Database schema initialization with vector support
SKILLS: @ultrathink, @api-design-principles
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade schema: Create pgvector extension and all tables

    CRITICAL: pgvector extension must be created before using Vector type
    """
    # ===================================================================
    # STEP 1: Create pgvector extension
    # ===================================================================
    print("Creating pgvector extension...")
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # ===================================================================
    # STEP 2: Create triage table
    # ===================================================================
    print("Creating triage table...")
    op.create_table(
        'triage',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.String(), nullable=True, index=True),

        # Demographics
        sa.Column('age', sa.Integer(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('pregnant', sa.Boolean(), default=False),

        # Medical data
        sa.Column('cid_codes', postgresql.JSON(), server_default='[]'),
        sa.Column('meds_in_use', postgresql.JSON(), server_default='[]'),
        sa.Column('allergies', postgresql.JSON(), server_default='[]'),
        sa.Column('renal_function', postgresql.JSON(), nullable=True),
        sa.Column('hepatic_function', postgresql.JSON(), nullable=True),

        # Status
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), server_default='pending'),
        sa.Column('job_id', sa.String(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
    )

    # Indexes for triage
    op.create_index('idx_triage_user_id', 'triage', ['user_id'])
    op.create_index('idx_triage_created_at', 'triage', ['created_at'])
    op.create_index('idx_triage_status', 'triage', ['status'])

    # ===================================================================
    # STEP 3: Create reports table
    # ===================================================================
    print("Creating reports table...")
    op.create_table(
        'reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('triage_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('triage.id'), nullable=False),
        sa.Column('vision_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Analysis results
        sa.Column('risk_level', sa.String(), nullable=False, index=True),
        sa.Column('contraindications', postgresql.JSON(), server_default='[]'),
        sa.Column('interactions', postgresql.JSON(), server_default='[]'),
        sa.Column('dosage_adjustments', postgresql.JSON(), server_default='[]'),
        sa.Column('adverse_reactions', postgresql.JSON(), server_default='[]'),
        sa.Column('evidence_links', postgresql.JSON(), server_default='[]'),

        # Metadata
        sa.Column('model_used', sa.String(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('analysis_notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), server_default='draft'),
        sa.Column('is_final', sa.Boolean(), server_default='false'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
    )

    # Indexes for reports
    op.create_index('idx_reports_triage_id', 'reports', ['triage_id'])
    op.create_index('idx_reports_risk_level', 'reports', ['risk_level'])

    # ===================================================================
    # STEP 4: Create documents table
    # ===================================================================
    print("Creating documents table...")
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Document metadata
        sa.Column('source', sa.String(), nullable=False, index=True),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('drug_name', sa.String(), nullable=False, index=True),
        sa.Column('section', sa.String(), nullable=False, index=True),

        # Content
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('meta', postgresql.JSON(), server_default='{}'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
    )

    # Composite index for efficient drug+section queries
    op.create_index('idx_documents_drug_name', 'documents', ['drug_name'])
    op.create_index('idx_documents_section', 'documents', ['section'])
    op.create_index('idx_documents_source_drug', 'documents', ['source', 'drug_name'])

    # ===================================================================
    # STEP 5: Create embeddings table (with pgvector)
    # ===================================================================
    print("Creating embeddings table with vector column...")
    op.create_table(
        'embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),

        # Vector embedding (768-dim for nomic-embed-text)
        # Using pgvector type directly via SQL
        sa.Column('chunk_idx', sa.Integer(), nullable=False),
        sa.Column('meta', postgresql.JSON(), server_default='{}'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    # Add vector column using raw SQL (pgvector type)
    print("Adding vector column to embeddings...")
    op.execute('ALTER TABLE embeddings ADD COLUMN vector vector(768)')

    # Create HNSW index for fast vector similarity search
    # HNSW (Hierarchical Navigable Small World) is the most efficient for high-dim vectors
    print("Creating HNSW index for vector similarity search...")
    op.execute("""
        CREATE INDEX idx_embeddings_vector_hnsw
        ON embeddings
        USING hnsw (vector vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Composite index for document+chunk queries
    op.create_index('idx_embeddings_document_chunk', 'embeddings', ['document_id', 'chunk_idx'])

    # ===================================================================
    # STEP 6: Create ingest_jobs table
    # ===================================================================
    print("Creating ingest_jobs table...")
    op.create_table(
        'ingest_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Job configuration
        sa.Column('source', sa.String(), nullable=False, index=True),
        sa.Column('data_type', sa.String(), nullable=False),
        sa.Column('query', sa.String(), nullable=True),
        sa.Column('max_results', sa.Integer(), nullable=True),
        sa.Column('urls', postgresql.JSON(), server_default='[]'),
        sa.Column('file_paths', postgresql.JSON(), server_default='[]'),

        # Configuration
        sa.Column('force_reprocess', sa.Boolean(), server_default='false'),
        sa.Column('chunk_size', sa.Integer(), nullable=True),

        # Status and progress
        sa.Column('status', sa.String(), server_default='pending'),
        sa.Column('progress', sa.Float(), server_default='0.0'),
        sa.Column('current_step', sa.String(), nullable=True),
        sa.Column('estimated_completion', sa.DateTime(timezone=True), nullable=True),

        # Results
        sa.Column('total_processed', sa.Integer(), server_default='0'),
        sa.Column('successful', sa.Integer(), server_default='0'),
        sa.Column('failed', sa.Integer(), server_default='0'),
        sa.Column('processed_items', postgresql.JSON(), server_default='[]'),
        sa.Column('errors', postgresql.JSON(), server_default='[]'),

        # Metadata
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSON(), server_default='[]'),
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.Column('model_used', sa.String(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
    )

    # Indexes for ingest_jobs
    op.create_index('idx_ingest_jobs_status', 'ingest_jobs', ['status'])
    op.create_index('idx_ingest_jobs_status_created', 'ingest_jobs', ['status', 'created_at'])

    print("All tables and indexes created successfully!")


def downgrade() -> None:
    """
    Downgrade schema: Drop all tables and pgvector extension

    WARNING: This will delete all data!
    """
    print("Dropping all tables...")

    # Drop tables in reverse order (respect foreign keys)
    op.drop_table('ingest_jobs')
    op.drop_table('embeddings')
    op.drop_table('documents')
    op.drop_table('reports')
    op.drop_table('triage')

    # Drop pgvector extension
    print("Dropping pgvector extension...")
    op.execute('DROP EXTENSION IF EXISTS vector CASCADE')

    print("All tables and extension dropped!")
