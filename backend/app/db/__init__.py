"""
Módulo de banco de dados do MedSafe
"""

from .database import get_db, init_db
from .models import *

__all__ = [
    "get_db",
    "init_db",
    "Base",
    "Triage",
    "Report",
    "Document",
    "Embedding",
    "IngestJob"
]
