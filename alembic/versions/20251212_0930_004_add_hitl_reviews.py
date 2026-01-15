"""Add HITL reviews audit table

Revision ID: 004
Revises: 003
Create Date: 2025-12-12 09:30:00.000000

Adds a durable audit log for Human-in-the-Loop decisions.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    print("Creating hitl_reviews table...")

    op.create_table(
        "hitl_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_jobs.id"), nullable=True),
        sa.Column("triage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("triage.id"), nullable=True),
        sa.Column("reviewer_id", sa.String(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("physician_notes", sa.Text(), nullable=True),
        sa.Column("modifications", postgresql.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("idx_hitl_reviews_session_id", "hitl_reviews", ["session_id"])
    op.create_index("idx_hitl_reviews_job_id", "hitl_reviews", ["job_id"])
    op.create_index("idx_hitl_reviews_triage_id", "hitl_reviews", ["triage_id"])
    op.create_index("idx_hitl_reviews_reviewer_id", "hitl_reviews", ["reviewer_id"])
    op.create_index("idx_hitl_reviews_created_at", "hitl_reviews", ["created_at"])

    print("hitl_reviews table created")


def downgrade() -> None:
    print("Dropping hitl_reviews table...")
    op.drop_index("idx_hitl_reviews_created_at", table_name="hitl_reviews")
    op.drop_index("idx_hitl_reviews_reviewer_id", table_name="hitl_reviews")
    op.drop_index("idx_hitl_reviews_triage_id", table_name="hitl_reviews")
    op.drop_index("idx_hitl_reviews_job_id", table_name="hitl_reviews")
    op.drop_index("idx_hitl_reviews_session_id", table_name="hitl_reviews")
    op.drop_table("hitl_reviews")
    print("hitl_reviews table dropped")

