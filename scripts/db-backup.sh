#!/bin/bash

# =============================================================================
# MedSafe - Database Backup Script
# DEPLOY_ROADMAP Section 4: Database backups
# =============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
CONTAINER_NAME="${DB_CONTAINER:-medsafe_db}"
DB_USER="${POSTGRES_USER:-medsafe}"
DB_NAME="${POSTGRES_DB:-medsafe}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# BACKUP FUNCTION
# =============================================================================

backup_database() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="medsafe_backup_${timestamp}.sql"
    local backup_path="${BACKUP_DIR}/${backup_file}"

    log_info "Starting backup..."

    # Create backup directory if not exists
    mkdir -p "$BACKUP_DIR"

    # Check if container is running
    if ! docker ps | grep -q "$CONTAINER_NAME"; then
        log_error "Container $CONTAINER_NAME is not running!"
        exit 1
    fi

    # Create backup
    log_info "Creating backup: $backup_file"
    docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" > "$backup_path"

    # Compress backup
    log_info "Compressing backup..."
    gzip "$backup_path"

    # Verify backup
    if [ -f "${backup_path}.gz" ]; then
        local size=$(du -h "${backup_path}.gz" | cut -f1)
        log_info "Backup created successfully: ${backup_file}.gz (${size})"
    else
        log_error "Backup failed!"
        exit 1
    fi

    # Cleanup old backups
    cleanup_old_backups

    log_info "Backup completed!"
}

# =============================================================================
# RESTORE FUNCTION
# =============================================================================

restore_database() {
    local backup_file="$1"

    if [ -z "$backup_file" ]; then
        log_error "Usage: $0 restore <backup_file.sql.gz>"
        exit 1
    fi

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi

    log_warn "This will REPLACE all data in database '$DB_NAME'!"
    read -p "Are you sure? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Restore cancelled."
        exit 0
    fi

    log_info "Restoring from: $backup_file"

    # Decompress if needed
    if [[ "$backup_file" == *.gz ]]; then
        log_info "Decompressing backup..."
        gunzip -k "$backup_file"
        backup_file="${backup_file%.gz}"
    fi

    # Restore
    log_info "Restoring database..."
    cat "$backup_file" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" "$DB_NAME"

    log_info "Restore completed!"
}

# =============================================================================
# CLEANUP FUNCTION
# =============================================================================

cleanup_old_backups() {
    log_info "Cleaning up backups older than $RETENTION_DAYS days..."
    find "$BACKUP_DIR" -name "medsafe_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
}

# =============================================================================
# LIST BACKUPS
# =============================================================================

list_backups() {
    log_info "Available backups in $BACKUP_DIR:"
    echo ""

    if [ -d "$BACKUP_DIR" ]; then
        ls -lh "$BACKUP_DIR"/medsafe_backup_*.sql.gz 2>/dev/null || echo "  No backups found."
    else
        echo "  Backup directory does not exist."
    fi
}

# =============================================================================
# MAIN
# =============================================================================

case "${1:-backup}" in
    backup)
        backup_database
        ;;
    restore)
        restore_database "$2"
        ;;
    list)
        list_backups
        ;;
    cleanup)
        cleanup_old_backups
        ;;
    *)
        echo "Usage: $0 {backup|restore <file>|list|cleanup}"
        echo ""
        echo "Commands:"
        echo "  backup          Create a new backup"
        echo "  restore <file>  Restore from a backup file"
        echo "  list            List available backups"
        echo "  cleanup         Remove old backups"
        echo ""
        echo "Environment variables:"
        echo "  BACKUP_DIR      Backup directory (default: ./backups)"
        echo "  DB_CONTAINER    Database container name (default: medsafe_db)"
        echo "  POSTGRES_USER   Database user (default: medsafe)"
        echo "  POSTGRES_DB     Database name (default: medsafe)"
        echo "  RETENTION_DAYS  Days to keep backups (default: 30)"
        exit 1
        ;;
esac
