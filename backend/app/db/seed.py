"""
Seed idempotente de dados iniciais (usuário admin).

Executado no startup da API (lifespan). Cria o usuário admin a partir de
``ADMIN_INITIAL_EMAIL``/``ADMIN_INITIAL_PASSWORD`` apenas se ele ainda não
existir — nunca sobrescreve a senha de um usuário já persistido, para que
rotação de senha em produção continue sendo feita pelo fluxo normal.
"""

import logging
import os

from .database import SessionLocal
from .user_models import User, UserRole

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_EMAIL = "admin@medsafe.local"


def seed_initial_admin() -> None:
    """Criar o usuário admin inicial se (e somente se) ele não existir.

    Regras:
    - ``ADMIN_INITIAL_PASSWORD`` vazio/ausente → apenas loga warning e retorna
      (deploys sem seed explícito não podem criar admin com senha implícita).
    - Usuário já existe → no-op (idempotente; não reseta senha).
    """
    email = os.getenv("ADMIN_INITIAL_EMAIL", DEFAULT_ADMIN_EMAIL).strip().lower()
    password = os.getenv("ADMIN_INITIAL_PASSWORD", "")

    if not password:
        logger.warning(
            "ADMIN_INITIAL_PASSWORD não definido — seed do admin inicial ignorado"
        )
        return

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            logger.info("Admin seed: usuário %s já existe — nada a fazer", email)
            return

        admin = User(
            email=email,
            password_hash=User.hash_password(password),
            full_name="Administrador",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        logger.info("Admin seed: usuário %s criado com role admin", email)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
