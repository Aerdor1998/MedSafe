"""
Clinical Rules Engine for Severity Adjustment and Escalation

Contains:
1. Patient context-based severity modifiers
2. Automatic HITL escalation rules
3. Structured recommendation templates
4. Dose adjustment calculations
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..data import get_critical_combinations, get_critical_interactions

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS E DATACLASSES
# =============================================================================


class PopulationRisk(str, Enum):
    """Categorias de população de risco"""

    PEDIATRIC = "pediatric"  # < 12 anos
    ADOLESCENT = "adolescent"  # 12-17 anos
    ADULT = "adult"  # 18-64 anos
    GERIATRIC = "geriatric"  # >= 65 anos
    PREGNANCY = "pregnancy"  # Gestante
    LACTATION = "lactation"  # Amamentando
    RENAL_IMPAIRED = "renal_impaired"
    HEPATIC_IMPAIRED = "hepatic_impaired"


class RenalStage(str, Enum):
    """Estágios de função renal (CKD-EPI)"""

    G1 = "G1"  # GFR >= 90: Normal ou alto
    G2 = "G2"  # GFR 60-89: Levemente diminuído
    G3A = "G3a"  # GFR 45-59: Leve a moderadamente diminuído
    G3B = "G3b"  # GFR 30-44: Moderado a severamente diminuído
    G4 = "G4"  # GFR 15-29: Severamente diminuído
    G5 = "G5"  # GFR < 15: Falência renal


class HepaticStage(str, Enum):
    """Classificação Child-Pugh para função hepática"""

    A = "A"  # 5-6 pontos: Bem compensado
    B = "B"  # 7-9 pontos: Comprometimento significativo
    C = "C"  # 10-15 pontos: Descompensado


@dataclass
class PatientContext:
    """
    Contexto completo do paciente para ajuste de classificação

    SKILL: @api-design-principles - Estrutura type-safe
    """

    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    sex: Optional[str] = None
    pregnant: bool = False
    lactating: bool = False

    # Função renal
    creatinine: Optional[float] = None  # mg/dL
    gfr: Optional[float] = None  # mL/min/1.73m2
    renal_stage: Optional[RenalStage] = None

    # Função hepática
    alt: Optional[float] = None  # U/L
    ast: Optional[float] = None  # U/L
    bilirubin: Optional[float] = None  # mg/dL
    child_pugh: Optional[HepaticStage] = None

    # Condições
    conditions: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)

    # Medicamentos atuais (para detecção de polifarmácia)
    current_medications: List[str] = field(default_factory=list)

    def get_population_risks(self) -> List[PopulationRisk]:
        """Identificar todas as categorias de risco do paciente"""
        risks = []

        # Idade
        if self.age is not None:
            if self.age < 12:
                risks.append(PopulationRisk.PEDIATRIC)
            elif self.age < 18:
                risks.append(PopulationRisk.ADOLESCENT)
            elif self.age >= 65:
                risks.append(PopulationRisk.GERIATRIC)
            else:
                risks.append(PopulationRisk.ADULT)

        # Gravidez/Lactação
        if self.pregnant:
            risks.append(PopulationRisk.PREGNANCY)
        if self.lactating:
            risks.append(PopulationRisk.LACTATION)

        # Função renal
        if self.gfr is not None and self.gfr < 60:
            risks.append(PopulationRisk.RENAL_IMPAIRED)
        elif self.renal_stage in [
            RenalStage.G3A,
            RenalStage.G3B,
            RenalStage.G4,
            RenalStage.G5,
        ]:
            risks.append(PopulationRisk.RENAL_IMPAIRED)

        # Função hepática
        if self.child_pugh in [HepaticStage.B, HepaticStage.C]:
            risks.append(PopulationRisk.HEPATIC_IMPAIRED)

        return risks

    def is_polypharmacy(self) -> bool:
        """Polifarmácia: >= 5 medicamentos"""
        return len(self.current_medications) >= 5

    def is_geriatric_polypharmacy(self) -> bool:
        """Polifarmácia em idoso (alto risco)"""
        return self.age is not None and self.age >= 65 and self.is_polypharmacy()


@dataclass
class SeverityModification:
    """Modificação de severidade baseada em contexto"""

    original_severity: str
    modified_severity: str
    reason: str
    risk_factors: List[str]
    confidence_adjustment: float  # -1.0 a +1.0


# =============================================================================
# REGRAS DE MODIFICAÇÃO DE SEVERIDADE
# =============================================================================


# Drogas que requerem atenção especial em populações específicas
POPULATION_DRUG_ALERTS = {
    PopulationRisk.PREGNANCY: {
        # Categoria X FDA (teratogênicos absolutos)
        "contraindicated": [
            "warfarin",
            "isotretinoin",
            "methotrexate",
            "valproic acid",
            "thalidomide",
            "leflunomide",
            "misoprostol",
            "finasteride",
            "dutasteride",
            "ribavirin",
            "bosentan",
        ],
        # Categoria D (risco demonstrado mas pode ser necessário)
        "high_risk": [
            "phenytoin",
            "carbamazepine",
            "lithium",
            "atenolol",
            "tetracycline",
            "doxycycline",
            "ciprofloxacin",
        ],
        "severity_increase": 2,  # Sempre aumentar 2 níveis para teratogênicos
    },
    PopulationRisk.PEDIATRIC: {
        "contraindicated": [
            "aspirin",  # Síndrome de Reye
            "tetracycline",
            "doxycycline",  # Manchas dentárias
            "fluoroquinolone",
            "ciprofloxacin",
            "levofloxacin",  # Artropatia
        ],
        "high_risk": [
            "codeine",  # Metabolizadores ultrarrápidos
            "tramadol",
            "metoclopramide",  # Efeitos extrapiramidais
        ],
        "severity_increase": 1,
    },
    PopulationRisk.GERIATRIC: {
        # Lista de Beers (medicamentos potencialmente inapropriados)
        "high_risk": [
            "diazepam",
            "alprazolam",
            "lorazepam",
            "clonazepam",  # BZD longa ação
            "diphenhydramine",
            "chlorpheniramine",  # Anti-histamínicos
            "amitriptyline",
            "imipramine",  # Antidepressivos tricíclicos
            "meperidine",  # Opioide
            "indomethacin",  # AINE
            "nifedipine",  # Liberação imediata
        ],
        "severity_increase": 1,
    },
    PopulationRisk.RENAL_IMPAIRED: {
        "contraindicated": [
            "metformin",  # Se GFR < 30
            "lithium",  # Alto risco de toxicidade
        ],
        "high_risk": [
            "nsaid",
            "ibuprofen",
            "naproxen",
            "diclofenac",  # AINEs
            "gentamicin",
            "amikacin",
            "tobramycin",  # Aminoglicosídeos
            "vancomycin",
            "digoxin",
            "gabapentin",
            "pregabalin",
            "allopurinol",
        ],
        "severity_increase": 1,
    },
    PopulationRisk.HEPATIC_IMPAIRED: {
        "contraindicated": [
            "methotrexate",
        ],
        "high_risk": [
            "acetaminophen",
            "paracetamol",  # Hepatotóxico em dose alta
            "statins",
            "atorvastatin",
            "simvastatin",
            "isoniazid",
            "valproic acid",
            "ketoconazole",
        ],
        "severity_increase": 1,
    },
}


# Combinações de drogas que requerem escalonamento automático
CRITICAL_DRUG_COMBINATIONS = [
    {
        "drugs": ["warfarin", "aspirin"],
        "reason": "Risco significativo de sangramento",
        "category": "Coagulação",
    },
    {
        "drugs": ["warfarin", "nsaid"],
        "reason": "AINE + anticoagulante aumenta risco de sangramento GI",
        "category": "Coagulação",
    },
    {
        "drugs": ["lithium", "nsaid"],
        "reason": "AINE reduz excreção renal de lítio → toxicidade",
        "category": "Renal",
    },
    {
        "drugs": ["methotrexate", "nsaid"],
        "reason": "AINE reduz excreção renal de metotrexato → toxicidade",
        "category": "Renal",
    },
    {
        "drugs": ["digoxin", "amiodarone"],
        "reason": "Amiodarona aumenta níveis de digoxina em 70-100%",
        "category": "Cardiovascular",
    },
    {
        "drugs": ["simvastatin", "amiodarone"],
        "reason": "Risco de rabdomiólise",
        "category": "Musculoesquelética",
    },
    {
        "drugs": ["clopidogrel", "omeprazole"],
        "reason": "IBP reduz ativação do clopidogrel (CYP2C19)",
        "category": "Farmacocinética",
    },
]

# Interações críticas conhecidas (fallback clínico embutido).
# ATENÇÃO: NÃO usar este dict diretamente para matching — as chaves NÃO são
# canônicas ("aspirin" != saída do normalizador "acetylsalicylic acid").
# Use get_all_critical_interaction_rules() + canonicalização no
# DrugInteractionService, que aplica o MESMO normalizador dos medicamentos
# do paciente (invariante que garante o matching).
CRITICAL_INTERACTIONS = {
    ("spironolactone", "losartan"): {
        "severity": "high",
        "mechanism": "Both drugs increase potassium levels",
        "effect": "Risk of hyperkalemia",
        "recommendation": "Monitor potassium levels closely",
        "category": "Renal",
    },
    ("warfarin", "aspirin"): {
        "severity": "critical",
        "mechanism": "Both affect coagulation",
        "effect": "Increased bleeding risk",
        "recommendation": "Avoid combination if possible",
        "category": "Coagulacao",
    },
    # Contraindicação absoluta clássica: potencialização da via NO/GMPc
    ("nitrate", "pde5_inhibitor"): {
        "severity": "critical",
        "mechanism": (
            "Nitratos doam óxido nítrico (↑GMPc) e inibidores de PDE5 "
            "bloqueiam a degradação do GMPc — vasodilatação potencializada"
        ),
        "effect": "Hipotensão grave, potencialmente fatal (colapso cardiovascular)",
        "recommendation": (
            "Combinação CONTRAINDICADA — não administrar; intervalo mínimo "
            "de 24-48h entre as classes"
        ),
        "category": "Cardiovascular",
    },
}

# Classes farmacológicas referenciadas por regras (ex: [warfarin, nsaid]).
# Expandidas para membros concretos na canonicalização das regras.
DRUG_CLASS_MEMBERS: Dict[str, List[str]] = {
    "nsaid": [
        "ibuprofen",
        "naproxen",
        "diclofenac",
        "ketoprofen",
        "ketorolac",
        "piroxicam",
        "meloxicam",
        "indomethacin",
        "celecoxib",
        "etodolac",
        "nimesulide",
        "aspirin",
        "acetylsalicylic acid",
    ],
}
DRUG_CLASS_MEMBERS["nsaids"] = DRUG_CLASS_MEMBERS["nsaid"]
DRUG_CLASS_MEMBERS["nitrate"] = [
    "isosorbide mononitrate",
    "isosorbide dinitrate",
    "nitroglycerin",
]
DRUG_CLASS_MEMBERS["nitrates"] = DRUG_CLASS_MEMBERS["nitrate"]
DRUG_CLASS_MEMBERS["pde5_inhibitor"] = [
    "sildenafil",
    "tadalafil",
    "vardenafil",
]
DRUG_CLASS_MEMBERS["pde5_inhibitors"] = DRUG_CLASS_MEMBERS["pde5_inhibitor"]


def get_all_critical_interaction_rules() -> List[Dict[str, Any]]:
    """
    Fonte ÚNICA de regras determinísticas de interação medicamentosa.

    Unifica (antes havia 4 fontes independentes, 2 delas nunca consultadas):
    1. CRITICAL_INTERACTIONS (fallback embutido acima)
    2. YAML drug_data.yaml -> critical_combinations (severity default: high)
    3. YAML drug_data.yaml -> critical_interactions (severity explícita)

    Cada regra: {"drugs": [a, b], "severity", "mechanism", "effect",
                 "recommendation", "category"}

    A canonicalização (PT/EN/sinônimos/classes) é responsabilidade do
    DrugInteractionService._get_canonical_critical_rules().
    """
    rules: List[Dict[str, Any]] = []

    for (drug_a, drug_b), data in CRITICAL_INTERACTIONS.items():
        rules.append({"drugs": [drug_a, drug_b], **data})

    try:
        for combo in get_critical_combinations():
            drugs = combo.get("drugs") or []
            if len(drugs) != 2:
                continue
            rules.append(
                {
                    "drugs": [str(drugs[0]), str(drugs[1])],
                    "severity": combo.get("severity", "high"),
                    "mechanism": combo.get("mechanism", combo.get("reason", "")),
                    "effect": combo.get("reason", "Interação crítica conhecida"),
                    "recommendation": combo.get(
                        "recommendation",
                        "Combinação de alto risco — revisar com o prescritor",
                    ),
                    "category": combo.get("category", "ClinicalRule"),
                }
            )

        for _name, data in (get_critical_interactions() or {}).items():
            drugs = data.get("drugs") or []
            if len(drugs) != 2:
                continue
            rules.append(
                {
                    "drugs": [str(drugs[0]), str(drugs[1])],
                    "severity": data.get("severity", "high"),
                    "mechanism": data.get("mechanism", ""),
                    "effect": data.get("effect", "Interação crítica conhecida"),
                    "recommendation": data.get(
                        "recommendation",
                        "Combinação de alto risco — revisar com o prescritor",
                    ),
                    "category": data.get("category", "ClinicalRule"),
                }
            )
    except Exception:  # pragma: no cover - resiliência a YAML ausente
        logger.warning(
            "Falha ao carregar regras críticas do YAML; usando fallback embutido",
            exc_info=True,
        )

    return rules


# =============================================================================
# REGRAS DE ESCALONAMENTO AUTOMÁTICO (HITL)
# =============================================================================


@dataclass
class EscalationRule:
    """Regra de escalonamento para HITL"""

    name: str
    condition: str
    priority: str  # critical, high, medium
    reason_template: str


AUTO_ESCALATION_RULES = [
    EscalationRule(
        name="critical_interaction",
        condition="severity == 'critical'",
        priority="critical",
        reason_template="Interação CRÍTICA identificada: {details}",
    ),
    EscalationRule(
        name="pregnancy_teratogen",
        condition="pregnant and drug in teratogens",
        priority="critical",
        reason_template="Medicamento teratogênico em gestante: {drug}",
    ),
    EscalationRule(
        name="pediatric_contraindication",
        condition="age < 12 and drug in pediatric_contraindicated",
        priority="critical",
        reason_template="Medicamento contraindicado em pediatria: {drug}",
    ),
    EscalationRule(
        name="multiple_high_interactions",
        condition="count(high_interactions) >= 2",
        priority="high",
        reason_template="Múltiplas interações de alto risco ({count}): {drugs}",
    ),
    EscalationRule(
        name="geriatric_polypharmacy",
        condition="age >= 65 and medication_count >= 5",
        priority="high",
        reason_template="Polifarmácia em paciente idoso ({count} medicamentos)",
    ),
    EscalationRule(
        name="renal_nephrotoxic",
        condition="gfr < 30 and drug in nephrotoxic",
        priority="high",
        reason_template="Droga nefrotóxica em paciente com GFR < 30: {drug}",
    ),
    EscalationRule(
        name="low_confidence_high_risk",
        condition="confidence < 0.7 and severity in ['high', 'critical']",
        priority="high",
        reason_template="Baixa confiança ({confidence:.0%}) com risco {severity}",
    ),
]


# =============================================================================
# TEMPLATES DE RECOMENDAÇÕES
# =============================================================================


RECOMMENDATION_TEMPLATES = {
    "critical": {
        "header": "ALERTA CRITICO - ACAO IMEDIATA NECESSARIA",
        "actions": [
            "NAO ADMINISTRAR sem avaliacao medica presencial",
            "Avaliar alternativas terapeuticas imediatamente",
            "Se ja em uso, considerar descontinuacao supervisionada",
        ],
        "monitoring": [
            "Sinais vitais a cada 4 horas",
            "ECG se indicado",
            "Laboratorio conforme droga especifica",
        ],
    },
    "high": {
        "header": "ALERTA ALTO - REVISAO MEDICA RECOMENDADA",
        "actions": [
            "Avaliar relacao risco-beneficio antes de prescrever",
            "Considerar ajuste de dose ou alternativa",
            "Documentar justificativa se mantiver prescricao",
        ],
        "monitoring": [
            "Monitoramento clinico semanal inicial",
            "Laboratorio basal e follow-up em 2 semanas",
        ],
    },
    "medium": {
        "header": "ATENCAO - CAUTELA NECESSARIA",
        "actions": [
            "Pode ser prescrito com precaucoes",
            "Informar paciente sobre sinais de alerta",
        ],
        "monitoring": [
            "Reavaliacao em consulta de retorno",
        ],
    },
    "low": {
        "header": "INTERACAO DE BAIXO RISCO",
        "actions": [
            "Pode ser prescrito normalmente",
        ],
        "monitoring": [
            "Acompanhamento de rotina",
        ],
    },
}


# Recomendações específicas por categoria de interação
CATEGORY_RECOMMENDATIONS = {
    "Cardiovascular": {
        "monitoring": ["ECG basal e seriado", "Monitorar QTc", "PA e FC diarios"],
        "labs": ["Eletrolitos (K, Mg)", "Funcao renal"],
        "alerts": ["Palpitacoes", "Tontura", "Sincope"],
    },
    "Coagulacao": {
        "monitoring": ["INR semanal inicial", "Sinais de sangramento"],
        "labs": ["Hemograma", "TAP/INR", "Plaquetas"],
        "alerts": ["Sangramento gengival", "Hematomas", "Melena", "Hematuria"],
    },
    "Renal": {
        "monitoring": ["Debito urinario", "Peso diario"],
        "labs": ["Creatinina", "Ureia", "Eletrolitos"],
        "alerts": ["Oliguria", "Edema", "Nauseas"],
    },
    "Hepatica": {
        "monitoring": ["Sinais de ictericia", "Hepatomegalia"],
        "labs": ["TGO/TGP", "Bilirrubinas", "Fosfatase alcalina", "GGT"],
        "alerts": ["Ictericia", "Dor abdominal QSD", "Prurido"],
    },
    "Neurologica": {
        "monitoring": ["Nivel de consciencia", "Reflexos"],
        "labs": ["Niveis sericos da droga se disponivel"],
        "alerts": ["Confusao", "Tremores", "Convulsoes", "Sedacao excessiva"],
    },
}


# =============================================================================
# FUNÇÕES DE CÁLCULO
# =============================================================================


def calculate_gfr_cockroft_gault(
    age: int, weight: float, creatinine: float, sex: str
) -> float:
    """
    Calcular GFR usando fórmula de Cockroft-Gault

    GFR = ((140 - idade) x peso x [0.85 se mulher]) / (72 x creatinina)

    Args:
        age: Idade em anos
        weight: Peso em kg
        creatinine: Creatinina sérica em mg/dL
        sex: 'M' ou 'F'

    Returns:
        GFR estimado em mL/min
    """
    if creatinine <= 0:
        return 0.0

    gfr = ((140 - age) * weight) / (72 * creatinine)

    if sex.upper() == "F":
        gfr *= 0.85

    return round(gfr, 1)


def calculate_bmi(weight: float, height: float) -> float:
    """
    Calcular IMC (BMI)

    Args:
        weight: Peso em kg
        height: Altura em metros

    Returns:
        IMC em kg/m2
    """
    if height <= 0:
        return 0.0

    return round(weight / (height**2), 1)


def get_renal_stage(gfr: float) -> RenalStage:
    """Determinar estágio renal baseado no GFR"""
    if gfr >= 90:
        return RenalStage.G1
    elif gfr >= 60:
        return RenalStage.G2
    elif gfr >= 45:
        return RenalStage.G3A
    elif gfr >= 30:
        return RenalStage.G3B
    elif gfr >= 15:
        return RenalStage.G4
    else:
        return RenalStage.G5


# =============================================================================
# FUNÇÕES PRINCIPAIS
# =============================================================================


class ClinicalRulesEngine:
    """
    Motor de regras clínicas para ajuste de severidade e escalonamento

    SKILL: @ultrathink - Arquitetura modular e extensível
    """

    def __init__(self):
        logger.info("ClinicalRulesEngine inicializado")

    def adjust_severity_for_patient(
        self, base_severity: str, drug_name: str, patient_context: PatientContext
    ) -> SeverityModification:
        """
        Ajustar severidade baseado no contexto do paciente

        Args:
            base_severity: Severidade base ('low', 'medium', 'high', 'critical')
            drug_name: Nome do medicamento
            patient_context: Contexto do paciente

        Returns:
            SeverityModification com ajuste e justificativa
        """
        severity_order = ["low", "medium", "high", "critical"]
        current_idx = severity_order.index(base_severity)
        max_increase = 0
        risk_factors = []
        reasons = []

        drug_lower = drug_name.lower()

        # Verificar cada categoria de risco do paciente
        for risk in patient_context.get_population_risks():
            if risk not in POPULATION_DRUG_ALERTS:
                continue

            alerts = POPULATION_DRUG_ALERTS[risk]

            # Verificar contraindicados
            if "contraindicated" in alerts:
                for contraindicated in alerts["contraindicated"]:
                    if contraindicated in drug_lower:
                        max_increase = max(
                            max_increase, alerts.get("severity_increase", 2)
                        )
                        risk_factors.append(f"{risk.value}_contraindicated")
                        reasons.append(
                            f"{drug_name} contraindicado em {risk.value}: "
                            f"Risco elevado para esta população"
                        )
                        break

            # Verificar alto risco
            if "high_risk" in alerts:
                for high_risk in alerts["high_risk"]:
                    if high_risk in drug_lower:
                        max_increase = max(
                            max_increase, alerts.get("severity_increase", 1)
                        )
                        risk_factors.append(f"{risk.value}_high_risk")
                        reasons.append(
                            f"{drug_name} requer cautela em {risk.value}: "
                            f"Monitoramento adicional necessario"
                        )
                        break

        # Calcular nova severidade
        new_idx = min(current_idx + max_increase, len(severity_order) - 1)
        new_severity = severity_order[new_idx]

        # Confidence adjustment (maior risco = menor incerteza na decisão)
        confidence_adj = 0.1 * max_increase if max_increase > 0 else 0.0

        return SeverityModification(
            original_severity=base_severity,
            modified_severity=new_severity,
            reason="; ".join(reasons) if reasons else "Sem ajuste necessario",
            risk_factors=risk_factors,
            confidence_adjustment=confidence_adj,
        )

    def check_escalation_needed(
        self,
        severity: str,
        confidence: float,
        interactions: List[Dict[str, Any]],
        patient_context: PatientContext,
        drug_name: str,
    ) -> Tuple[bool, List[str]]:
        """
        Verificar se escalonamento para HITL é necessário

        Returns:
            Tuple[needs_escalation, reasons]
        """
        needs_escalation = False
        escalation_reasons = []

        # Regra 1: Interação crítica
        if severity == "critical":
            needs_escalation = True
            escalation_reasons.append("Interacao CRITICA identificada")

        # Regra 2: Gestante com teratogênico
        if patient_context.pregnant:
            teratogens = POPULATION_DRUG_ALERTS[PopulationRisk.PREGNANCY].get(
                "contraindicated", []
            )
            if any(t in drug_name.lower() for t in teratogens):
                needs_escalation = True
                escalation_reasons.append(
                    f"Medicamento teratogenico em gestante: {drug_name}"
                )

        # Regra 3: Pediatria com contraindicação
        if patient_context.age and patient_context.age < 12:
            pediatric_contra = POPULATION_DRUG_ALERTS[PopulationRisk.PEDIATRIC].get(
                "contraindicated", []
            )
            if any(c in drug_name.lower() for c in pediatric_contra):
                needs_escalation = True
                escalation_reasons.append(
                    f"Medicamento contraindicado em pediatria: {drug_name}"
                )

        # Regra 4: Múltiplas interações de alto risco
        high_interactions = [
            i for i in interactions if i.get("severity") in ["high", "critical"]
        ]
        if len(high_interactions) >= 2:
            needs_escalation = True
            escalation_reasons.append(
                f"Multiplas interacoes de alto risco ({len(high_interactions)})"
            )

        # Regra 5: Polifarmácia em idoso
        if patient_context.is_geriatric_polypharmacy():
            needs_escalation = True
            escalation_reasons.append(
                f"Polifarmacia em idoso ({len(patient_context.current_medications)} medicamentos)"
            )

        # Regra 6: Insuficiência renal + droga nefrotóxica
        if PopulationRisk.RENAL_IMPAIRED in patient_context.get_population_risks():
            nephrotoxic = POPULATION_DRUG_ALERTS[PopulationRisk.RENAL_IMPAIRED].get(
                "high_risk", []
            )
            if any(n in drug_name.lower() for n in nephrotoxic):
                needs_escalation = True
                escalation_reasons.append(
                    "Droga nefrotoxica em paciente com funcao renal comprometida"
                )

        # Regra 7: Baixa confiança + alto risco
        if confidence < 0.7 and severity in ["high", "critical"]:
            needs_escalation = True
            escalation_reasons.append(
                f"Baixa confianca ({confidence:.0%}) com risco {severity}"
            )

        return needs_escalation, escalation_reasons

    def generate_structured_recommendations(
        self,
        severity: str,
        category: str,
        interactions: List[Dict[str, Any]],
        contraindications: List[Dict[str, Any]],
        patient_context: PatientContext,
    ) -> Dict[str, Any]:
        """
        Gerar recomendações estruturadas baseadas na análise

        Returns:
            Dict com recomendações organizadas por tipo
        """
        base_template = RECOMMENDATION_TEMPLATES.get(
            severity, RECOMMENDATION_TEMPLATES["medium"]
        )
        category_specific = CATEGORY_RECOMMENDATIONS.get(category, {})

        recommendations = {
            "header": base_template["header"],
            "immediate_actions": list(base_template.get("actions", [])),
            "monitoring_required": list(base_template.get("monitoring", [])),
            "laboratory_tests": list(category_specific.get("labs", [])),
            "patient_alerts": list(category_specific.get("alerts", [])),
            "alternatives": [],
            "follow_up": [],
            "patient_counseling": [],
        }

        # Adicionar monitoramento específico da categoria
        if category_specific.get("monitoring"):
            recommendations["monitoring_required"].extend(
                category_specific["monitoring"]
            )

        # Ajustes por população
        if patient_context.pregnant:
            recommendations["patient_counseling"].append(
                "Discutir riscos e beneficios com obstetra"
            )

        if patient_context.is_geriatric_polypharmacy():
            recommendations["immediate_actions"].append(
                "Revisar lista completa de medicamentos para desprescricao"
            )
            recommendations["monitoring_required"].append(
                "Avaliacao de risco de quedas"
            )

        if PopulationRisk.RENAL_IMPAIRED in patient_context.get_population_risks():
            recommendations["laboratory_tests"].append(
                "Creatinina e clearance de creatinina seriados"
            )
            recommendations["follow_up"].append(
                "Ajuste de dose baseado em funcao renal"
            )

        # Adicionar interações encontradas como alertas
        for interaction in interactions[:3]:  # Top 3
            drug1 = interaction.get("drug1", "?")
            drug2 = interaction.get("drug2", "?")
            sev = interaction.get("severity", "?").upper()
            recommendations["patient_alerts"].append(
                f"Interacao {sev}: {drug1} + {drug2}"
            )

        # Remover duplicatas mantendo ordem
        for key in recommendations:
            if isinstance(recommendations[key], list):
                seen = set()
                unique = []
                for item in recommendations[key]:
                    if item not in seen:
                        seen.add(item)
                        unique.append(item)
                recommendations[key] = unique

        return recommendations


# Instância global
_rules_engine = None


def get_rules_engine() -> ClinicalRulesEngine:
    """Obter instância singleton do motor de regras"""
    global _rules_engine
    if _rules_engine is None:
        _rules_engine = ClinicalRulesEngine()
    return _rules_engine
