-- MedSafe - Postgres init script (docker-entrypoint-initdb.d)
--
-- Runs once, automatically, only when the postgres_data volume is empty
-- (first container start). Alembic migration
-- alembic/versions/20251127_1800_001_init_pgvector_and_tables.py already
-- runs `CREATE EXTENSION IF NOT EXISTS vector` and creates all application
-- tables, so this script is intentionally minimal: it just guarantees the
-- pgvector extension exists as early as possible, idempotently, without
-- duplicating schema ownership that belongs to Alembic.
CREATE EXTENSION IF NOT EXISTS vector;
