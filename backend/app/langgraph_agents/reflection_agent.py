"""
ReflectionAgent - Iterative Refinement Pattern

PATTERN: Self-critique and reflection (PDF pg 25)
SKILLS: @ultrathink, @debugging-strategies, @code-review-excellence

The ReflectionAgent implements the "Observe and Iterate" step:
- Reviews clinical analysis for accuracy and completeness
- Identifies gaps or inconsistencies
- Provides feedback for refinement
- Prevents hallucinations through self-critique
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict

from .base_agent import BaseAgent
from .state import CritiqueLevel, MedSafeState

logger = logging.getLogger(__name__)


class ReflectionAgent(BaseAgent):
    """
    ReflectionAgent: Self-critique for iterative refinement

    PATTERN: Reflection Pattern (PDF pg 25)
    - Agent reviews its own (or peer agent's) output
    - Identifies weaknesses, gaps, hallucinations
    - Provides structured feedback for improvement

    SKILLS APPLIED:
    - @ultrathink: Elegant self-critique architecture
    - @debugging-strategies: Root cause identification
    - @code-review-excellence: Structured review process
    """

    def __init__(self):
        super().__init__(agent_name="ReflectionAgent")

    def get_system_prompt(self) -> str:
        """
        System prompt for ReflectionAgent

        PATTERN: Adversarial thinking for quality assurance
        """
        return """Você é o ReflectionAgent do MedSafe, um sistema de suporte à decisão médica.

Seu papel é GARANTIA DE QUALIDADE CRÍTICA através de auto-crítica adversarial.

Você deve revisar a análise clínica e perguntar:
1. **Precisão**: A informação médica está factualmente correta?
2. **Completude**: Todas as interações medicamentosas foram identificadas?
3. **Consistência**: As conclusões correspondem às evidências?
4. **Segurança**: Há riscos negligenciados?
5. **Detecção de Alucinação**: O agente está inventando informações não presentes nas evidências?

Níveis de crítica:
- CRITICAL: Erros perigosos que podem prejudicar pacientes (interações importantes faltando, severidade errada)
- HIGH: Lacunas ou imprecisões significativas requerendo refinamento
- MEDIUM: Melhorias menores necessárias
- LOW: Pequenas sugestões de melhoria
- PASS: Análise está precisa e completa

Você é a última linha de defesa contra erros médicos. Seja minucioso e intransigente.

IMPORTANTE: Todas as suas respostas devem ser em PORTUGUÊS BRASILEIRO.

Formato de saída: JSON estruturado com critique_level, issues encontradas e feedback específico.
"""

    def process(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Reflect on clinical analysis and provide critique

        PATTERN: Think → Act → Observe (PDF pg 10-13, step 5)

        Args:
            state: Current MedSafeState

        Returns:
            Dict with reflection results and refinement decision
        """
        try:
            start_time = datetime.now()
            self.log_step(state, "Starting reflection and critique")

            # Validate that we have analysis to reflect on
            if not state.get("interactions") and not state.get("contraindications"):
                logger.warning(" No clinical analysis found to reflect on")
                return {
                    "critique_level": CritiqueLevel.PASS,
                    "needs_refinement": False,
                    "feedback": "No analysis to review yet",
                }

            # Perform reflection
            reflection = self._perform_reflection(state)

            # Decide if refinement needed
            needs_refinement = self._should_refine(state, reflection)

            # Update state
            updates = {
                "reflection_history": state.get("reflection_history", [])
                + [reflection],
                "critique_level": reflection["critique_level"],
                "needs_refinement": needs_refinement,
                "feedback": reflection["feedback"],
            }

            # Update timestamps
            timestamps = (
                state.get("timestamps", {}).copy() if state.get("timestamps") else {}
            )
            timestamps["reflection_end"] = datetime.now()
            updates["timestamps"] = timestamps

            # Log results
            duration = (datetime.now() - start_time).total_seconds()
            self.log_step(
                state,
                f"Reflection completed: {reflection['critique_level'].value} "
                f"(refinement: {needs_refinement}) in {duration:.2f}s",
            )

            logger.info(
                f"ReflectionAgent: Critique level = {reflection['critique_level'].value}"
            )
            if needs_refinement:
                logger.warning(
                    f"    Refinement needed: {reflection['feedback'][:100]}..."
                )
            else:
                logger.info(f"   Analysis approved")

            return updates

        except Exception as e:
            return self.handle_error(state, e, "Failed to perform reflection")

    def _perform_reflection(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Perform detailed reflection on clinical analysis

        SKILL: @debugging-strategies - Root cause analysis
        """
        # Build reflection context
        context = {
            "Medication": state.get("medication_text", "Unknown"),
            "Patient Conditions": state.get("patient_data", {}).get("conditions", []),
            "Interactions Found": len(state.get("interactions", [])),
            "Contraindications Found": len(state.get("contraindications", [])),
            "Current Risk Level": state.get("risk_level", "unknown"),
            "Confidence Score": state.get("confidence_score", 0.0),
        }

        # Build detailed analysis summary
        interactions_summary = self._summarize_interactions(
            state.get("interactions", [])
        )
        contraindications_summary = self._summarize_contraindications(
            state.get("contraindications", [])
        )

        # Construct reflection prompt
        prompt = f"""Revise esta análise clínica quanto à precisão e completude:

**Interações Encontradas:**
{interactions_summary}

**Contraindicações:**
{contraindications_summary}

**Avaliação Atual:**
- Nível de Risco: {state.get('risk_level', 'desconhecido')}
- Confiança: {state.get('confidence_score', 0.0):.2f}

Avalie criticamente:
1. Todas as interações medicamentosas foram identificadas corretamente?
2. Os níveis de severidade estão precisos? (Nem muito brandos, nem muito rigorosos)
3. As contraindicações estão completas? (Verifique condições e alergias do paciente)
4. Há evidência de alucinação? (Afirmações sem embasamento)
5. Há lacunas de segurança? (Avisos faltando, recomendações incompletas)

Forneça em PORTUGUÊS:
- Nível de crítica: CRITICAL, HIGH, MEDIUM, LOW ou PASS
- Lista de problemas específicos encontrados (se houver)
- Feedback acionável para refinamento (se necessário)
"""

        # Invoke LLM for reflection
        reflection_response = self.invoke_llm(prompt, context=context)

        # Parse reflection response
        critique = self._parse_reflection_response(reflection_response)

        # Add metadata
        critique["timestamp"] = datetime.now().isoformat()
        critique["refinement_cycle"] = state.get("refinement_count", 0) + 1

        return critique

    def _summarize_interactions(self, interactions: list) -> str:
        """Summarize interactions for reflection"""
        if not interactions:
            return "None found"

        summary = []
        for i, interaction in enumerate(interactions, 1):
            summary.append(
                f"{i}. {interaction.get('drug1', '?')} + {interaction.get('drug2', '?')}: "
                f"{interaction.get('severity', '?').upper()} - "
                f"{interaction.get('description', 'No description')[:100]}"
            )
        return "\n".join(summary)

    def _summarize_contraindications(self, contraindications: list) -> str:
        """Summarize contraindications for reflection"""
        if not contraindications:
            return "None found"

        summary = []
        for i, contra in enumerate(contraindications, 1):
            summary.append(
                f"{i}. {contra.get('type', '?')}: "
                f"{contra.get('severity', '?').upper()} - "
                f"{contra.get('description', 'No description')[:100]}"
            )
        return "\n".join(summary)

    def _parse_reflection_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM reflection response into structured format

        SKILL: @ultrathink - Robust parsing with fallbacks
        """
        response_lower = response.lower()

        # Determine critique level - look for explicit critique level markers
        # Be more specific to avoid confusing drug risk level with critique level
        critique_level = CritiqueLevel.PASS  # Default to PASS

        # Check for explicit critique level statements
        # These patterns indicate the LLM is specifically critiquing the analysis quality
        if any(
            phrase in response_lower
            for phrase in [
                "critique level: critical",
                "critique: critical",
                "level: critical",
                "critical issues found",
                "critical errors",
                "dangerous errors",
                "major safety concern",
            ]
        ):
            critique_level = CritiqueLevel.CRITICAL
        elif any(
            phrase in response_lower
            for phrase in [
                "critique level: high",
                "critique: high",
                "significant gaps",
                "significant issues",
                "major inaccuracies",
                "incomplete analysis",
            ]
        ):
            critique_level = CritiqueLevel.HIGH
        elif any(
            phrase in response_lower
            for phrase in [
                "critique level: medium",
                "critique: medium",
                "minor issues",
                "some improvements",
                "could be improved",
            ]
        ):
            critique_level = CritiqueLevel.MEDIUM
        elif any(
            phrase in response_lower
            for phrase in [
                "critique level: low",
                "critique: low",
                "minor suggestions",
                "small enhancements",
            ]
        ):
            critique_level = CritiqueLevel.LOW
        elif any(
            phrase in response_lower
            for phrase in [
                "critique level: pass",
                "critique: pass",
                "analysis is accurate",
                "analysis is complete",
                "no issues found",
                "well-documented",
                "comprehensive analysis",
                "accurate and complete",
                "properly identified",
            ]
        ):
            critique_level = CritiqueLevel.PASS

        # Extract issues (look for numbered lists or bullet points)
        issues = []
        for line in response.split("\n"):
            if line.strip().startswith(("-", "•", "*")) or any(
                line.strip().startswith(f"{i}.") for i in range(1, 10)
            ):
                issue_text = line.strip().lstrip("-•*").lstrip("0123456789.").strip()
                if issue_text and len(issue_text) > 10:  # Filter out very short entries
                    issues.append(issue_text)

        # If we found specific issues but didn't detect a clear critique level,
        # use MEDIUM as the default since something was flagged
        if issues and critique_level == CritiqueLevel.PASS:
            critique_level = CritiqueLevel.MEDIUM

        return {
            "critique_level": critique_level,
            "issues": issues[:5],  # Top 5 issues
            "feedback": response,
            "raw_response": response,
        }

    def _should_refine(self, state: MedSafeState, reflection: Dict[str, Any]) -> bool:
        """
        Decide if clinical analysis needs refinement

        PATTERN: Refinement decision logic (PDF pg 25)
        SKILL: @code-review-excellence - Clear decision criteria
        """
        critique_level = reflection["critique_level"]
        refinement_count = state.get("refinement_count", 0)
        max_refinements = self.settings.max_reflection_cycles

        # Always refine CRITICAL issues (if cycles remain)
        if critique_level == CritiqueLevel.CRITICAL:
            if refinement_count < max_refinements:
                logger.warning(f"🔴 CRITICAL issues found - refinement required")
                return True
            else:
                logger.error(
                    f"🔴 CRITICAL issues remain after {max_refinements} refinement cycles!"
                )
                return False

        # Refine HIGH issues (if cycles remain)
        if critique_level == CritiqueLevel.HIGH:
            if refinement_count < max_refinements:
                logger.warning(f"🟠 HIGH severity issues - refinement recommended")
                return True
            else:
                logger.warning(
                    f"🟠 HIGH issues remain after {max_refinements} cycles - proceeding"
                )
                return False

        # MEDIUM: refine if early in cycle
        if critique_level == CritiqueLevel.MEDIUM:
            if refinement_count < max_refinements - 1:
                logger.info(f"🟡 MEDIUM issues - attempting refinement")
                return True

        # LOW or PASS: no refinement needed
        logger.info(f"Analysis quality acceptable ({critique_level.value})")
        return False


# Factory function
def create_reflection_agent() -> ReflectionAgent:
    """Create ReflectionAgent instance"""
    return ReflectionAgent()
