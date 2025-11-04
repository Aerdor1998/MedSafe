"""
Módulo de banco de dados do MedSafe
"""

from .database import check_db_health, get_db, get_db_stats, init_db
from .models import Base, Document, Embedding, IngestJob, Report, Triage

__all__ = [
    "get_db",
    "init_db",
    "check_db_health",
    "get_db_stats",
    "Base",
    "Triage",
    "Report",
    "Document",
    "Embedding",
    "IngestJob",
]
