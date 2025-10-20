"""
Configuração do banco de dados PostgreSQL com pgvector
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
import logging
from typing import Generator

from ..config import settings

# Configurar logging
logger = logging.getLogger(__name__)

# Criar engine do PostgreSQL
DATABASE_URL = settings.database_url_safe

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    echo=settings.debug
)

# Criar sessão
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para os modelos
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency para obter sessão do banco"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager para sessão do banco"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Inicializar banco de dados e criar tabelas"""
    try:
        # Detectar tipo de banco de dados
        is_postgres = 'postgresql' in str(engine.url)
        is_sqlite = 'sqlite' in str(engine.url)

        # Verificar conexão
        with engine.connect() as conn:
            if is_postgres:
                # Verificar se a extensão pgvector está disponível
                result = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                if not result.fetchone():
                    logger.warning("Extensão pgvector não encontrada. Criando...")
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()

                logger.info("✅ Conexão com PostgreSQL estabelecida")
            elif is_sqlite:
                logger.info("✅ Usando SQLite para desenvolvimento local")

        # Criar todas as tabelas
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tabelas criadas com sucesso")

        # Criar índices específicos (apenas para PostgreSQL)
        if is_postgres:
            create_indexes()

    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco: {e}")
        raise


def create_indexes():
    """Criar índices otimizados para o MedSafe"""
    try:
        with engine.connect() as conn:
            # Índice HNSW para embeddings (pgvector)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_vector
                ON embeddings
                USING hnsw (vector vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """))

            # Índices para busca textual
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_drug_name
                ON documents (drug_name)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_section
                ON documents (section)
            """))

            # Índices para triagem
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_triage_user_id
                ON triage (user_id)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_triage_created_at
                ON triage (created_at)
            """))

            # Índices para relatórios
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_reports_triage_id
                ON reports (triage_id)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_reports_risk_level
                ON reports (risk_level)
            """))

            conn.commit()
            logger.info("✅ Índices criados com sucesso")

    except Exception as e:
        logger.error(f"❌ Erro ao criar índices: {e}")
        # Não falhar se os índices não puderem ser criados
        pass


def check_db_health() -> bool:
    """Verificar saúde do banco de dados"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"❌ Erro de saúde do banco: {e}")
        return False


def get_db_stats() -> dict:
    """Obter estatísticas do banco de dados"""
    try:
        from sqlalchemy import select, func
        from sqlalchemy.schema import MetaData
        from .models import Triage, Report, Document, Embedding

        with engine.connect() as conn:
            stats = {}

            # Mapear modelos (seguro - não usa SQL dinâmico)
            models = {
                'triage': Triage,
                'reports': Report,
                'documents': Document,
                'embeddings': Embedding
            }

            # Contar registros usando ORM (seguro)
            metadata = MetaData()
            metadata.reflect(bind=engine)

            for name, model in models.items():
                if name in metadata.tables:
                    table_obj = metadata.tables[name]
                    count_query = select(func.count()).select_from(table_obj)
                    result = conn.execute(count_query)
                    stats[f"{name}_count"] = result.scalar()

            # Verificar tamanho do banco
            result = conn.execute(text("""
                SELECT pg_size_pretty(pg_database_size(current_database()))
            """))
            stats['database_size'] = result.fetchone()[0]

            return stats

    except Exception as e:
        logger.error(f"❌ Erro ao obter estatísticas: {type(e).__name__}")
        return {}
