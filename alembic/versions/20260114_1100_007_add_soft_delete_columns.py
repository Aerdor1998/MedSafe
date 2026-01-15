"""add soft delete columns for LGPD compliance

Revision ID: 007
Revises: 006
Create Date: 2026-01-14 11:00:00.000000

LGPD Compliance:
- Adiciona colunas is_deleted e deleted_at para soft delete
- Permite manter registros para auditoria sem exposição
- Índices otimizados para filtrar registros ativos
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Adiciona colunas de soft delete para compliance LGPD."""

    # ==========================================================================
    # Tabela: triage
    # ==========================================================================
    op.add_column('triage', sa.Column(
        'is_deleted',
        sa.Boolean(),
        nullable=False,
        server_default='false'
    ))
    op.add_column('triage', sa.Column(
        'deleted_at',
        sa.DateTime(timezone=True),
        nullable=True
    ))
    op.add_column('triage', sa.Column(
        'deleted_by',
        sa.String(36),
        nullable=True
    ))
    op.add_column('triage', sa.Column(
        'deletion_reason',
        sa.String(255),
        nullable=True
    ))

    # Índice para filtrar registros ativos
    op.create_index(
        'idx_triage_is_deleted',
        'triage',
        ['is_deleted']
    )
    # Índice parcial para queries de registros ativos (mais eficiente)
    op.create_index(
        'idx_triage_active',
        'triage',
        ['created_at'],
        postgresql_where=sa.text('is_deleted = false')
    )

    # ==========================================================================
    # Tabela: reports
    # ==========================================================================
    op.add_column('reports', sa.Column(
        'is_deleted',
        sa.Boolean(),
        nullable=False,
        server_default='false'
    ))
    op.add_column('reports', sa.Column(
        'deleted_at',
        sa.DateTime(timezone=True),
        nullable=True
    ))
    op.add_column('reports', sa.Column(
        'deleted_by',
        sa.String(36),
        nullable=True
    ))

    op.create_index(
        'idx_reports_is_deleted',
        'reports',
        ['is_deleted']
    )
    op.create_index(
        'idx_reports_active',
        'reports',
        ['created_at'],
        postgresql_where=sa.text('is_deleted = false')
    )

    # ==========================================================================
    # Tabela: hitl_reviews
    # ==========================================================================
    op.add_column('hitl_reviews', sa.Column(
        'is_deleted',
        sa.Boolean(),
        nullable=False,
        server_default='false'
    ))
    op.add_column('hitl_reviews', sa.Column(
        'deleted_at',
        sa.DateTime(timezone=True),
        nullable=True
    ))

    op.create_index(
        'idx_hitl_reviews_is_deleted',
        'hitl_reviews',
        ['is_deleted']
    )

    # ==========================================================================
    # Tabela: documents (para RAG)
    # ==========================================================================
    op.add_column('documents', sa.Column(
        'is_deleted',
        sa.Boolean(),
        nullable=False,
        server_default='false'
    ))
    op.add_column('documents', sa.Column(
        'deleted_at',
        sa.DateTime(timezone=True),
        nullable=True
    ))

    op.create_index(
        'idx_documents_is_deleted',
        'documents',
        ['is_deleted']
    )
    op.create_index(
        'idx_documents_active_drug',
        'documents',
        ['drug_name'],
        postgresql_where=sa.text('is_deleted = false')
    )

    # ==========================================================================
    # Tabela: analysis_jobs (operacional, mas útil para auditoria)
    # ==========================================================================
    op.add_column('analysis_jobs', sa.Column(
        'is_deleted',
        sa.Boolean(),
        nullable=False,
        server_default='false'
    ))
    op.add_column('analysis_jobs', sa.Column(
        'deleted_at',
        sa.DateTime(timezone=True),
        nullable=True
    ))

    op.create_index(
        'idx_analysis_jobs_is_deleted',
        'analysis_jobs',
        ['is_deleted']
    )

    print("✅ Colunas de soft delete adicionadas com sucesso!")
    print("   Tabelas atualizadas: triage, reports, hitl_reviews, documents, analysis_jobs")
    print("   Índices criados para queries de registros ativos")


def downgrade() -> None:
    """Remove colunas de soft delete."""

    # analysis_jobs
    op.drop_index('idx_analysis_jobs_is_deleted', table_name='analysis_jobs')
    op.drop_column('analysis_jobs', 'deleted_at')
    op.drop_column('analysis_jobs', 'is_deleted')

    # documents
    op.drop_index('idx_documents_active_drug', table_name='documents')
    op.drop_index('idx_documents_is_deleted', table_name='documents')
    op.drop_column('documents', 'deleted_at')
    op.drop_column('documents', 'is_deleted')

    # hitl_reviews
    op.drop_index('idx_hitl_reviews_is_deleted', table_name='hitl_reviews')
    op.drop_column('hitl_reviews', 'deleted_at')
    op.drop_column('hitl_reviews', 'is_deleted')

    # reports
    op.drop_index('idx_reports_active', table_name='reports')
    op.drop_index('idx_reports_is_deleted', table_name='reports')
    op.drop_column('reports', 'deleted_by')
    op.drop_column('reports', 'deleted_at')
    op.drop_column('reports', 'is_deleted')

    # triage
    op.drop_index('idx_triage_active', table_name='triage')
    op.drop_index('idx_triage_is_deleted', table_name='triage')
    op.drop_column('triage', 'deletion_reason')
    op.drop_column('triage', 'deleted_by')
    op.drop_column('triage', 'deleted_at')
    op.drop_column('triage', 'is_deleted')

    print("✅ Colunas de soft delete removidas")
