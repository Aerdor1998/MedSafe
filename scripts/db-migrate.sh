#!/bin/bash

# =============================================================================
# MedSafe - Database Migration Script
# DEPLOY_ROADMAP Section 4: Run migrations outside runtime
# =============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

cd "$PROJECT_DIR"

# Detect docker compose command
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# =============================================================================
# MIGRATION FUNCTIONS
# =============================================================================

run_migration() {
    log_info "Running database migrations..."

    # Check if database is ready
    log_info "Waiting for database..."
    $DOCKER_COMPOSE -f "$COMPOSE_FILE" exec -T db pg_isready -U medsafe || {
        log_error "Database is not ready!"
        exit 1
    }

    # Run alembic migrations
    log_info "Applying migrations with alembic..."
    $DOCKER_COMPOSE -f "$COMPOSE_FILE" run --rm api alembic upgrade head

    log_info "Migrations completed!"
}

show_current() {
    log_info "Current migration status:"
    $DOCKER_COMPOSE -f "$COMPOSE_FILE" run --rm api alembic current
}

show_history() {
    log_info "Migration history:"
    $DOCKER_COMPOSE -f "$COMPOSE_FILE" run --rm api alembic history
}

create_migration() {
    local message="$1"

    if [ -z "$message" ]; then
        log_error "Usage: $0 create \"migration message\""
        exit 1
    fi

    log_info "Creating new migration: $message"
    $DOCKER_COMPOSE -f "$COMPOSE_FILE" run --rm api alembic revision --autogenerate -m "$message"
}

downgrade() {
    local target="${1:--1}"

    log_warn "This will downgrade the database to: $target"
    read -p "Are you sure? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Downgrade cancelled."
        exit 0
    fi

    log_info "Downgrading to: $target"
    $DOCKER_COMPOSE -f "$COMPOSE_FILE" run --rm api alembic downgrade "$target"

    log_info "Downgrade completed!"
}

# =============================================================================
# MAIN
# =============================================================================

case "${1:-upgrade}" in
    upgrade|up)
        run_migration
        ;;
    current|status)
        show_current
        ;;
    history)
        show_history
        ;;
    create)
        create_migration "$2"
        ;;
    downgrade|down)
        downgrade "$2"
        ;;
    *)
        echo "Usage: $0 {upgrade|current|history|create|downgrade}"
        echo ""
        echo "Commands:"
        echo "  upgrade         Apply all pending migrations (default)"
        echo "  current         Show current migration version"
        echo "  history         Show migration history"
        echo "  create <msg>    Create a new migration"
        echo "  downgrade [rev] Downgrade to a specific revision (-1 by default)"
        echo ""
        echo "Environment variables:"
        echo "  COMPOSE_FILE    Docker compose file (default: docker-compose.prod.yml)"
        exit 1
        ;;
esac
