"""
Schemas Pydantic para o MedSafe
"""

from .base import BaseSchema
from .ingest import IngestRequest, IngestResponse
from .medications import MedicationInfo, MedicationSearch, MedicationSearchResult
from .reports import ReportCreate, ReportResponse
from .triage import TriageCreate, TriageReport, TriageResponse
from .vision import VisionRequest, VisionResponse

__all__ = [
    "BaseSchema",
    "TriageCreate",
    "TriageResponse",
    "TriageReport",
    "VisionRequest",
    "VisionResponse",
    "ReportCreate",
    "ReportResponse",
    "MedicationSearch",
    "MedicationInfo",
    "MedicationSearchResult",
    "IngestRequest",
    "IngestResponse",
]
