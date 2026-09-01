"""
Módulo de banco de dados do MedSafe
"""

from .database import Base, get_db, init_db
from .models import Document, Embedding, IngestJob, Report, Triage

__all__ = [
    "get_db",
    "init_db",
    "Base",
    "Triage",
    "Report",
    "Document",
    "Embedding",
    "IngestJob",
]
