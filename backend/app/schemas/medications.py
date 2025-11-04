"""
Schemas para medicamentos e busca
"""

from typing import List, Optional, Dict, Any
from pydantic import Field
from .base import BaseSchema


class MedicationSearch(BaseSchema):
    """Parâmetros de busca de medicamentos"""

    query: str = Field(..., description="Termo de busca")
    limit: int = Field(10, ge=1, le=100, description="Limite de resultados")
    include_generic: bool = Field(True, description="Incluir genéricos")
    include_brands: bool = Field(True, description="Incluir marcas comerciais")

    # Filtros opcionais
    form: Optional[str] = Field(None, description="Forma farmacêutica")
    strength: Optional[str] = Field(None, description="Concentração específica")
    source: Optional[str] = Field(
        None, description="Fonte dos dados (ANVISA, RxNorm, etc.)"
    )


class MedicationInfo(BaseSchema):
    """Informações completas de um medicamento"""

    # Identificação
    name: str = Field(..., description="Nome do medicamento")
    generic_name: Optional[str] = Field(None, description="Nome genérico")
    brand_names: List[str] = Field(default=[], description="Nomes comerciais")

    # Características
    strength: Optional[str] = Field(None, description="Concentração/força")
    form: Optional[str] = Field(None, description="Forma farmacêutica")
    route: Optional[str] = Field(None, description="Via de administração")

    # Classificações
    atc_code: Optional[str] = Field(None, description="Código ATC")
    rxnorm_cui: Optional[str] = Field(None, description="Código RxNorm CUI")

    # Dados clínicos
    indications: List[str] = Field(default=[], description="Indicações terapêuticas")
    contraindications: List[str] = Field(default=[], description="Contraindicações")
    warnings: List[str] = Field(default=[], description="Advertências")

    # Interações
    drug_interactions: List[Dict[str, Any]] = Field(
        default=[], description="Interações medicamentosas"
    )

    # Reações adversas
    side_effects: List[Dict[str, Any]] = Field(
        default=[], description="Efeitos colaterais e reações adversas"
    )

    # Posologia
    dosage_info: Optional[Dict[str, Any]] = Field(
        None, description="Informações de posologia"
    )

    # Fontes
    sources: List[Dict[str, Any]] = Field(
        default=[], description="Fontes dos dados (ANVISA, SIDER, DrugCentral)"
    )

    # Metadados
    last_updated: Optional[str] = Field(None, description="Última atualização")
    data_quality_score: Optional[float] = Field(
        None, description="Score de qualidade dos dados"
    )


class MedicationSearchResult(BaseSchema):
    """Resultado de busca de medicamentos"""

    query: str
    total_results: int
    results: List[MedicationInfo]
    search_time: float = Field(..., description="Tempo de busca em segundos")

    # Metadados da busca
    sources_searched: List[str] = Field(default=[], description="Fontes consultadas")
    filters_applied: Dict[str, Any] = Field(default={}, description="Filtros aplicados")
