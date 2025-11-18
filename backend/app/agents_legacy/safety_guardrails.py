"""
MedicalSafetyGuardrails - Guardrails de segurança para aplicações médicas
Implementa padrão de Guardrails/Safety do Capítulo 18 - Agentic Design Patterns

Responsabilidades:
- Validar recomendações contra diretrizes ANVISA/OMS
- Detectar alucinações do LLM
- Injetar disclaimers legais obrigatórios
- Bloquear conselhos médicos não autorizados
- Filtrar conteúdo perigoso ou inadequado
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class RiskCategory(str, Enum):
    """Categorias de risco de conteúdo"""
    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"


class GuardrailViolation(Exception):
    """Exceção para violações de guardrails"""
    def __init__(self, violation_type: str, message: str, severity: str):
        self.violation_type = violation_type
        self.message = message
        self.severity = severity
        super().__init__(f"{violation_type}: {message}")


class MedicalSafetyGuardrails:
    """
    Sistema de guardrails de segurança médica
    Implementa múltiplas camadas de validação e proteção
    """

    def __init__(self):
        """Inicializar guardrails"""
        self.blocked_phrases = self._load_blocked_phrases()
        self.required_disclaimers = self._load_disclaimers()
        self.anvisa_guidelines = self._load_anvisa_guidelines()

        logger.info("🛡️ MedicalSafetyGuardrails inicializado")

    def _load_blocked_phrases(self) -> List[str]:
        """Carregar frases proibidas que nunca devem aparecer"""
        return [
            # Conselhos médicos diretos não autorizados
            r"você deve tomar",
            r"recomendo que use",
            r"substitua.*por",
            r"pare.*de tomar",
            r"aumente.*dose",
            r"diminua.*dose",

            # Diagnósticos diretos
            r"você tem",
            r"você está com",
            r"diagnóstico.*de",

            # Garantias absolutas (nunca garantir em medicina)
            r"com certeza",
            r"100% seguro",
            r"sem risco",
            r"impossível.*causar",
            r"nunca causa",

            # Comparações perigosas
            r"melhor que.*prescrição",
            r"não precisa.*médico",
            r"substitui.*consulta",
        ]

    def _load_disclaimers(self) -> Dict[str, str]:
        """Carregar disclaimers legais obrigatórios"""
        return {
            "main": """
⚠️ AVISO LEGAL IMPORTANTE:

Esta análise é APENAS INFORMATIVA e não substitui consulta médica, diagnóstico ou
tratamento profissional. As informações fornecidas são baseadas em dados públicos
e algoritmos de inteligência artificial que podem conter imprecisões.

SEMPRE consulte um médico, farmacêutico ou profissional de saúde habilitado antes de:
- Iniciar ou interromper qualquer medicamento
- Modificar doses prescritas
- Tomar decisões sobre sua saúde

EM CASO DE EMERGÊNCIA, procure imediatamente atendimento médico presencial ou ligue 192 (SAMU).

O MedSafe não se responsabiliza por decisões tomadas com base nestas informações.
""",
            "high_risk": """
🔴 ALERTA DE ALTO RISCO:

Esta análise identificou potenciais riscos SIGNIFICATIVOS. É FUNDAMENTAL que você:
1. Consulte um médico IMEDIATAMENTE
2. NÃO tome decisões sem supervisão médica
3. Informe ao profissional de saúde sobre TODOS os medicamentos em uso

Decisões inadequadas podem colocar sua saúde em risco grave.
""",
            "critical_risk": """
🚨 ALERTA CRÍTICO - AÇÃO IMEDIATA NECESSÁRIA:

Esta análise identificou CONTRAINDICAÇÕES CRÍTICAS ou INTERAÇÕES GRAVES.

⚠️ NÃO USE este medicamento sem avaliação médica URGENTE.
⚠️ Se já estiver usando, CONSULTE UM MÉDICO IMEDIATAMENTE.
⚠️ Em caso de sintomas adversos, procure EMERGÊNCIA MÉDICA (192 - SAMU).

Esta é uma situação potencialmente PERIGOSA que requer INTERVENÇÃO PROFISSIONAL.
""",
            "pregnancy": """
🤰 AVISO ESPECIAL - GRAVIDEZ:

Medicamentos durante a gravidez requerem avaliação OBRIGATÓRIA por obstetra.
Alguns medicamentos podem causar malformações fetais graves.

CONSULTE SEU OBSTETRA antes de usar qualquer medicamento.
""",
            "pediatric": """
👶 AVISO ESPECIAL - USO PEDIÁTRICO:

Medicamentos para crianças requerem cálculo de dose por PEDIATRA habilitado.
Doses adultas podem ser PERIGOSAS para crianças.

CONSULTE UM PEDIATRA antes de administrar qualquer medicamento.
""",
            "elderly": """
👴 AVISO ESPECIAL - USO GERIÁTRICO:

Idosos têm metabolismo diferente e maior risco de reações adversas.
Ajustes de dose são frequentemente necessários.

CONSULTE UM GERIATRA ou médico responsável para orientações específicas.
"""
        }

    def _load_anvisa_guidelines(self) -> Dict[str, Any]:
        """Carregar diretrizes ANVISA (simplificado)"""
        return {
            "pregnancy_categories": {
                "A": "Seguro na gravidez (estudos adequados não demonstraram risco)",
                "B": "Provavelmente seguro (sem evidência de risco em humanos)",
                "C": "Risco não pode ser descartado (faltam estudos adequados)",
                "D": "Evidência positiva de risco (usar apenas se benefício justificar)",
                "X": "CONTRAINDICADO na gravidez (risco supera qualquer benefício)"
            },
            "controlled_substances": [
                "benzodiazepínicos", "opioides", "anfetaminas",
                "barbitúricos", "anabolizantes"
            ],
            "high_risk_medications": [
                "varfarina", "metotrexato", "lítio", "digoxina",
                "insulina", "anticoagulantes"
            ]
        }

    async def validate_analysis(
        self,
        analysis: Dict[str, Any],
        triage_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validar análise completa com todos os guardrails

        Args:
            analysis: Análise gerada pelos agentes
            triage_data: Dados da triagem do paciente

        Returns:
            Análise validada e enriquecida com disclaimers

        Raises:
            GuardrailViolation: Se violação crítica for detectada
        """
        logger.info("🛡️ Iniciando validação de guardrails...")

        try:
            # 1. Verificar conteúdo proibido (ANTES de injetar disclaimers)
            self._check_blocked_content(analysis)

            # 2. Detectar alucinações
            hallucination_score = await self._detect_hallucinations(analysis)
            analysis['hallucination_risk'] = hallucination_score

            # 3. Validar conformidade regulatória
            compliance_issues = self._check_regulatory_compliance(analysis, triage_data)
            analysis['compliance_issues'] = compliance_issues

            # 4. Verificar autorização para recomendações
            self._validate_recommendation_authority(analysis)

            # 5. Classificar risco de segurança (antes de disclaimers)
            safety_classification = self._classify_safety_risk(analysis)
            analysis['safety_classification'] = safety_classification

            # 6. Injetar disclaimers apropriados (APÓS todas as validações)
            analysis = self._inject_disclaimers(analysis, triage_data)

            # 7. Adicionar metadados de validação
            analysis['guardrails_validated'] = True
            analysis['validation_timestamp'] = datetime.now().isoformat()
            analysis['guardrails_version'] = "1.0.0"

            logger.info(f"✅ Guardrails validados - Classificação: {safety_classification}")

            return analysis

        except GuardrailViolation as e:
            logger.error(f"🚫 Violação de guardrail: {e.violation_type} - {e.message}")
            raise
        except Exception as e:
            logger.error(f"❌ Erro na validação de guardrails: {e}")
            # Em caso de erro, adicionar disclaimer de falha
            analysis['guardrails_validated'] = False
            analysis['guardrails_error'] = str(e)
            analysis = self._inject_disclaimers(analysis, triage_data, force_critical=True)
            return analysis

    def _check_blocked_content(self, analysis: Dict[str, Any]) -> None:
        """
        Verificar se análise contém conteúdo proibido

        NOTA: Esta verificação é feita ANTES de injetar disclaimers,
        pois os disclaimers legítimos podem conter frases como "não substitui consulta"

        Raises:
            GuardrailViolation: Se conteúdo proibido for encontrado
        """
        # Concatenar apenas o conteúdo gerado (não inclui disclaimers que serão injetados depois)
        text_to_check = " ".join([
            # NÃO incluir analysis_notes aqui pois pode já ter disclaimers
            str(analysis.get('recommendations', [])),
            " ".join([str(c.get('description', '')) for c in analysis.get('contraindications', [])]),
            " ".join([str(i.get('recommendation', '')) for i in analysis.get('interactions', [])]),
            " ".join([str(i.get('effect', '')) for i in analysis.get('interactions', [])])
        ]).lower()

        # Verificar cada padrão proibido
        for pattern in self.blocked_phrases:
            if re.search(pattern, text_to_check, re.IGNORECASE):
                raise GuardrailViolation(
                    violation_type="BLOCKED_CONTENT",
                    message=f"Conteúdo proibido detectado: padrão '{pattern}'",
                    severity="critical"
                )

        logger.debug("✅ Nenhum conteúdo proibido detectado")

    async def _detect_hallucinations(self, analysis: Dict[str, Any]) -> float:
        """
        Detectar possíveis alucinações do LLM

        Retorna score de 0 (sem alucinação) a 1 (alta probabilidade de alucinação)
        """
        hallucination_indicators = []

        # 1. Verificar se há evidências para as afirmações
        evidence_links = analysis.get('evidence_links', [])
        if len(evidence_links) == 0:
            hallucination_indicators.append(0.3)  # Sem evidências = suspeito

        # 2. Verificar confidence score baixo
        confidence = analysis.get('confidence_score', 1.0)
        if confidence < 0.5:
            hallucination_indicators.append(0.4)  # Baixa confiança = possível alucinação

        # 3. Verificar inconsistências
        risk_level = analysis.get('risk_level', 'low')
        contraindications = analysis.get('contraindications', [])
        interactions = analysis.get('interactions', [])

        # Se risco é baixo mas há muitas contraindicações/interações = inconsistente
        if risk_level == 'low' and (len(contraindications) > 2 or len(interactions) > 2):
            hallucination_indicators.append(0.5)

        # Se risco é crítico mas sem contraindicações = inconsistente
        if risk_level == 'critical' and len(contraindications) == 0 and len(interactions) == 0:
            hallucination_indicators.append(0.6)

        # 4. Verificar declarações absolutas (sinal de alucinação)
        analysis_text = str(analysis.get('analysis_notes', '')).lower()
        absolute_phrases = [
            '100%', 'totalmente seguro', 'sem risco', 'impossível',
            'nunca causa', 'sempre seguro', 'com certeza'
        ]

        for phrase in absolute_phrases:
            if phrase in analysis_text:
                hallucination_indicators.append(0.4)
                break

        # Calcular score médio
        if hallucination_indicators:
            hallucination_score = sum(hallucination_indicators) / len(hallucination_indicators)
        else:
            hallucination_score = 0.0

        # Adicionar warning se score alto
        if hallucination_score > 0.5:
            logger.warning(f"⚠️ Alto risco de alucinação detectado: {hallucination_score:.2f}")
            analysis.setdefault('warnings', []).append(
                "Esta análise pode conter informações imprecisas (baixa evidência). "
                "Validação médica é ESSENCIAL."
            )

        return hallucination_score

    def _check_regulatory_compliance(
        self,
        analysis: Dict[str, Any],
        triage_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Verificar conformidade com regulamentações ANVISA"""
        issues = []

        # Verificar uso em gravidez
        if triage_data.get('pregnant', False):
            # Verificar se análise considera gravidez
            notes = str(analysis.get('analysis_notes', '')).lower()
            if 'gravidez' not in notes and 'gestante' not in notes:
                issues.append({
                    "type": "pregnancy_not_addressed",
                    "severity": "high",
                    "message": "Análise não abordou adequadamente o uso na gravidez"
                })

        # Verificar uso pediátrico
        age = triage_data.get('age', 0)
        if age < 18:
            dosage_adjustments = analysis.get('dosage_adjustments', [])
            has_pediatric_adjustment = any(
                'pediátrico' in str(adj).lower() or 'criança' in str(adj).lower()
                for adj in dosage_adjustments
            )

            if not has_pediatric_adjustment:
                issues.append({
                    "type": "pediatric_dosing_missing",
                    "severity": "critical",
                    "message": "Ajuste de dose pediátrica não foi especificado"
                })

        # Verificar substâncias controladas
        # (Aqui você verificaria contra lista da ANVISA)

        return issues

    def _validate_recommendation_authority(self, analysis: Dict[str, Any]) -> None:
        """
        Validar que sistema não está dando conselhos médicos diretos

        Raises:
            GuardrailViolation: Se recomendações inadequadas forem detectadas
        """
        # Verificar se há "recomendações" que são na verdade prescrições
        recommendations = analysis.get('recommendations', [])

        unauthorized_patterns = [
            r"tome\s+\d+",  # "tome 2 comprimidos"
            r"use\s+\d+",   # "use 500mg"
            r"administre",  # "administre pela manhã"
        ]

        for rec in recommendations:
            rec_text = str(rec).lower()
            for pattern in unauthorized_patterns:
                if re.search(pattern, rec_text):
                    raise GuardrailViolation(
                        violation_type="UNAUTHORIZED_PRESCRIPTION",
                        message="Sistema não pode prescrever medicamentos diretamente",
                        severity="critical"
                    )

    def _inject_disclaimers(
        self,
        analysis: Dict[str, Any],
        triage_data: Dict[str, Any],
        force_critical: bool = False
    ) -> Dict[str, Any]:
        """Injetar disclaimers legais apropriados"""
        disclaimers = [self.required_disclaimers['main']]

        # Disclaimer baseado em risco
        risk_level = analysis.get('risk_level', 'low')

        if force_critical or risk_level == 'critical':
            disclaimers.append(self.required_disclaimers['critical_risk'])
        elif risk_level == 'high':
            disclaimers.append(self.required_disclaimers['high_risk'])

        # Disclaimers para populações especiais
        if triage_data.get('pregnant', False):
            disclaimers.append(self.required_disclaimers['pregnancy'])

        age = triage_data.get('age', 0)
        if age < 18:
            disclaimers.append(self.required_disclaimers['pediatric'])
        elif age >= 65:
            disclaimers.append(self.required_disclaimers['elderly'])

        # Adicionar disclaimers à análise
        analysis['legal_disclaimers'] = disclaimers

        # Também adicionar ao início das notas de análise
        existing_notes = analysis.get('analysis_notes', '')
        analysis['analysis_notes'] = "\n\n".join(disclaimers) + "\n\n---\n\n" + existing_notes

        return analysis

    def _classify_safety_risk(self, analysis: Dict[str, Any]) -> str:
        """
        Classificar risco de segurança da análise

        Returns:
            "safe", "warning", "dangerous", "blocked"
        """
        # Verificar alucinação
        hallucination_risk = analysis.get('hallucination_risk', 0.0)
        if hallucination_risk > 0.7:
            return RiskCategory.DANGEROUS

        # Verificar compliance
        compliance_issues = analysis.get('compliance_issues', [])
        critical_issues = [i for i in compliance_issues if i.get('severity') == 'critical']
        if critical_issues:
            return RiskCategory.DANGEROUS

        # Verificar risco médico
        risk_level = analysis.get('risk_level', 'low')
        if risk_level == 'critical':
            return RiskCategory.WARNING
        elif risk_level == 'high':
            return RiskCategory.WARNING

        return RiskCategory.SAFE

    async def validate_medication_name(self, medication_name: str) -> Tuple[bool, Optional[str]]:
        """
        Validar nome de medicamento contra base ANVISA

        Returns:
            (is_valid, error_message)
        """
        # TODO: Integrar com API ANVISA real
        # Por enquanto, validação básica

        if not medication_name or len(medication_name.strip()) < 3:
            return False, "Nome de medicamento inválido ou muito curto"

        # Verificar se não é gibberish
        if not re.match(r'^[a-zA-Z0-9\s\-]+$', medication_name):
            return False, "Nome de medicamento contém caracteres inválidos"

        return True, None

    def sanitize_output(self, text: str) -> str:
        """
        Sanitizar texto de saída, removendo conteúdo perigoso

        Args:
            text: Texto a ser sanitizado

        Returns:
            Texto sanitizado e seguro
        """
        # Remover URLs suspeitas
        text = re.sub(r'https?://[^\s]+', '[URL removida por segurança]', text)

        # Remover emails
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                     '[email removido]', text)

        # Remover números de telefone
        text = re.sub(r'\b\d{10,11}\b', '[telefone removido]', text)

        # Limitar tamanho para prevenir DoS
        max_length = 50000
        if len(text) > max_length:
            text = text[:max_length] + "\n\n[Texto truncado por segurança]"

        return text


# Instância global (singleton)
_safety_guardrails = None


def get_safety_guardrails() -> MedicalSafetyGuardrails:
    """Obter instância singleton dos guardrails"""
    global _safety_guardrails
    if _safety_guardrails is None:
        _safety_guardrails = MedicalSafetyGuardrails()
    return _safety_guardrails
