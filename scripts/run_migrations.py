#!/usr/bin/env python3
"""
Database Migration Runner for MedSafe

PATTERN: Database migration automation script
SKILLS: @ultrathink, @api-design-principles

This script provides easy commands for running Alembic migrations.

Usage:
    # Run all pending migrations
    python scripts/run_migrations.py upgrade

    # Rollback last migration
    python scripts/run_migrations.py downgrade

    # Show current revision
    python scripts/run_migrations.py current

    # Show migration history
    python scripts/run_migrations.py history

    # Create new migration
    python scripts/run_migrations.py revision --message "Add new column"
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import logging
from alembic.config import Config
from alembic import command

from backend.app.config import settings
from backend.app.db.database import check_db_health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def get_alembic_config() -> Config:
    """Get Alembic configuration"""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url_safe)
    return alembic_cfg


def upgrade_database(revision: str = "head"):
    """
    Upgrade database to specified revision

    Args:
        revision: Target revision (default: "head" for latest)
    """
    logger.info(f"Upgrading database to revision: {revision}")

    # Check database health
    if not check_db_health():
        logger.error("Database is not healthy. Cannot run migrations.")
        sys.exit(1)

    alembic_cfg = get_alembic_config()

    try:
        command.upgrade(alembic_cfg, revision)
        logger.info(f"Database upgraded to {revision}")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


def downgrade_database(revision: str = "-1"):
    """
    Downgrade database to specified revision

    Args:
        revision: Target revision (default: "-1" for previous)
    """
    logger.warning(f" Downgrading database to revision: {revision}")
    logger.warning(" This may result in data loss!")

    # Confirm
    response = input("Are you sure you want to downgrade? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("Downgrade cancelled.")
        return

    alembic_cfg = get_alembic_config()

    try:
        command.downgrade(alembic_cfg, revision)
        logger.info(f"Database downgraded to {revision}")
    except Exception as e:
        logger.error(f"Downgrade failed: {e}")
        raise


def show_current_revision():
    """Show current database revision"""
    alembic_cfg = get_alembic_config()

    try:
        command.current(alembic_cfg, verbose=True)
    except Exception as e:
        logger.error(f"Failed to get current revision: {e}")
        raise


def show_history(verbose: bool = False):
    """Show migration history"""
    alembic_cfg = get_alembic_config()

    try:
        command.history(alembic_cfg, verbose=verbose)
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise


def create_revision(message: str, autogenerate: bool = False):
    """
    Create new migration revision

    Args:
        message: Revision message
        autogenerate: Auto-generate migration from model changes
    """
    logger.info(f"Creating new revision: {message}")

    alembic_cfg = get_alembic_config()

    try:
        command.revision(
            alembic_cfg,
            message=message,
            autogenerate=autogenerate
        )
        logger.info("Revision created successfully")
    except Exception as e:
        logger.error(f"Failed to create revision: {e}")
        raise


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="MedSafe Database Migration Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Upgrade to latest
    python scripts/run_migrations.py upgrade

    # Downgrade one step
    python scripts/run_migrations.py downgrade

    # Show current revision
    python scripts/run_migrations.py current

    # Show history
    python scripts/run_migrations.py history

    # Create new migration
    python scripts/run_migrations.py revision --message "Add column"

    # Auto-generate migration
    python scripts/run_migrations.py revision --message "Auto changes" --autogenerate
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Upgrade command
    upgrade_parser = subparsers.add_parser('upgrade', help='Upgrade database')
    upgrade_parser.add_argument(
        'revision',
        nargs='?',
        default='head',
        help='Target revision (default: head)'
    )

    # Downgrade command
    downgrade_parser = subparsers.add_parser('downgrade', help='Downgrade database')
    downgrade_parser.add_argument(
        'revision',
        nargs='?',
        default='-1',
        help='Target revision (default: -1 for previous)'
    )

    # Current command
    subparsers.add_parser('current', help='Show current revision')

    # History command
    history_parser = subparsers.add_parser('history', help='Show migration history')
    history_parser.add_argument('--verbose', action='store_true', help='Verbose output')

    # Revision command
    revision_parser = subparsers.add_parser('revision', help='Create new migration')
    revision_parser.add_argument('--message', '-m', required=True, help='Revision message')
    revision_parser.add_argument('--autogenerate', action='store_true', help='Auto-generate from models')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch commands
    try:
        if args.command == 'upgrade':
            upgrade_database(args.revision)
        elif args.command == 'downgrade':
            downgrade_database(args.revision)
        elif args.command == 'current':
            show_current_revision()
        elif args.command == 'history':
            show_history(args.verbose)
        elif args.command == 'revision':
            create_revision(args.message, args.autogenerate)
        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
