"""rotate seeded default admin password on existing databases

Bancos que rodaram a versão antiga da migração 006 têm admin@medsafe.local
com um hash bcrypt LITERAL (fixo no código-fonte, sem geração em runtime),
portanto a detecção por igualdade de hash é determinística. Se o hash default
ainda estiver armazenado, esta migração exige ADMIN_INITIAL_PASSWORD (env),
substitui o hash e revoga sessões ativas do admin. Caso a conta não exista ou
a senha já tenha sido trocada, é no-op.

Revision ID: 008
Revises: 007
Create Date: 2026-08-04 19:00:00.000000

"""

import os

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

ADMIN_EMAIL = "admin@medsafe.local"

# Hash exatamente como seedado pela versão antiga da 006 (literal no fonte).
DEFAULT_SEEDED_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.SuFPz6XWx5Xrz6"


def _needs_rotation(stored_hash: str) -> bool:
    """True se o hash armazenado ainda é o hash default seedado pela 006 antiga."""
    return stored_hash == DEFAULT_SEEDED_HASH


def _get_admin_initial_password() -> str:
    """Lê ADMIN_INITIAL_PASSWORD do ambiente; FALHA se ausente/vazia."""
    password = os.environ.get("ADMIN_INITIAL_PASSWORD", "").strip()
    if not password:
        raise RuntimeError(
            "ADMIN_INITIAL_PASSWORD ausente ou vazia, mas o admin ainda usa a "
            "senha default seedada pela migração 006 antiga. Defina esta "
            'variável de ambiente e rode "alembic upgrade" novamente.'
        )
    return password


def _admin_password_hash() -> str:
    """Deriva o novo hash reusando o mesmo contexto bcrypt do app."""
    # Import tardio: alembic/env.py já coloca a raiz do repo no sys.path.
    from backend.app.auth.password import hash_password

    return hash_password(_get_admin_initial_password())


def upgrade() -> None:
    conn = op.get_bind()

    row = conn.execute(
        sa.text("SELECT id, password_hash FROM users WHERE email = :email"),
        {"email": ADMIN_EMAIL},
    ).first()

    if row is None or not _needs_rotation(row.password_hash):
        # Conta não existe ou a senha já foi trocada — nada a fazer.
        print("✅ 008: admin sem senha default (ou inexistente) — no-op.")
        return

    conn.execute(
        sa.text(
            """
            UPDATE users
            SET password_hash = :new_hash,
                last_password_change = NOW(),
                updated_at = NOW()
            WHERE id = :user_id
        """
        ),
        {"new_hash": _admin_password_hash(), "user_id": row.id},
    )

    # Revogar sessões ativas do admin (mecanismo existente: user_sessions).
    conn.execute(
        sa.text(
            """
            UPDATE user_sessions
            SET is_active = false,
                revoked_at = NOW(),
                revoke_reason = 'rotação forçada da senha default do admin (migração 008)'
            WHERE user_id = :user_id AND is_active = true
        """
        ),
        {"user_id": row.id},
    )

    print(
        f"✅ 008: senha default de {ADMIN_EMAIL} rotacionada e sessões ativas revogadas."
    )


def downgrade() -> None:
    # No-op intencional: não restauramos a senha default conhecida (inseguro).
    pass
