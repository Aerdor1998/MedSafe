"""
Módulo de banco de dados do MedSafe
"""

from .database import get_db, init_db, check_db_health, get_db_stats
from .models import Base, Triage, Report, Document, Embedding, IngestJob

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
