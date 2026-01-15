#!/bin/bash

# Apply Database Performance Indexes
#
# This script applies performance optimization indexes to the MedSafe database
# Expected improvement: 30-50% faster queries
#
# Usage:
#   ./scripts/apply-db-indexes.sh          # Apply to development DB
#   ./scripts/apply-db-indexes.sh prod     # Apply to production DB

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MIGRATION_FILE="$PROJECT_ROOT/backend/app/db/migrations/001_add_performance_indexes.sql"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}MedSafe - Apply Database Indexes${NC}"
echo -e "${GREEN}======================================${NC}"
echo

# Check if migration file exists
if [ ! -f "$MIGRATION_FILE" ]; then
    echo -e "${RED}❌ Migration file not found: $MIGRATION_FILE${NC}"
    exit 1
fi

# Determine environment
ENV=${1:-dev}

if [ "$ENV" = "prod" ]; then
    echo -e "${YELLOW}⚠️  Production mode${NC}"
    CONTAINER_NAME="medsafe_db_prod"
    DB_NAME="medsafe"
else
    echo -e "${GREEN}📦 Development mode${NC}"
    CONTAINER_NAME="medsafe_db"
    DB_NAME="medsafe"
fi

echo

# Check if Docker container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${YELLOW}⚠️  Container '$CONTAINER_NAME' is not running${NC}"
    echo -e "${YELLOW}   Starting containers...${NC}"

    if [ "$ENV" = "prod" ]; then
        docker-compose -f docker-compose.prod.yml up -d db
    else
        docker-compose up -d db
    fi

    echo -e "${GREEN}✅ Waiting for database to be ready...${NC}"
    sleep 5
fi

echo -e "${GREEN}📊 Current database indexes:${NC}"
docker exec -it $CONTAINER_NAME psql -U medsafe -d $DB_NAME -c "
    SELECT tablename, indexname
    FROM pg_indexes
    WHERE schemaname = 'public'
    AND tablename IN ('triage', 'reports', 'documents', 'embeddings')
    ORDER BY tablename, indexname;
"

echo
echo -e "${YELLOW}🔧 Applying performance indexes...${NC}"
echo

# Apply migration
docker exec -i $CONTAINER_NAME psql -U medsafe -d $DB_NAME < "$MIGRATION_FILE"

if [ $? -eq 0 ]; then
    echo
    echo -e "${GREEN}✅ Indexes applied successfully!${NC}"
    echo
    echo -e "${GREEN}📊 New indexes created:${NC}"
    docker exec -it $CONTAINER_NAME psql -U medsafe -d $DB_NAME -c "
        SELECT
            tablename,
            indexname,
            pg_size_pretty(pg_relation_size(indexrelid)) as size
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
        AND tablename IN ('triage', 'reports', 'documents', 'embeddings')
        ORDER BY pg_relation_size(indexrelid) DESC;
    "

    echo
    echo -e "${GREEN}🎉 Performance optimization complete!${NC}"
    echo -e "${GREEN}   Expected query performance improvement: 30-50%${NC}"
    echo
else
    echo
    echo -e "${RED}❌ Failed to apply indexes${NC}"
    exit 1
fi
