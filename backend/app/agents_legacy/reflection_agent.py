"""
ReflectionAgent - Agente para auto-crítica e refinamento iterativo de análises clínicas
Implementa padrão Reflection (Self-Critique) do Capítulo 4 - Agentic Design Patterns

PADRÃO REFLECTION (Capítulo 4):
1. CRITIQUE: Agente analisa sua própria saída ou de outro agente
2. DETECT: Identifica erros, inconsistências, informações faltantes
3. FEEDBACK: Gera feedback estruturado para melhoria
4. REGENERATE: Cria versão melhorada baseada no feedback
5. ITERATE: Repete ciclo até atingir qualidade satisfatória

SKILLS APLICADAS:
- code-review-excellence: Lógica de crítica e checagem de qualidade
- debugging-strategies: Padrões de detecção de erros
- python-performance-optimization: Caching de reflexões
- fastapi-templates: Estrutura assíncrona e type hints
- api-design-principles: Interface clara e consistente
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import hashlib
from functools import lru_cache

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class ReflectionType(str, Enum):
    """Tipos de reflexão possíveis"""
    CONSISTENCY_CHECK = "consistency_check"
    EVIDENCE_VALIDATION = "evidence_validation"
    RISK_ASSESSMENT_REVIEW = "risk_assessment_review"
    COMPLETENESS_CHECK = "completeness_check"
    LOGICAL_COHERENCE = "logical_coherence"


class CritiqueLevel(str, Enum):
    """Níveis de severidade da crítica"""
    PASS = "pass"  # Análise está boa
    MINOR_ISSUES = "minor_issues"  # Problemas pequenos
    MAJOR_ISSUES = "major_issues"  # Problemas significativos
    CRITICAL_FLAWS = "critical_flaws"  # Falhas críticas, regenerar obrigatório


class ReflectionResult:
    """
    Resultado de uma reflexão

    SKILL: api-design-principles
    Estrutura clara e tipada para resultados
    """

    def __init__(
        self,
        critique_level: CritiqueLevel,
        issues_found: List[Dict[str, Any]],
        suggestions: List[str],
        confidence_score: float,
        should_regenerate: bool,
        reflection_type: ReflectionType,
        analysis_hash: str
    ):
        self.critique_level = critique_level
        self.issues_found = issues_found
        self.suggestions = suggestions
        self.confidence_score = confidence_score
        self.should_regenerate = should_regenerate
        self.reflection_type = reflection_type
        self.analysis_hash = analysis_hash
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Converter para dicionário"""
        return {
            'critique_level': self.critique_level.value,
            'issues_found': self.issues_found,
            'suggestions': self.suggestions,
            'confidence_score': self.confidence_score,
            'should_regenerate': self.should_regenerate,
            'reflection_type': self.reflection_type.value,
            'analysis_hash': self.analysis_hash,
            'timestamp': self.timestamp.isoformat()
        }


class ReflectionAgent:
    """
    Agente de Reflexão para auto-crítica e refinamento iterativo

    PADRÃO: Reflection (Self-Critique) - Capítulo 4

    Este agente implementa o loop de reflexão:
    1. Recebe análise de outro agente (ex: ClinicalAgent)
    2. Realiza crítica estruturada em múltiplas dimensões
    3. Detecta erros, inconsistências, gaps de informação
    4. Gera feedback acionável
    5. Decide se regeneração é necessária
    6. Suporta múltiplos ciclos iterativos

    SKILLS APLICADAS:
    - code-review-excellence: Padrões de crítica e revisão
    - debugging-strategies: Detecção sistemática de problemas
    - python-performance-optimization: Cache de reflexões
    """

    def __init__(self):
        """Inicializar ReflectionAgent"""
        self.ollama_url = f"{settings.ollama_host}/api/generate"
        self.model = settings.ollama_llm

        # Cache de reflexões (evitar reprocessamento)
        # SKILL: python-performance-optimization
        self._reflection_cache: Dict[str, ReflectionResult] = {}

        # Limites de iteração (evitar loops infinitos)
        self.max_reflection_cycles = 3
        self.min_confidence_threshold = 0.7

        # Critérios de crítica estruturados
        # SKILL: code-review-excellence
        self.critique_dimensions = [
            "consistency",  # Análise é internamente consistente?
            "evidence",  # Evidências suportam conclusões?
            "completeness",  # Todas informações necessárias presentes?
            "logic",  # Raciocínio é logicamente coerente?
            "safety",  # Considerações de segurança adequadas?
            "clarity"  # Comunicação clara e não ambígua?
        ]

        logger.info("🔍 ReflectionAgent inicializado (Capítulo 4 - Self-Critique)")

    @lru_cache(maxsize=500)
    def _compute_analysis_hash(self, analysis_str: str) -> str:
        """
        Computar hash da análise para caching

        SKILL: python-performance-optimization
        Evita reprocessamento de análises idênticas
        """
        return hashlib.sha256(analysis_str.encode()).hexdigest()

    async def reflect_on_analysis(
        self,
        analysis: Dict[str, Any],
        triage_data: Dict[str, Any],
        reflection_type: ReflectionType = ReflectionType.CONSISTENCY_CHECK,
        use_cache: bool = True
    ) -> ReflectionResult:
        """
        Realizar reflexão sobre uma análise clínica

        PADRÃO: Reflection Pattern - Passo CRITIQUE

        Args:
            analysis: Análise clínica a ser revisada
            triage_data: Dados originais do paciente
            reflection_type: Tipo de reflexão a realizar
            use_cache: Se deve usar cache de reflexões

        Returns:
            ReflectionResult com crítica estruturada
        """
        logger.info(f"🔍 Iniciando reflexão tipo: {reflection_type.value}")

        # Verificar cache
        # SKILL: python-performance-optimization
        if use_cache:
            analysis_str = str(sorted(analysis.items()))
            analysis_hash = self._compute_analysis_hash(analysis_str)

            cache_key = f"{analysis_hash}:{reflection_type.value}"
            if cache_key in self._reflection_cache:
                logger.info("✅ Reflexão recuperada do cache")
                return self._reflection_cache[cache_key]

        # Executar reflexão via LLM
        reflection_result = await self._execute_reflection_llm(
            analysis, triage_data, reflection_type
        )

        # Cachear resultado
        if use_cache:
            self._reflection_cache[cache_key] = reflection_result

        logger.info(
            f"✅ Reflexão concluída: {reflection_result.critique_level.value}"
        )

        return reflection_result

    async def _execute_reflection_llm(
        self,
        analysis: Dict[str, Any],
        triage_data: Dict[str, Any],
        reflection_type: ReflectionType
    ) -> ReflectionResult:
        """
        Executar reflexão usando LLM

        SKILL: code-review-excellence
        Implementa crítica estruturada e sistemática
        """
        # Construir prompt de reflexão específico
        prompt = self._build_reflection_prompt(
            analysis, triage_data, reflection_type
        )

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.2,  # Baixa temp para crítica objetiva
                            "top_p": 0.9
                        }
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Erro ao chamar LLM para reflexão: {response.status_code}")
                    return self._generate_fallback_reflection(analysis)

                result = response.json()
                llm_response = result.get("response", "")

                # Parse resposta do LLM
                reflection_result = self._parse_llm_reflection(
                    llm_response, analysis, reflection_type
                )

                return reflection_result

        except Exception as e:
            logger.error(f"❌ Erro na reflexão LLM: {e}")
            return self._generate_fallback_reflection(analysis)

    def _build_reflection_prompt(
        self,
        analysis: Dict[str, Any],
        triage_data: Dict[str, Any],
        reflection_type: ReflectionType
    ) -> str:
        """
        Construir prompt estruturado para reflexão

        SKILL: code-review-excellence
        Prompts claros e específicos para cada tipo de crítica
        """
        base_prompt = f"""Você é um especialista médico realizando revisão crítica de uma análise clínica.

DADOS DO PACIENTE:
{self._format_triage_data(triage_data)}

ANÁLISE A SER REVISADA:
{self._format_analysis(analysis)}

TIPO DE REFLEXÃO: {reflection_type.value}
"""

        # Adicionar instruções específicas por tipo
        if reflection_type == ReflectionType.CONSISTENCY_CHECK:
            base_prompt += """
TAREFA: Verificar consistência interna da análise

Analise se:
1. O nível de risco é consistente com as contraindicações encontradas
2. As interações identificadas justificam as recomendações
3. Não há contradições entre diferentes partes da análise
4. A confiança expressa condiz com a quantidade/qualidade de evidências

Liste TODAS as inconsistências encontradas.
"""

        elif reflection_type == ReflectionType.EVIDENCE_VALIDATION:
            base_prompt += """
TAREFA: Validar se evidências suportam conclusões

Analise se:
1. Cada afirmação tem evidência correspondente
2. Evidências citadas são relevantes para as conclusões
3. Não há saltos lógicos sem suporte
4. Fontes de evidência são confiáveis (ex: bulas ANVISA)

Liste TODOS os problemas de evidência encontrados.
"""

        elif reflection_type == ReflectionType.COMPLETENESS_CHECK:
            base_prompt += """
TAREFA: Verificar completude da análise

Analise se:
1. Todas as contraindicações relevantes foram consideradas
2. Todas as interações medicamentosas foram verificadas
3. Populações vulneráveis (idosos, crianças, gestantes) foram consideradas
4. Dosagens e vias de administração foram mencionadas quando relevante

Liste TUDO que está faltando.
"""

        elif reflection_type == ReflectionType.RISK_ASSESSMENT_REVIEW:
            base_prompt += """
TAREFA: Revisar avaliação de risco

Analise se:
1. Classificação de risco (low/medium/high/critical) é apropriada
2. Riscos mais graves foram priorizados adequadamente
3. Precauções necessárias foram mencionadas
4. Situações que exigem atenção médica imediata foram identificadas

Liste TODOS os problemas na avaliação de risco.
"""

        elif reflection_type == ReflectionType.LOGICAL_COHERENCE:
            base_prompt += """
TAREFA: Verificar coerência lógica

Analise se:
1. Argumentação segue lógica clara
2. Não há falácias ou raciocínio circular
3. Causa e efeito são corretamente relacionados
4. Generalizações são justificadas

Liste TODOS os problemas lógicos encontrados.
"""

        base_prompt += """

FORMATO DA RESPOSTA (JSON):
{
  "critique_level": "pass" | "minor_issues" | "major_issues" | "critical_flaws",
  "issues_found": [
    {
      "severity": "low" | "medium" | "high" | "critical",
      "category": "consistency" | "evidence" | "completeness" | "logic" | "safety" | "clarity",
      "description": "Descrição detalhada do problema",
      "location": "Onde na análise o problema ocorre"
    }
  ],
  "suggestions": [
    "Sugestão específica e acionável para melhoria"
  ],
  "confidence_score": 0.0-1.0,
  "should_regenerate": true/false
}

Seja rigoroso e objetivo. Crítica construtiva salva vidas.
"""

        return base_prompt

    def _format_triage_data(self, triage_data: Dict[str, Any]) -> str:
        """Formatar dados de triagem para o prompt"""
        lines = []
        if 'age' in triage_data:
            lines.append(f"- Idade: {triage_data['age']} anos")
        if 'pregnant' in triage_data:
            lines.append(f"- Gestante: {'Sim' if triage_data['pregnant'] else 'Não'}")
        if 'meds_in_use' in triage_data:
            meds = ", ".join(triage_data['meds_in_use'])
            lines.append(f"- Medicamentos em uso: {meds}")
        if 'cid_codes' in triage_data:
            cids = ", ".join(triage_data['cid_codes'])
            lines.append(f"- Códigos CID: {cids}")
        return "\n".join(lines)

    def _format_analysis(self, analysis: Dict[str, Any]) -> str:
        """Formatar análise para o prompt"""
        import json
        return json.dumps(analysis, indent=2, ensure_ascii=False)

    def _parse_llm_reflection(
        self,
        llm_response: str,
        original_analysis: Dict[str, Any],
        reflection_type: ReflectionType
    ) -> ReflectionResult:
        """
        Parse resposta do LLM em ReflectionResult estruturado

        SKILL: debugging-strategies
        Parse robusto com fallbacks
        """
        import json
        import re

        try:
            # Tentar extrair JSON da resposta
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))

                # Validar campos obrigatórios
                critique_level_str = parsed.get('critique_level', 'minor_issues')
                critique_level = CritiqueLevel(critique_level_str)

                issues_found = parsed.get('issues_found', [])
                suggestions = parsed.get('suggestions', [])
                confidence_score = float(parsed.get('confidence_score', 0.5))
                should_regenerate = parsed.get('should_regenerate', False)

                # Computar hash da análise
                analysis_str = str(sorted(original_analysis.items()))
                analysis_hash = self._compute_analysis_hash(analysis_str)

                return ReflectionResult(
                    critique_level=critique_level,
                    issues_found=issues_found,
                    suggestions=suggestions,
                    confidence_score=confidence_score,
                    should_regenerate=should_regenerate,
                    reflection_type=reflection_type,
                    analysis_hash=analysis_hash
                )

        except Exception as e:
            logger.warning(f"⚠️ Erro ao parse reflexão LLM: {e}")

        # Fallback: análise heurística
        return self._generate_fallback_reflection(original_analysis)

    def _generate_fallback_reflection(
        self,
        analysis: Dict[str, Any]
    ) -> ReflectionResult:
        """
        Gerar reflexão fallback baseada em regras heurísticas

        SKILL: debugging-strategies
        Fallback robusto quando LLM falha
        """
        issues = []
        suggestions = []

        # Checar consistência básica
        risk_level = analysis.get('risk_level', 'unknown')
        contraindications = analysis.get('contraindications', [])
        interactions = analysis.get('interactions', [])

        # Heurística 1: Risco alto mas sem contraindicações?
        if risk_level in ['high', 'critical'] and len(contraindications) == 0:
            issues.append({
                'severity': 'high',
                'category': 'consistency',
                'description': 'Risco classificado como alto/crítico mas sem contraindicações listadas',
                'location': 'risk_level vs contraindications'
            })
            suggestions.append('Verificar se há contraindicações não detectadas')

        # Heurística 2: Muitas interações mas risco baixo?
        if len(interactions) > 3 and risk_level == 'low':
            issues.append({
                'severity': 'medium',
                'category': 'consistency',
                'description': 'Múltiplas interações detectadas mas risco classificado como baixo',
                'location': 'interactions vs risk_level'
            })
            suggestions.append('Reavaliar classificação de risco')

        # Heurística 3: Confiança muito baixa?
        confidence = analysis.get('confidence_score', 1.0)
        if confidence < 0.5:
            issues.append({
                'severity': 'medium',
                'category': 'evidence',
                'description': f'Confiança muito baixa ({confidence:.2f})',
                'location': 'confidence_score'
            })
            suggestions.append('Buscar evidências adicionais ou escalar para revisão humana')

        # Determinar critique level
        if len(issues) == 0:
            critique_level = CritiqueLevel.PASS
        elif any(i['severity'] == 'critical' for i in issues):
            critique_level = CritiqueLevel.CRITICAL_FLAWS
        elif any(i['severity'] == 'high' for i in issues):
            critique_level = CritiqueLevel.MAJOR_ISSUES
        else:
            critique_level = CritiqueLevel.MINOR_ISSUES

        should_regenerate = critique_level in [
            CritiqueLevel.MAJOR_ISSUES,
            CritiqueLevel.CRITICAL_FLAWS
        ]

        analysis_str = str(sorted(analysis.items()))
        analysis_hash = self._compute_analysis_hash(analysis_str)

        return ReflectionResult(
            critique_level=critique_level,
            issues_found=issues,
            suggestions=suggestions,
            confidence_score=0.6,  # Fallback tem confiança moderada
            should_regenerate=should_regenerate,
            reflection_type=ReflectionType.CONSISTENCY_CHECK,
            analysis_hash=analysis_hash
        )

    async def iterative_refinement(
        self,
        initial_analysis: Dict[str, Any],
        triage_data: Dict[str, Any],
        regeneration_callback: Optional[callable] = None,
        max_cycles: Optional[int] = None
    ) -> Tuple[Dict[str, Any], List[ReflectionResult]]:
        """
        Refinamento iterativo com múltiplos ciclos de reflexão

        PADRÃO: Reflection Pattern - Loop completo CRITIQUE → REGENERATE → CRITIQUE

        Args:
            initial_analysis: Análise inicial a ser refinada
            triage_data: Dados do paciente
            regeneration_callback: Função async para regenerar análise
                                   Assinatura: async (analysis, feedback) -> new_analysis
            max_cycles: Número máximo de ciclos (default: self.max_reflection_cycles)

        Returns:
            Tupla (análise_final, lista_de_reflexões)
        """
        logger.info("🔄 Iniciando refinamento iterativo")

        max_cycles = max_cycles or self.max_reflection_cycles
        current_analysis = initial_analysis
        reflection_history = []

        for cycle in range(max_cycles):
            logger.info(f"🔄 Ciclo de reflexão {cycle + 1}/{max_cycles}")

            # Executar múltiplos tipos de reflexão
            reflections = await self._run_multi_dimensional_critique(
                current_analysis, triage_data
            )

            reflection_history.extend(reflections)

            # Verificar se refinamento é necessário
            needs_regeneration = any(r.should_regenerate for r in reflections)
            critical_issues = any(
                r.critique_level == CritiqueLevel.CRITICAL_FLAWS
                for r in reflections
            )

            if not needs_regeneration and not critical_issues:
                logger.info("✅ Análise aprovada pela reflexão, sem necessidade de refinamento")
                break

            # Regenerar se callback fornecido
            if regeneration_callback:
                logger.info("🔄 Regenerando análise com feedback...")

                # Compilar feedback de todas as reflexões
                feedback = self._compile_feedback(reflections)

                try:
                    current_analysis = await regeneration_callback(
                        current_analysis, feedback
                    )
                    logger.info("✅ Análise regenerada")
                except Exception as e:
                    logger.error(f"❌ Erro ao regenerar análise: {e}")
                    break
            else:
                logger.warning("⚠️ Regeneração necessária mas sem callback fornecido")
                break

        logger.info(f"✅ Refinamento iterativo concluído após {len(reflection_history)} reflexões")

        return current_analysis, reflection_history

    async def _run_multi_dimensional_critique(
        self,
        analysis: Dict[str, Any],
        triage_data: Dict[str, Any]
    ) -> List[ReflectionResult]:
        """
        Executar crítica em múltiplas dimensões em paralelo

        SKILL: python-performance-optimization
        Execução paralela de múltiplas reflexões
        """
        reflection_tasks = [
            self.reflect_on_analysis(
                analysis, triage_data, reflection_type, use_cache=True
            )
            for reflection_type in [
                ReflectionType.CONSISTENCY_CHECK,
                ReflectionType.EVIDENCE_VALIDATION,
                ReflectionType.COMPLETENESS_CHECK,
                ReflectionType.RISK_ASSESSMENT_REVIEW,
                ReflectionType.LOGICAL_COHERENCE
            ]
        ]

        reflections = await asyncio.gather(*reflection_tasks)
        return list(reflections)

    def _compile_feedback(
        self,
        reflections: List[ReflectionResult]
    ) -> Dict[str, Any]:
        """
        Compilar feedback de múltiplas reflexões em estrutura unificada

        SKILL: api-design-principles
        Feedback estruturado e acionável
        """
        all_issues = []
        all_suggestions = []

        for reflection in reflections:
            all_issues.extend(reflection.issues_found)
            all_suggestions.extend(reflection.suggestions)

        # Priorizar por severidade
        all_issues.sort(
            key=lambda x: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(
                x.get('severity', 'low'), 3
            )
        )

        return {
            'issues': all_issues,
            'suggestions': all_suggestions,
            'critical_count': len([i for i in all_issues if i.get('severity') == 'critical']),
            'high_count': len([i for i in all_issues if i.get('severity') == 'high']),
            'reflection_types': [r.reflection_type.value for r in reflections]
        }

    def get_reflection_summary(
        self,
        reflections: List[ReflectionResult]
    ) -> Dict[str, Any]:
        """
        Gerar resumo de múltiplas reflexões

        SKILL: api-design-principles
        Agregação útil de métricas de reflexão
        """
        total_issues = sum(len(r.issues_found) for r in reflections)
        critical_issues = sum(
            1 for r in reflections
            if r.critique_level == CritiqueLevel.CRITICAL_FLAWS
        )
        major_issues = sum(
            1 for r in reflections
            if r.critique_level == CritiqueLevel.MAJOR_ISSUES
        )

        avg_confidence = sum(r.confidence_score for r in reflections) / len(reflections) if reflections else 0.0

        return {
            'total_reflections': len(reflections),
            'total_issues_found': total_issues,
            'critical_flaws_count': critical_issues,
            'major_issues_count': major_issues,
            'average_confidence': avg_confidence,
            'needs_regeneration': any(r.should_regenerate for r in reflections),
            'reflection_types': list(set(r.reflection_type.value for r in reflections))
        }


# Instância singleton
_reflection_agent = None


def get_reflection_agent() -> ReflectionAgent:
    """Obter instância singleton do ReflectionAgent"""
    global _reflection_agent
    if _reflection_agent is None:
        _reflection_agent = ReflectionAgent()
    return _reflection_agent
