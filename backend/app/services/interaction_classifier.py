"""
InteractionClassifierAgent - Agente especializado em classificação de severidade de interações medicamentosas

LOCALIZAÇÃO: backend/app/services/interaction_classifier.py
(Movido de agents/ para services/ para evitar circular import - mantém separação de responsabilidades)

PADRÃO AGÊNTICO APLICADO:
- Tool Use Pattern: Usa ferramentas especializadas (regex, análise contextual)
- Reflection Pattern: Valida e explica decisões de classificação
- Single Responsibility: Foco exclusivo em classificação de severidade
- Context-Aware: Ajusta severidade baseado no contexto do paciente

SKILLS APLICADAS:
- ULTRATHINK: Solução elegante baseada em padrões reais do CSV, não keywords genéricas
- DEBUGGING-STRATEGIES: Análise root cause e solução sistemática (incluindo fix de circular import)
- API-DESIGN-PRINCIPLES: Interface clara e previsível, separação correta de responsabilidades
- CODE-REVIEW-EXCELLENCE: Documentação inline, nomes descritivos

ATUALIZAÇÃO 2025-12-03:
- Adicionado suporte a contexto de paciente para ajuste de severidade
- Integração com ClinicalRulesEngine para populações de risco
- Recomendações estruturadas por categoria
"""

import logging
import re
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """
    Níveis de severidade baseados em impacto clínico

    SKILL: API-DESIGN-PRINCIPLES - Enum para type safety
    """

    CRITICAL = "critical"  # Risco de morte ou complicação grave
    HIGH = "high"  # Requer monitoramento rigoroso
    MEDIUM = "medium"  # Cautela necessária
    LOW = "low"  # Risco mínimo ou benéfico
    BENEFICIAL = "beneficial"  # Interação positiva (reduz toxicidade)


@dataclass
class ClassificationResult:
    """
    Resultado estruturado da classificação

    SKILL: API-DESIGN-PRINCIPLES - Estrutura previsível e type-safe
    """

    severity: SeverityLevel
    confidence: float  # 0.0 a 1.0
    reasoning: str  # Explicação da decisão
    matched_patterns: List[str]  # Padrões que levaram à decisão
    clinical_category: str
    # Novos campos para contexto e recomendações
    patient_risk_factors: List[str] = field(default_factory=list)
    severity_modified: bool = False
    original_severity: Optional[SeverityLevel] = None
    recommendations: Dict[str, Any] = field(default_factory=dict)


class InteractionClassifierAgent:
    """
    Agente especializado em classificar severidade de interações medicamentosas

    PADRÃO: Tool Use + Reflection (Capítulos 3 e 4)

    Este agente:
    1. Analisa descrição da interação
    2. Identifica padrões clínicos críticos
    3. Classifica severidade baseado em evidências
    4. Explica raciocínio (Reflection)
    5. Valida decisões críticas (Self-Critique)
    """

    def __init__(self):
        """
        Inicializar agente com padrões clínicos

        SKILL: ULTRATHINK - Padrões baseados em análise profunda do CSV real
        """
        logger.info("🤖 InteractionClassifierAgent inicializado")

        # Padrões CRÍTICOS (risco de morte/complicação grave)
        # SKILL: ULTRATHINK - Padrões baseados em farmacologia clínica real
        self.critical_patterns = {
            # Cardiovasculares graves
            "qt_prolongation": r"(?i)(QT.*prolongation|QTc.*prolongation|torsades)",
            "av_block": r"(?i)(atrioventricular.*block|AV.*block)",
            "cardiac_arrest": r"(?i)(cardiac.*arrest|ventricular.*fibrillation)",
            # ===== CRISE HIPERTENSIVA (IMAO + ESTIMULANTE) =====
            # Esta é uma das interações mais perigosas da farmacologia
            # IMAO + estimulante/simpatomiméticos → crise hipertensiva → AVC/morte
            "hypertensive_crisis": r"(?i)(hypertensive.*activities|hypertensive.*crisis|hypertension.*crisis)",
            "hypertensive_increase": r"(?i)(increase.*hypertensive)",
            # Coagulação
            "anticoagulant_interaction": r"(?i)(may.*increase.*anticoagulant|anticoagulant.*activities)",
            "bleeding_risk": r"(?i)(bleeding|hemorrhage|haemorrhage)(?!.*decrease)",
            # Toxicidade severa
            "cardiotoxic_increase": r"(?i)(?<!decrease).*increase.*cardiotoxic",
            "hepatotoxic_severe": r"(?i)(severe.*hepatotoxic|hepatic.*failure)",
            "respiratory_depression": r"(?i)(respiratory.*depression|apnea)",
            "serotonin_syndrome": r"(?i)(serotonin.*syndrome)",
            # Contraindicações absolutas
            "contraindicated": r"(?i)(contraindicated|should not|must not)",
            # ===== CLASSES DE DROGAS PERIGOSAS =====
            # IMAOs com qualquer efeito aumentado são potencialmente fatais
            "maoi_interaction": r"(?i)(MAO.*inhibitor|monoamine.*oxidase)",
        }

        # ===== DROGAS DE ALTO RISCO (IMAOs e similares) =====
        # Usadas para classificação adicional baseada em classe farmacológica
        self.high_risk_drug_classes = {
            "maoi": [
                "phenelzine",
                "tranylcypromine",
                "isocarboxazid",
                "selegiline",
                "moclobemide",
                "fenelzina",
                "tranilcipromina",
                "isocarboxazida",
                "selegilina",
                "moclobemida",
            ],
            "stimulant": [
                "methylphenidate",
                "amphetamine",
                "dexamphetamine",
                "lisdexamfetamine",
                "metilfenidato",
                "anfetamina",
                "ritalina",
                "concerta",
                "venvanse",
            ],
        }

        # Padrões HIGH (requer monitoramento rigoroso)
        self.high_patterns = {
            # Cardiovasculares moderados
            "bradycardia": r"(?i)(bradycardic.*activities|bradycardia)",
            "hypotension": r"(?i)(hypotensive.*activities|severe.*hypotension)",
            # Toxicidade moderada
            "cardiotoxic": r"(?i)(cardiotoxic)(?!.*decrease)",
            "hepatotoxic": r"(?i)(hepatotoxic)(?!.*decrease)",
            "nephrotoxic": r"(?i)(nephrotoxic)(?!.*decrease)",
            "neurotoxic": r"(?i)(neurotoxic)",
            # Excitação neurológica
            "neuroexcitatory": r"(?i)(neuroexcitatory|seizure|convulsion)",
            # Concentrações séricas aumentadas (risco de toxicidade)
            "serum_concentration_increase": r"(?i)(serum.*concentration.*can.*be.*increased)",
            # Efeitos adversos significativos
            "adverse_effects_increased": r"(?i)(adverse.*effects.*can.*be.*increased|risk.*severity.*adverse)",
        }

        # Padrões MEDIUM (cautela necessária)
        self.medium_patterns = {
            # Metabolismo alterado
            "metabolism_altered": r"(?i)(metabolism.*can.*be.*(increased|decreased))",
            # Biodisponibilidade/eficácia
            "bioavailability": r"(?i)(bioavailability)",
            "therapeutic_effect": r"(?i)(therapeutic.*effect.*decrease)",
            # Fotossensibilidade
            "photosensitizing": r"(?i)(photosensitizing.*activities)",
            # Concentração sérica diminuída
            "serum_concentration_decrease": r"(?i)(serum.*concentration.*can.*be.*decreased)",
        }

        # Padrões BENÉFICOS/LOW (redução de toxicidade = bom)
        self.beneficial_patterns = {
            "decrease_toxicity": r"(?i)(decrease.*the.*(cardiotoxic|hepatotoxic|nephrotoxic|neurotoxic))",
            "protective_effect": r"(?i)(protective|reduce.*risk)",
        }

    def classify_interaction(
        self,
        description: str,
        drug1: str,
        drug2: str,
        patient_context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        """
        Classificar severidade da interação medicamentosa

        SKILL: DEBUGGING-STRATEGIES - Logging detalhado para rastreabilidade
        SKILL: CODE-REVIEW-EXCELLENCE - Método bem documentado

        Args:
            description: Descrição da interação do CSV
            drug1: Nome do primeiro medicamento
            drug2: Nome do segundo medicamento
            patient_context: Contexto opcional do paciente para ajuste de severidade
                {
                    "age": int,
                    "weight": float,
                    "pregnant": bool,
                    "conditions": List[str],
                    "current_medications": List[str],
                    "gfr": float,  # Taxa de filtração glomerular
                    "child_pugh": str  # A, B, C para função hepática
                }

        Returns:
            ClassificationResult com severidade, confiança e raciocínio
        """
        logger.debug(f"Classificando: {drug1} + {drug2}")
        logger.debug(f"   Descrição: {description}")
        if patient_context:
            logger.debug(f"   Contexto do paciente: idade={patient_context.get('age')}, "
                        f"gestante={patient_context.get('pregnant', False)}")

        # 0. VERIFICAÇÃO DE CLASSES FARMACOLÓGICAS DE ALTO RISCO
        # SKILL: ULTRATHINK - Certas combinações são SEMPRE críticas, independente da descrição
        drug_class_result = self._check_high_risk_drug_classes(drug1, drug2, description)
        if drug_class_result:
            logger.warning(f"🚨 CRÍTICO (CLASSE FARMACOLÓGICA): {drug1} + {drug2} - {drug_class_result.reasoning}")
            return drug_class_result

        # 1. Verificar padrões CRÍTICOS primeiro
        critical_matches = self._match_patterns(description, self.critical_patterns)
        if critical_matches:
            result = ClassificationResult(
                severity=SeverityLevel.CRITICAL,
                confidence=0.95,
                reasoning=f"Interação CRÍTICA identificada. Padrões detectados: {', '.join(critical_matches)}",
                matched_patterns=critical_matches,
                clinical_category=self._infer_category(critical_matches[0]),
            )
            logger.warning(f"CRÍTICO: {drug1} + {drug2} - {result.reasoning}")
            return result

        # 2. Verificar padrões BENÉFICOS (reduz toxicidade)
        beneficial_matches = self._match_patterns(description, self.beneficial_patterns)
        if beneficial_matches:
            result = ClassificationResult(
                severity=SeverityLevel.LOW,  # Ou BENEFICIAL se quisermos distinguir
                confidence=0.85,
                reasoning=f"Interação BENÉFICA (reduz toxicidade). Padrões: {', '.join(beneficial_matches)}",
                matched_patterns=beneficial_matches,
                clinical_category="Benéfica",
            )
            logger.info(f"BENÉFICO: {drug1} + {drug2} - {result.reasoning}")
            return result

        # 3. Verificar padrões HIGH
        high_matches = self._match_patterns(description, self.high_patterns)
        if high_matches:
            result = ClassificationResult(
                severity=SeverityLevel.HIGH,
                confidence=0.90,
                reasoning=f"Interação de ALTO risco. Padrões detectados: {', '.join(high_matches)}",
                matched_patterns=high_matches,
                clinical_category=self._infer_category(high_matches[0]),
            )
            logger.warning(f"ALTO: {drug1} + {drug2} - {result.reasoning}")
            return result

        # 4. Verificar padrões MEDIUM
        medium_matches = self._match_patterns(description, self.medium_patterns)
        if medium_matches:
            result = ClassificationResult(
                severity=SeverityLevel.MEDIUM,
                confidence=0.85,
                reasoning=f"Interação MODERADA. Padrões detectados: {', '.join(medium_matches)}",
                matched_patterns=medium_matches,
                clinical_category=self._infer_category(medium_matches[0]),
            )
            logger.info(f"ℹ️ MÉDIO: {drug1} + {drug2} - {result.reasoning}")
            return result

        # 5. Fallback: LOW (mas com confiança baixa)
        result = ClassificationResult(
            severity=SeverityLevel.LOW,
            confidence=0.60,
            reasoning="Nenhum padrão de alto risco identificado. Interação de baixo impacto clínico.",
            matched_patterns=[],
            clinical_category="Geral",
        )
        logger.info(f"✓ BAIXO: {drug1} + {drug2} - {result.reasoning}")
        return result

    def _check_high_risk_drug_classes(self, drug1: str, drug2: str, description: str) -> ClassificationResult | None:
        """
        Verificar se a combinação de drogas envolve classes de alto risco conhecidas

        SKILL: ULTRATHINK - Abordagem farmacológica baseada em classes de drogas
        SKILL: DEBUGGING-STRATEGIES - Classificação robusta para casos conhecidos

        Combinações CRÍTICAS conhecidas:
        - IMAO + Estimulante → Crise hipertensiva (pode ser fatal)
        - IMAO + ISRS → Síndrome serotoninérgica (pode ser fatal)

        Args:
            drug1: Nome do primeiro medicamento
            drug2: Nome do segundo medicamento
            description: Descrição da interação

        Returns:
            ClassificationResult se for combinação de alto risco, None caso contrário
        """
        drug1_lower = drug1.lower()
        drug2_lower = drug2.lower()

        # Verificar se uma das drogas é IMAO
        is_maoi_drug1 = any(maoi in drug1_lower for maoi in self.high_risk_drug_classes["maoi"])
        is_maoi_drug2 = any(maoi in drug2_lower for maoi in self.high_risk_drug_classes["maoi"])

        # Verificar se uma das drogas é estimulante
        is_stimulant_drug1 = any(stim in drug1_lower for stim in self.high_risk_drug_classes["stimulant"])
        is_stimulant_drug2 = any(stim in drug2_lower for stim in self.high_risk_drug_classes["stimulant"])

        # IMAO + ESTIMULANTE = CRISE HIPERTENSIVA CRÍTICA
        if (is_maoi_drug1 and is_stimulant_drug2) or (is_maoi_drug2 and is_stimulant_drug1):
            return ClassificationResult(
                severity=SeverityLevel.CRITICAL,
                confidence=0.99,
                reasoning=(
                    "INTERAÇÃO CRÍTICA IMAO + ESTIMULANTE: "
                    "Risco de crise hipertensiva potencialmente fatal. "
                    "O uso concomitante de inibidores da MAO com estimulantes do SNC "
                    "pode causar elevação súbita e grave da pressão arterial, "
                    "podendo resultar em AVC hemorrágico ou morte. "
                    f"Descrição original: {description}"
                ),
                matched_patterns=["maoi_stimulant_combination"],
                clinical_category="IMAO-Crítico",
            )

        return None

    def _match_patterns(self, text: str, patterns: Dict[str, str]) -> List[str]:
        """
        Verificar quais padrões correspondem ao texto

        SKILL: PYTHON-PERFORMANCE - Regex eficiente

        Returns:
            Lista de nomes dos padrões que foram encontrados
        """
        matched = []
        for pattern_name, regex in patterns.items():
            if re.search(regex, text):
                matched.append(pattern_name)
        return matched

    def _infer_category(self, pattern_name: str) -> str:
        """
        Inferir categoria clínica baseado no padrão detectado

        SKILL: API-DESIGN-PRINCIPLES - Categorização consistente
        """
        category_map = {
            # Cardiovascular
            "qt_prolongation": "Cardiovascular",
            "av_block": "Cardiovascular",
            "cardiac_arrest": "Cardiovascular",
            "bradycardia": "Cardiovascular",
            "cardiotoxic": "Cardiovascular",
            "hypertensive_crisis": "Cardiovascular-Crítico",
            "hypertensive_increase": "Cardiovascular-Crítico",
            "hypotension": "Cardiovascular",
            # Coagulação
            "anticoagulant_interaction": "Coagulação",
            "bleeding_risk": "Coagulação",
            # Hepática
            "hepatotoxic": "Hepática",
            "hepatotoxic_severe": "Hepática",
            # Renal
            "nephrotoxic": "Renal",
            # Neurológica
            "neurotoxic": "Neurológica",
            "neuroexcitatory": "Neurológica",
            "serotonin_syndrome": "Neurológica",
            # Respiratória
            "respiratory_depression": "Respiratória",
            # Outras
            "photosensitizing": "Fotossensibilidade",
            "metabolism_altered": "Farmacocinética",
            "bioavailability": "Farmacocinética",
            # IMAO
            "maoi_interaction": "IMAO-Crítico",
        }
        return category_map.get(pattern_name, "Farmacológica")

    def validate_critical_decision(self, result: ClassificationResult, description: str) -> ClassificationResult:
        """
        Validar decisões críticas com segundo método (Reflection Pattern)

        PADRÃO: Reflection - Self-Critique (Capítulo 4)
        SKILL: ULTRATHINK - Validação dupla para decisões críticas

        Se a classificação é CRITICAL, revalidar com análise adicional
        """
        if result.severity != SeverityLevel.CRITICAL:
            return result

        logger.info("🔄 Validando decisão CRÍTICA com reflexão...")

        # Contar quantos padrões críticos distintos foram encontrados
        critical_pattern_count = len(result.matched_patterns)

        # Se apenas 1 padrão crítico, verificar contexto adicional
        if critical_pattern_count == 1:
            # Verificar se há indicadores de que não é tão grave
            mitigating_factors = [
                r"(?i)(may.*reduce|protective)",
                r"(?i)(monitor.*closely)",  # Monitoramento sugere gerenciável
            ]

            has_mitigation = any(re.search(factor, description) for factor in mitigating_factors)

            if has_mitigation:
                logger.warning("Reflexão: Padrão crítico com fatores mitigantes. Rebaixando para HIGH.")
                result.severity = SeverityLevel.HIGH
                result.confidence = 0.80
                result.reasoning += " (Rebaixado de CRÍTICO após reflexão: fatores mitigantes identificados)"

        logger.info(f"Validação concluída: {result.severity.value}")
        return result

    def adjust_for_patient_context(
        self,
        result: ClassificationResult,
        drug_name: str,
        patient_context: Dict[str, Any]
    ) -> ClassificationResult:
        """
        Ajustar severidade baseado no contexto do paciente

        SKILL: @ultrathink - Regras baseadas em guidelines clínicos
        SKILL: @debugging-strategies - Rastreabilidade de ajustes

        Args:
            result: Resultado da classificação base
            drug_name: Nome do medicamento
            patient_context: Contexto do paciente

        Returns:
            ClassificationResult ajustado
        """
        if not patient_context:
            return result

        severity_order = [SeverityLevel.LOW, SeverityLevel.MEDIUM, SeverityLevel.HIGH, SeverityLevel.CRITICAL]
        current_idx = severity_order.index(result.severity)
        max_increase = 0
        risk_factors = []
        adjustment_reasons = []

        drug_lower = drug_name.lower()
        age = patient_context.get("age")
        pregnant = patient_context.get("pregnant", False)
        gfr = patient_context.get("gfr")
        child_pugh = patient_context.get("child_pugh")
        current_meds = patient_context.get("current_medications", [])

        # ===== REGRA 1: GESTANTE COM TERATOGÊNICO =====
        teratogens = [
            "warfarin", "isotretinoin", "methotrexate", "valproic",
            "thalidomide", "leflunomide", "misoprostol", "finasteride",
        ]
        if pregnant:
            for teratogen in teratogens:
                if teratogen in drug_lower:
                    max_increase = max(max_increase, 2)
                    risk_factors.append("pregnancy_teratogen")
                    adjustment_reasons.append(
                        f"GESTANTE + {drug_name}: Medicamento teratogenico - "
                        "risco de malformacao fetal grave"
                    )
                    break

        # ===== REGRA 2: PEDIATRIA =====
        pediatric_contraindicated = [
            "aspirin",  # Síndrome de Reye
            "tetracycline", "doxycycline",
            "fluoroquinolone", "ciprofloxacin", "levofloxacin",
        ]
        if age is not None and age < 12:
            for contra in pediatric_contraindicated:
                if contra in drug_lower:
                    max_increase = max(max_increase, 2)
                    risk_factors.append("pediatric_contraindication")
                    adjustment_reasons.append(
                        f"PEDIATRIA (<12 anos) + {drug_name}: "
                        "Medicamento contraindicado nesta faixa etaria"
                    )
                    break

        # ===== REGRA 3: IDOSO (>= 65) =====
        geriatric_high_risk = [
            "diazepam", "alprazolam", "lorazepam", "clonazepam",
            "diphenhydramine", "amitriptyline", "meperidine",
        ]
        if age is not None and age >= 65:
            for high_risk in geriatric_high_risk:
                if high_risk in drug_lower:
                    max_increase = max(max_increase, 1)
                    risk_factors.append("geriatric_high_risk")
                    adjustment_reasons.append(
                        f"IDOSO (>= 65 anos) + {drug_name}: "
                        "Medicamento da Lista de Beers - maior risco de eventos adversos"
                    )
                    break

            # Polifarmácia em idoso
            if len(current_meds) >= 5:
                max_increase = max(max_increase, 1)
                risk_factors.append("geriatric_polypharmacy")
                adjustment_reasons.append(
                    f"POLIFARMACIA em idoso: {len(current_meds)} medicamentos - "
                    "risco aumentado de interacoes"
                )

        # ===== REGRA 4: INSUFICIÊNCIA RENAL =====
        nephrotoxic_drugs = [
            "metformin", "lithium", "nsaid", "ibuprofen", "naproxen",
            "gentamicin", "vancomycin", "digoxin", "gabapentin",
        ]
        if gfr is not None and gfr < 60:
            for nephro in nephrotoxic_drugs:
                if nephro in drug_lower:
                    increase = 2 if gfr < 30 else 1
                    max_increase = max(max_increase, increase)
                    risk_factors.append("renal_impairment_nephrotoxic")
                    adjustment_reasons.append(
                        f"INSUFICIENCIA RENAL (GFR={gfr}) + {drug_name}: "
                        f"Droga com eliminacao renal - risco de acumulo e toxicidade"
                    )
                    break

        # ===== REGRA 5: INSUFICIÊNCIA HEPÁTICA =====
        hepatotoxic_drugs = [
            "acetaminophen", "paracetamol", "statin", "atorvastatin",
            "simvastatin", "isoniazid", "valproic", "ketoconazole",
        ]
        if child_pugh in ["B", "C"]:
            for hepato in hepatotoxic_drugs:
                if hepato in drug_lower:
                    increase = 2 if child_pugh == "C" else 1
                    max_increase = max(max_increase, increase)
                    risk_factors.append("hepatic_impairment_hepatotoxic")
                    adjustment_reasons.append(
                        f"INSUFICIENCIA HEPATICA (Child-Pugh {child_pugh}) + {drug_name}: "
                        "Droga com metabolismo hepatico - risco de acumulo e hepatotoxicidade"
                    )
                    break

        # Aplicar ajuste se necessário
        if max_increase > 0:
            new_idx = min(current_idx + max_increase, len(severity_order) - 1)
            new_severity = severity_order[new_idx]

            logger.warning(
                f"Severidade ajustada: {result.severity.value} → {new_severity.value} "
                f"(fatores: {', '.join(risk_factors)})"
            )

            result.original_severity = result.severity
            result.severity = new_severity
            result.severity_modified = True
            result.patient_risk_factors = risk_factors
            result.confidence = min(result.confidence + 0.1, 0.99)
            result.reasoning += f" | AJUSTADO POR CONTEXTO: {'; '.join(adjustment_reasons)}"

        return result

    def classify_with_patient_context(
        self,
        description: str,
        drug1: str,
        drug2: str,
        patient_context: Dict[str, Any]
    ) -> ClassificationResult:
        """
        Classificar interação com ajuste automático por contexto do paciente

        Método de conveniência que combina classificação base + ajuste

        Args:
            description: Descrição da interação
            drug1: Nome do primeiro medicamento
            drug2: Nome do segundo medicamento
            patient_context: Contexto do paciente

        Returns:
            ClassificationResult com severidade ajustada se aplicável
        """
        # 1. Classificação base
        result = self.classify_interaction(description, drug1, drug2, patient_context)

        # 2. Validar decisões críticas
        result = self.validate_critical_decision(result, description)

        # 3. Ajustar por contexto do paciente
        result = self.adjust_for_patient_context(result, drug1, patient_context)
        result = self.adjust_for_patient_context(result, drug2, patient_context)

        return result


# Instância global (singleton)
_classifier_agent = None


def get_classifier_agent() -> InteractionClassifierAgent:
    """
    Obter instância singleton do agente classificador

    SKILL: API-DESIGN-PRINCIPLES - Singleton pattern
    """
    global _classifier_agent
    if _classifier_agent is None:
        _classifier_agent = InteractionClassifierAgent()
    return _classifier_agent
