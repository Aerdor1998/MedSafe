-- Performance Optimization Indexes for MedSafe
-- Generated: 2025-11-28
-- Estimated Performance Improvement: 30-50% faster queries
--
-- These indexes are based on analysis from the Multi-Agent Optimization Report
-- See: docs/optimization/MULTI_AGENT_OPTIMIZATION_REPORT.md

-- ============================================================================
-- TABLE: triage
-- ============================================================================

-- Index on status for filtering pending/completed triages
-- Query pattern: SELECT * FROM triage WHERE status = 'pending'
CREATE INDEX IF NOT EXISTS idx_triage_status
ON triage(status);

-- Index on user_id for user-specific queries
-- Note: Already indexed in models.py, but ensuring it exists
CREATE INDEX IF NOT EXISTS idx_triage_user_id
ON triage(user_id);

-- Index on created_at for time-based queries and sorting
-- Query pattern: SELECT * FROM triage WHERE created_at > NOW() - INTERVAL '7 days'
CREATE INDEX IF NOT EXISTS idx_triage_created_at
ON triage(created_at DESC);

-- Composite index for common query pattern: user + status
-- Query pattern: SELECT * FROM triage WHERE user_id = ? AND status = ?
CREATE INDEX IF NOT EXISTS idx_triage_user_status
ON triage(user_id, status);

-- ============================================================================
-- TABLE: reports
-- ============================================================================

-- Composite index on triage_id + risk_level
-- Query pattern: SELECT * FROM reports WHERE triage_id = ? ORDER BY risk_level
-- This is critical for joining triage → report and filtering by risk
CREATE INDEX IF NOT EXISTS idx_reports_triage_risk
ON reports(triage_id, risk_level);

-- Index on risk_level for risk-based filtering
-- Query pattern: SELECT * FROM reports WHERE risk_level = 'critical'
CREATE INDEX IF NOT EXISTS idx_reports_risk_level
ON reports(risk_level);

-- Index on is_final for filtering final reports
-- Query pattern: SELECT * FROM reports WHERE is_final = true
CREATE INDEX IF NOT EXISTS idx_reports_is_final
ON reports(is_final);

-- Index on created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_reports_created_at
ON reports(created_at DESC);

-- ============================================================================
-- TABLE: documents
-- ============================================================================

-- Composite index on drug_name + section
-- Query pattern: SELECT * FROM documents WHERE drug_name = ? AND section = ?
-- This is critical for RAG document retrieval
CREATE INDEX IF NOT EXISTS idx_documents_drug_section
ON documents(drug_name, section);

-- Index on source for filtering by data source
-- Query pattern: SELECT * FROM documents WHERE source = 'FDA'
CREATE INDEX IF NOT EXISTS idx_documents_source
ON documents(source);

-- Full-text search index on text field (PostgreSQL GIN index)
-- Query pattern: SELECT * FROM documents WHERE text ILIKE '%interaction%'
CREATE INDEX IF NOT EXISTS idx_documents_text_gin
ON documents USING gin(to_tsvector('english', text));

-- ============================================================================
-- TABLE: embeddings
-- ============================================================================

-- Index on document_id for joining embeddings → documents
-- Note: Already has foreign key, but explicit index improves performance
CREATE INDEX IF NOT EXISTS idx_embeddings_document
ON embeddings(document_id);

-- Index on chunk_idx for ordering chunks
-- Query pattern: SELECT * FROM embeddings WHERE document_id = ? ORDER BY chunk_idx
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_idx
ON embeddings(chunk_idx);

-- ============================================================================
-- VECTOR INDEXES (pgvector specific)
-- ============================================================================

-- HNSW index for fast approximate nearest neighbor search
-- This is CRITICAL for RAG performance with pgvector
-- HNSW is faster than IVFFlat for most use cases
--
-- NOTE: This index is created only if pgvector extension is installed
-- and the vector column exists (dimension 1024)
--
-- Query pattern: SELECT * FROM embeddings ORDER BY vector <=> ? LIMIT 5
DO $$
BEGIN
    -- Check if pgvector extension exists
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        -- Create HNSW index for cosine distance
        -- m=16: number of connections per layer (trade-off between speed/accuracy)
        -- ef_construction=64: size of dynamic candidate list during construction
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_embeddings_vector_hnsw
                 ON embeddings USING hnsw (vector vector_cosine_ops)
                 WITH (m = 16, ef_construction = 64)';

        RAISE NOTICE 'Created HNSW vector index for fast semantic search';
    ELSE
        RAISE NOTICE 'pgvector extension not found, skipping vector index creation';
    END IF;
END$$;

-- ============================================================================
-- ANALYZE TABLES
-- ============================================================================

-- Update table statistics for query planner
-- This helps PostgreSQL choose the best query plans
ANALYZE triage;
ANALYZE reports;
ANALYZE documents;
ANALYZE embeddings;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Show created indexes
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND tablename IN ('triage', 'reports', 'documents', 'embeddings')
ORDER BY tablename, indexname;

-- Show index sizes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
    AND tablename IN ('triage', 'reports', 'documents', 'embeddings')
ORDER BY pg_relation_size(indexrelid) DESC;
