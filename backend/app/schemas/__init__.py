"""
Schemas Pydantic para o MedSafe
"""

from .base import BaseSchema
from .triage import TriageCreate, TriageResponse, TriageReport
from .vision import VisionRequest, VisionResponse
from .reports import ReportCreate, ReportResponse
from .medications import MedicationSearch, MedicationInfo, MedicationSearchResult
from .ingest import IngestRequest, IngestResponse

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
