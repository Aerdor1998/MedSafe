"""Add durable analysis_jobs table

Revision ID: 003
Revises: 002
Create Date: 2025-12-12 09:00:00.000000

This migration adds a durable job table to support:
- long-running LangGraph workflows executed by a separate worker process
- status polling without relying on in-memory checkpoints
- HITL resume after process restarts (state stored in DB)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    print("Creating analysis_jobs table...")

    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("triage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("triage.id"), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="pending"),
        sa.Column("retries", sa.Integer(), server_default="0"),
        sa.Column("max_retries", sa.Integer(), server_default="3"),
        sa.Column("payload", postgresql.JSON(), server_default="{}"),
        sa.Column("state", postgresql.JSON(), server_default="{}"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.text("now()")),
    )

    op.create_index("idx_analysis_jobs_session_id", "analysis_jobs", ["session_id"], unique=True)
    op.create_index("idx_analysis_jobs_status", "analysis_jobs", ["status"])
    op.create_index("idx_analysis_jobs_created_at", "analysis_jobs", ["created_at"])
    op.create_index("idx_analysis_jobs_status_created", "analysis_jobs", ["status", "created_at"])

    print("analysis_jobs table created")


def downgrade() -> None:
    print("Dropping analysis_jobs table...")
    op.drop_index("idx_analysis_jobs_status_created", table_name="analysis_jobs")
    op.drop_index("idx_analysis_jobs_created_at", table_name="analysis_jobs")
    op.drop_index("idx_analysis_jobs_status", table_name="analysis_jobs")
    op.drop_index("idx_analysis_jobs_session_id", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
    print("analysis_jobs table dropped")

