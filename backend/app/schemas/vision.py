"""
Schemas para análise de imagem/PDF com VisionAgent
"""

from typing import List, Optional, Dict, Any
from pydantic import Field
from .base import BaseSchema, TimestampSchema, IDSchema


class VisionRequest(BaseSchema):
    """Requisição para análise de imagem/PDF"""

    # Dados do arquivo
    file_type: str = Field(..., description="Tipo do arquivo (image/pdf)")
    file_size: int = Field(..., description="Tamanho do arquivo em bytes")

    # Dados opcionais
    medication_text: Optional[str] = Field(
        None, description="Texto adicional sobre medicamento"
    )
    session_id: Optional[str] = Field(None, description="ID da sessão")

    # Metadados
    source: Optional[str] = Field(
        None, description="Fonte da imagem (rótulo, bula, etc.)"
    )


class VisionResponse(IDSchema, TimestampSchema):
    """Resposta da análise de imagem/PDF"""

    session_id: str = Field(..., description="ID da sessão")

    # Dados extraídos
    drug_name: Optional[str] = Field(
        None, description="Nome do medicamento identificado"
    )
    strength: Optional[str] = Field(
        None, description="Concentração/força do medicamento"
    )
    form: Optional[str] = Field(None, description="Forma farmacêutica")

    # Seções extraídas da bula
    sections: List[Dict[str, Any]] = Field(
        default=[],
        description="Seções extraídas (contraindicações, advertências, posologia, interações)",  # noqa: E501
    )

    # Dados de processamento
    extracted_text: str = Field(..., description="Texto extraído da imagem/PDF")
    confidence_score: Optional[float] = Field(
        None, description="Score de confiança da extração"
    )

    # Metadados técnicos
    model_used: str = Field(..., description="Modelo VLM utilizado")
    processing_time: Optional[float] = Field(
        None, description="Tempo de processamento em segundos"
    )

    # Status
    status: str = Field(..., description="Status da análise")
    error_message: Optional[str] = Field(None, description="Mensagem de erro se houver")


class VisionSection(BaseSchema):
    """Seção extraída de uma bula"""

    section_type: str = Field(
        ..., description="Tipo da seção (contraindicações, advertências, etc.)"
    )
    text: str = Field(..., description="Texto da seção")
    confidence: float = Field(..., description="Confiança da extração (0-1)")

    # Posições no documento original
    start_offset: Optional[int] = Field(None, description="Posição inicial no texto")
    end_offset: Optional[int] = Field(None, description="Posição final no texto")

    # Metadados
    source_page: Optional[int] = Field(None, description="Página da fonte (para PDFs)")
    bounding_box: Optional[List[float]] = Field(
        None, description="Coordenadas da seção na imagem"
    )
