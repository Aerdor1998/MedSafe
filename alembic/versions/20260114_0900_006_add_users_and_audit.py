"""add users and audit tables

Revision ID: 006
Revises: 005
Create Date: 2026-01-14 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Cria tabelas de usuários, sessões e auditoria."""
    
    # Criar enum para roles de usuário
    user_role_enum = postgresql.ENUM(
        'admin', 'physician', 'pharmacist', 'readonly',
        name='user_role_enum',
        create_type=False
    )
    
    # Criar tipo enum se não existir
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_role_enum AS ENUM (
                'admin', 'physician', 'pharmacist', 'readonly'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Tabela de usuários
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', user_role_enum, nullable=False, server_default='readonly'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_password_change', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('crm', sa.String(20), nullable=True, unique=True),
        sa.Column('crf', sa.String(20), nullable=True, unique=True),
        sa.Column('specialty', sa.String(100), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notification_preferences', sa.String(500), 
                  server_default='{"email": true, "sms": false}'),
    )
    
    # Índices para users
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_is_active', 'users', ['is_active'])
    op.create_index('idx_users_is_deleted', 'users', ['is_deleted'])
    op.create_index('idx_users_crm', 'users', ['crm'], postgresql_where=sa.text('crm IS NOT NULL'))
    op.create_index('idx_users_crf', 'users', ['crf'], postgresql_where=sa.text('crf IS NOT NULL'))
    
    # Tabela de sessões de usuário
    op.create_table(
        'user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('jti', sa.String(36), nullable=False, unique=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('device_info', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoke_reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_activity', sa.DateTime(timezone=True), 
                  server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    
    # Índices para user_sessions
    op.create_index('idx_user_sessions_user_id', 'user_sessions', ['user_id'])
    op.create_index('idx_user_sessions_jti', 'user_sessions', ['jti'])
    op.create_index('idx_user_sessions_is_active', 'user_sessions', ['is_active'])
    op.create_index('idx_user_sessions_expires_at', 'user_sessions', ['expires_at'])
    
    # Tabela de logs de auditoria
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_category', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False, server_default='INFO'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('user_role', sa.String(50), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('request_id', sa.String(36), nullable=True),
        sa.Column('endpoint', sa.String(255), nullable=True),
        sa.Column('http_method', sa.String(10), nullable=True),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(36), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('details', sa.String(2000), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    
    # Índices para audit_logs
    op.create_index('idx_audit_logs_event_type', 'audit_logs', ['event_type'])
    op.create_index('idx_audit_logs_event_category', 'audit_logs', ['event_category'])
    op.create_index('idx_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_logs_request_id', 'audit_logs', ['request_id'])
    op.create_index('idx_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('idx_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])
    
    # Índice parcial para logs de erros
    op.create_index(
        'idx_audit_logs_errors', 
        'audit_logs', 
        ['created_at', 'event_type'],
        postgresql_where=sa.text("success = false")
    )
    
    # Criar usuário admin inicial (senha deve ser alterada no primeiro login)
    # Hash BCrypt de 'ChangeMeNow123!' para bootstrap
    op.execute("""
        INSERT INTO users (email, password_hash, full_name, role, is_active, is_verified)
        VALUES (
            'admin@medsafe.local',
            '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.SuFPz6XWx5Xrz6',
            'Administrador MedSafe',
            'admin',
            true,
            true
        )
        ON CONFLICT (email) DO NOTHING;
    """)
    
    print("✅ Tabelas users, user_sessions e audit_logs criadas com sucesso!")
    print("⚠️  Usuário admin inicial criado: admin@medsafe.local")
    print("⚠️  IMPORTANTE: Altere a senha no primeiro login!")


def downgrade() -> None:
    """Remove tabelas de usuários, sessões e auditoria."""
    
    # Remover tabelas na ordem correta (FK constraints)
    op.drop_table('audit_logs')
    op.drop_table('user_sessions')
    op.drop_table('users')
    
    # Remover enum
    op.execute("DROP TYPE IF EXISTS user_role_enum")
    
    print("✅ Tabelas removidas com sucesso.")

