"""Add drug_interactions table (CSV -> Postgres)

Revision ID: 005
Revises: 004
Create Date: 2025-12-12 10:00:00.000000

Creates a normalized drug interaction table optimized for pair lookups.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    print("Creating drug_interactions table...")

    op.create_table(
        "drug_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("drug_a", sa.String(), nullable=False),
        sa.Column("drug_b", sa.String(), nullable=False),
        sa.Column("drug_a_norm", sa.String(), nullable=False),
        sa.Column("drug_b_norm", sa.String(), nullable=False),
        sa.Column("interaction_type", sa.String(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("mechanism", sa.Text(), nullable=True),
        sa.Column("clinical_effect", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("idx_drug_interactions_severity", "drug_interactions", ["severity"])
    op.create_index("idx_drug_interactions_source", "drug_interactions", ["source"])
    op.create_index("idx_drug_interactions_pair", "drug_interactions", ["drug_a_norm", "drug_b_norm"])

    print("drug_interactions table created")


def downgrade() -> None:
    print("Dropping drug_interactions table...")
    op.drop_index("idx_drug_interactions_pair", table_name="drug_interactions")
    op.drop_index("idx_drug_interactions_source", table_name="drug_interactions")
    op.drop_index("idx_drug_interactions_severity", table_name="drug_interactions")
    op.drop_table("drug_interactions")
    print("drug_interactions table dropped")

