"""
Esquemas Pydantic para validação de dados
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class Gender(str, Enum):
    MALE = "masculino"
    FEMALE = "feminino"
    OTHER = "outro"

class RiskLevel(str, Enum):
    LOW = "baixo"
    MEDIUM = "medio"
    HIGH = "alto"
    CRITICAL = "critico"

class PatientData(BaseModel):
    """Dados do paciente para anamnese"""
    id: Optional[str] = Field(None, description="ID anonimizado do paciente")
    age: int = Field(..., ge=0, le=120, description="Idade do paciente")
    weight: Optional[float] = Field(None, ge=0, description="Peso aproximado em kg")
    gender: Gender = Field(..., description="Gênero do paciente")
    conditions: List[str] = Field(default=[], description="Condições médicas anteriores")
    allergies: List[str] = Field(default=[], description="Alergias conhecidas")
    current_medications: List[str] = Field(default=[], description="Medicamentos atuais")
    supplements: List[str] = Field(default=[], description="Suplementos atuais")
    alcohol_use: bool = Field(default=False, description="Uso regular de álcool")
    smoking: bool = Field(default=False, description="Tabagismo")
    pregnancy: Optional[bool] = Field(None, description="Gravidez (se aplicável)")
    breastfeeding: Optional[bool] = Field(None, description="Amamentação (se aplicável)")
    kidney_function: Optional[str] = Field(None, description="Função renal")
    liver_function: Optional[str] = Field(None, description="Função hepática")
    additional_info: Optional[str] = Field(None, description="Informações adicionais")

class MedicationInfo(BaseModel):
    """Informações do medicamento"""
    name: str = Field(..., description="Nome comercial")
    active_ingredient: str = Field(..., description="Princípio ativo")
    dosage: Optional[str] = Field(None, description="Dosagem")
    route: Optional[str] = Field(None, description="Via de administração")
    manufacturer: Optional[str] = Field(None, description="Fabricante")
    therapeutic_class: Optional[str] = Field(None, description="Classe terapêutica")
    anvisa_registry: Optional[str] = Field(None, description="Registro ANVISA")

class Contraindication(BaseModel):
    """Contraindicação identificada"""
    type: str = Field(..., description="Tipo de contraindicação")
    description: str = Field(..., description="Descrição da contraindicação")
    risk_level: RiskLevel = Field(..., description="Nível de risco")
    source: str = Field(..., description="Fonte da informação (OMS/ANVISA)")
    recommendation: str = Field(..., description="Recomendação")

class DrugInteraction(BaseModel):
    """Interação medicamentosa"""
    interacting_drug: str = Field(..., description="Medicamento que interage")
    interaction_type: str = Field(..., description="Tipo de interação")
    effect: str = Field(..., description="Efeito da interação")
    risk_level: RiskLevel = Field(..., description="Nível de risco")
    mechanism: Optional[str] = Field(None, description="Mecanismo da interação")
    recommendation: str = Field(..., description="Recomendação")

class AdverseReaction(BaseModel):
    """Reação adversa possível"""
    reaction: str = Field(..., description="Tipo de reação")
    frequency: str = Field(..., description="Frequência da reação")
    severity: str = Field(..., description="Severidade")
    risk_factors: List[str] = Field(default=[], description="Fatores de risco do paciente")
    description: str = Field(..., description="Descrição da reação")

class Recommendation(BaseModel):
    """Recomendação médica"""
    category: str = Field(..., description="Categoria da recomendação")
    priority: RiskLevel = Field(..., description="Prioridade")
    action: str = Field(..., description="Ação recomendada")
    rationale: str = Field(..., description="Justificativa")

class AnalysisResult(BaseModel):
    """Resultado completo da análise"""
    session_id: str = Field(..., description="ID da sessão")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp da análise")
    patient: PatientData = Field(..., description="Dados do paciente")
    medication: MedicationInfo = Field(..., description="Informações do medicamento")
    contraindications: List[Contraindication] = Field(default=[], description="Contraindicações identificadas")
    drug_interactions: List[DrugInteraction] = Field(default=[], description="Interações medicamentosas")
    adverse_reactions: List[AdverseReaction] = Field(default=[], description="Possíveis reações adversas")
    recommendations: List[Recommendation] = Field(default=[], description="Recomendações médicas")
    overall_risk: RiskLevel = Field(..., description="Risco geral")
    summary: str = Field(..., description="Resumo da análise")
    disclaimer: str = Field(
        default="Esta é uma ferramenta de apoio informativo. Consulte seu médico antes de qualquer decisão sobre medicamentos.",
        description="Aviso legal"
    )

class MedicationRequest(BaseModel):
    """Requisição de análise de medicamento"""
    patient_data: PatientData = Field(..., description="Dados do paciente")
    medication_name: Optional[str] = Field(None, description="Nome do medicamento")
    image_path: Optional[str] = Field(None, description="Caminho da imagem")

class OCRResult(BaseModel):
    """Resultado do OCR"""
    extracted_text: str = Field(..., description="Texto extraído")
    medication_name: Optional[str] = Field(None, description="Nome do medicamento identificado")
    confidence: float = Field(..., ge=0, le=1, description="Nível de confiança")
    
class LogEntry(BaseModel):
    """Entrada de log para auditoria"""
    session_id: str = Field(..., description="ID da sessão")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp")
    event_type: str = Field(..., description="Tipo de evento")
    data: Dict[str, Any] = Field(default={}, description="Dados do evento")
    user_ip: Optional[str] = Field(None, description="IP do usuário")

class InteractionGraph(BaseModel):
    """Dados para grafo de interações"""
    nodes: List[Dict[str, Any]] = Field(..., description="Nós do grafo")
    edges: List[Dict[str, Any]] = Field(..., description="Arestas do grafo")
    metadata: Dict[str, Any] = Field(default={}, description="Metadados do grafo")