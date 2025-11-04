"""
Schemas para ingestão de dados (ANVISA, SIDER, DrugCentral)
"""

from typing import List, Optional, Dict, Any
from pydantic import Field
from .base import BaseSchema, TimestampSchema, IDSchema


class IngestRequest(BaseSchema):
    """Requisição para ingestão de dados"""

    source: str = Field(..., description="Fonte dos dados (ANVISA, SIDER, DrugCentral)")
    data_type: str = Field(
        ..., description="Tipo de dados (bulas, interações, reações_adversas)"
    )

    # Parâmetros específicos por fonte
    query: Optional[str] = Field(None, description="Termo de busca (para ANVISA)")
    max_results: Optional[int] = Field(None, description="Máximo de resultados")

    # URLs ou arquivos
    urls: List[str] = Field(default=[], description="URLs para download")
    file_paths: List[str] = Field(default=[], description="Caminhos de arquivos locais")

    # Configurações de processamento
    force_reprocess: bool = Field(False, description="Forçar reprocessamento")
    chunk_size: Optional[int] = Field(None, description="Tamanho dos chunks para RAG")

    # Metadados
    description: Optional[str] = Field(None, description="Descrição da ingestão")
    tags: List[str] = Field(default=[], description="Tags para categorização")


class IngestResponse(IDSchema, TimestampSchema):
    """Resposta da ingestão de dados"""

    source: str
    data_type: str
    status: str = Field(..., description="Status da ingestão")

    # Resultados
    total_processed: int = Field(..., description="Total de itens processados")
    successful: int = Field(..., description="Itens processados com sucesso")
    failed: int = Field(..., description="Itens que falharam")

    # Detalhes
    processed_items: List[Dict[str, Any]] = Field(
        default=[], description="Detalhes dos itens processados"
    )

    errors: List[Dict[str, Any]] = Field(
        default=[], description="Erros encontrados durante o processamento"
    )

    # Metadados
    processing_time: float = Field(
        ..., description="Tempo de processamento em segundos"
    )
    model_used: Optional[str] = Field(None, description="Modelo de IA utilizado")

    # Links para resultados
    report_url: Optional[str] = Field(None, description="URL do relatório detalhado")
    download_url: Optional[str] = Field(None, description="URL para download dos dados")


class IngestStatus(BaseSchema):
    """Status de uma ingestão em andamento"""

    id: str
    source: str
    data_type: str
    status: str
    progress: float = Field(..., ge=0, le=100, description="Progresso em porcentagem")
    current_step: str = Field(..., description="Etapa atual")
    estimated_completion: Optional[str] = Field(
        None, description="Tempo estimado para conclusão"
    )
    created_at: str
    updated_at: str


class IngestSource(BaseSchema):
    """Configuração de uma fonte de dados"""

    name: str = Field(..., description="Nome da fonte")
    type: str = Field(..., description="Tipo da fonte (API, arquivo, web scraping)")
    base_url: Optional[str] = Field(None, description="URL base da API")

    # Configurações de autenticação
    requires_auth: bool = Field(False, description="Se requer autenticação")
    auth_type: Optional[str] = Field(None, description="Tipo de autenticação")

    # Configurações de rate limiting
    rate_limit: Optional[int] = Field(
        None, description="Limite de requisições por minuto"
    )

    # Metadados
    description: Optional[str] = Field(None, description="Descrição da fonte")
    last_updated: Optional[str] = Field(None, description="Última atualização")
    is_active: bool = Field(True, description="Se a fonte está ativa")
