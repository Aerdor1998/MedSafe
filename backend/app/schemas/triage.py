"""
Schemas para triagem de pacientes
"""

from typing import Any, Dict, List, Optional

from pydantic import Field, validator

from .base import BaseSchema, IDSchema, TimestampSchema


class TriageCreate(BaseSchema):
    """Dados para criação de triagem"""

    # Dados demográficos
    age: int = Field(..., ge=0, le=150, description="Idade do paciente")
    weight: Optional[float] = Field(None, gt=0, description="Peso em kg")
    pregnant: bool = Field(False, description="Paciente gestante")

    # Comorbidades (CID-10/11)
    cid_codes: List[str] = Field(default=[], description="Códigos CID das comorbidades")

    # Medicamentos em uso
    meds_in_use: List[Dict[str, Any]] = Field(
        default=[], description="Lista de medicamentos em uso"
    )

    # Alergias
    allergies: List[str] = Field(default=[], description="Lista de alergias")

    # Função renal e hepática
    renal_function: Optional[Dict[str, Any]] = Field(
        None, description="Dados da função renal (TFG, creatinina, etc.)"
    )
    hepatic_function: Optional[Dict[str, Any]] = Field(
        None, description="Dados da função hepática (ALT, AST, bilirrubina, etc.)"
    )

    # Notas adicionais
    notes: Optional[str] = Field(None, description="Observações adicionais")

    @validator("meds_in_use")
    def validate_meds_in_use(cls, v):
        """Validar estrutura dos medicamentos em uso"""
        for med in v:
            if not isinstance(med, dict):
                raise ValueError("Cada medicamento deve ser um dicionário")
            if "name" not in med:
                raise ValueError("Medicamento deve ter campo 'name'")
        return v


class TriageResponse(IDSchema, TimestampSchema):
    """Resposta da triagem criada"""

    user_id: Optional[str] = Field(None, description="ID do usuário")
    status: str = Field(..., description="Status da triagem")
    job_id: Optional[str] = Field(None, description="ID do job de análise")

    # Dados da triagem
    age: int
    weight: Optional[float]
    pregnant: bool
    cid_codes: List[str]
    meds_in_use: List[Dict[str, Any]]
    allergies: List[str]
    renal_function: Optional[Dict[str, Any]]
    hepatic_function: Optional[Dict[str, Any]]
    notes: Optional[str]


class TriageReport(BaseSchema):
    """Relatório completo da triagem"""

    triage_id: str = Field(..., description="ID da triagem")
    risk_level: str = Field(..., description="Nível de risco (baixo, médio, alto)")

    # Resultados da análise
    contraindications: List[Dict[str, Any]] = Field(
        default=[], description="Lista de contraindicações encontradas"
    )

    interactions: List[Dict[str, Any]] = Field(
        default=[], description="Lista de interações medicamentosas"
    )

    dosage_adjustments: List[Dict[str, Any]] = Field(
        default=[], description="Ajustes de posologia recomendados"
    )

    adverse_reactions: List[Dict[str, Any]] = Field(
        default=[], description="Reações adversas identificadas"
    )

    # Evidências e citações
    evidence_links: List[Dict[str, Any]] = Field(
        default=[], description="Links para evidências e fontes"
    )

    # Metadados
    analysis_timestamp: str = Field(..., description="Timestamp da análise")
    model_used: str = Field(..., description="Modelo de IA utilizado")
    confidence_score: Optional[float] = Field(None, description="Score de confiança")
