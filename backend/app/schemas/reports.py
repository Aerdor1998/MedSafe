"""
Schemas para relatórios de análise
"""

from typing import List, Optional, Dict, Any
from pydantic import Field
from .base import BaseSchema, TimestampSchema, IDSchema


class ReportCreate(BaseSchema):
    """Dados para criação de relatório"""
    
    triage_id: str = Field(..., description="ID da triagem")
    vision_id: Optional[str] = Field(None, description="ID da análise de imagem/PDF")
    
    # Dados da análise
    risk_level: str = Field(..., description="Nível de risco identificado")
    
    # Resultados detalhados
    contraindications: List[Dict[str, Any]] = Field(
        default=[],
        description="Contraindicações encontradas"
    )
    
    interactions: List[Dict[str, Any]] = Field(
        default=[],
        description="Interações medicamentosas"
    )
    
    dosage_adjustments: List[Dict[str, Any]] = Field(
        default=[],
        description="Ajustes de posologia recomendados"
    )
    
    adverse_reactions: List[Dict[str, Any]] = Field(
        default=[],
        description="Reações adversas identificadas"
    )
    
    # Evidências e citações
    evidence_links: List[Dict[str, Any]] = Field(
        default=[],
        description="Links para evidências e fontes"
    )
    
    # Metadados da análise
    model_used: str = Field(..., description="Modelo de IA utilizado")
    confidence_score: Optional[float] = Field(None, description="Score de confiança")
    analysis_notes: Optional[str] = Field(None, description="Observações da análise")


class ReportResponse(IDSchema, TimestampSchema):
    """Relatório completo retornado"""
    
    triage_id: str
    vision_id: Optional[str]
    
    # Dados da análise
    risk_level: str
    contraindications: List[Dict[str, Any]]
    interactions: List[Dict[str, Any]]
    dosage_adjustments: List[Dict[str, Any]]
    adverse_reactions: List[Dict[str, Any]]
    evidence_links: List[Dict[str, Any]]
    
    # Metadados
    model_used: str
    confidence_score: Optional[float]
    analysis_notes: Optional[str]
    
    # Status
    status: str = Field(..., description="Status do relatório")
    is_final: bool = Field(..., description="Se o relatório é final")


class ReportSummary(BaseSchema):
    """Resumo do relatório para listagem"""
    
    id: str
    triage_id: str
    risk_level: str
    created_at: str
    status: str
    model_used: str
    confidence_score: Optional[float]

