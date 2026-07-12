"""
SafetyAgent - Safety Guardrails Layer

PATTERN: Security and safety validation (PDF pg 34-38)
SKILLS: @ultrathink, @code-review-excellence, @debugging-strategies

RESPONSIBILITIES:
1. Validate outputs for medical safety
2. Detect hallucinations or incorrect information
3. Block dangerous recommendations
4. Escalate high-risk cases to HITL
5. Enforce safety policies and constraints
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from .base_agent import BaseAgent
from .state import MedSafeState, RiskLevel, SafetyClassification

logger = logging.getLogger(__name__)


class SafetyAgent(BaseAgent):
    """
    SafetyAgent: Final safety validation before output

    PATTERN: Safety Guardrails (PDF pg 34-38)
    - Input/output validation
    - Hallucination detection
    - Safety policy enforcement
    - HITL escalation decisions

    SKILLS APPLIED:
    - @ultrathink: Multi-layered safety validation
    - @code-review-excellence: Defensive safety checks
    - @debugging-strategies: Comprehensive safety logging
    """

    def __init__(self):
        super().__init__(agent_name="SafetyAgent")

    def get_system_prompt(self) -> str:
        """
        System prompt for SafetyAgent

        PATTERN: Adversarial safety review
        """
        return """Você é o SafetyAgent do MedSafe, o guardião final de segurança.

Sua missão é prevenir qualquer informação médica que possa prejudicar pacientes.

Você deve detectar e bloquear:
1. **Alucinações**: Afirmações sem suporte de evidências
2. **Contradições**: Informações inconsistentes
3. **Omissões Perigosas**: Avisos críticos faltando
4. **Confiança Inapropriada**: Superestimar certeza
5. **Violações de Políticas**: Quebrar diretrizes de segurança médica

Classificações de Segurança:
- SAFE: Saída atende todos os critérios de segurança
- NEEDS_REVIEW: Requer revisão de médico humano (HITL)
- BLOCKED: Saída perigosa que não deve ser mostrada

Gatilhos de escalação (requerem HITL):
- Níveis de risco CRÍTICO ou ALTO
- Confiança muito baixa (<0.5) com sinal clínico (achados ou risco >= médio)
- Combinações de medicamentos conhecidas como perigosas
- Contraindicações para populações vulneráveis (gestantes, crianças)
- Recomendações conflitantes

IMPORTANTE: Todas as suas respostas devem ser em PORTUGUÊS BRASILEIRO.

Você é a última linha de defesa. Seja conservador e cauteloso.
"""

    def process(self, state: MedSafeState) -> Dict[str, Any]:
        """
        Perform safety validation on clinical analysis

        PATTERN: Think → Act → Observe (PDF pg 10-13, step 4)

        Args:
            state: Current MedSafeState

        Returns:
            Dict with safety classification and escalation decisions
        """
        try:
            start_time = datetime.now()
            self.log_step(state, "Starting safety validation")

            # Run safety checks
            violations = self._run_safety_checks(state)

            # Determine safety classification
            classification = self._classify_safety(state, violations)

            # Decide if human review needed
            requires_hitl, escalation_reasons = self._evaluate_hitl_need(
                state, violations
            )

            # Prepare updates
            updates = {
                "safety_classification": classification,
                "safety_violations": violations,
                "requires_human_review": requires_hitl,
                "escalation_reasons": escalation_reasons,
                "status": (
                    "safety_validated"
                    if classification == SafetyClassification.SAFE
                    else "needs_review"
                ),
            }

            # Escalate uncertain LOW risk when findings exist.
            # Golden set gap (clopidogrel+omeprazol, eval 20260707T175212Z):
            # LOW_CONFIDENCE_SAFETY warned but the final report stayed "low".
            # Contract: LOW risk + confidence < 0.6 + interactions or
            # contraindications present → risk becomes MEDIUM. Without
            # findings (e.g. paracetamol negative control), stays LOW.
            has_findings = bool(
                state.get("interactions") or state.get("contraindications")
            )
            if has_findings and any(
                v["type"] == "LOW_CONFIDENCE_SAFETY" for v in violations
            ):
                updates["risk_level"] = RiskLevel.MEDIUM
                self.log_step(
                    state,
                    "Escalated risk_level LOW→MEDIUM: "
                    "low confidence with findings present",
                )

            # Update timestamps - ensure timestamps dict exists in updates
            if "timestamps" not in updates:
                updates["timestamps"] = state.get("timestamps", {}).copy()
            updates["timestamps"]["safety_validation_end"] = datetime.now()

            # Log results
            duration = (datetime.now() - start_time).total_seconds()
            self.log_step(
                state,
                f"Safety validation: {classification.value}, "
                f"{len(violations)} violations, HITL={requires_hitl} "
                f"in {duration:.2f}s",
            )

            logger.info(f"🛡️  SafetyAgent: Classification = {classification.value}")
            if violations:
                logger.warning(f"    {len(violations)} safety violations detected")
                for v in violations:
                    logger.warning(f"      - {v['type']}: {v['message'][:80]}")
            if requires_hitl:
                logger.warning(f"    HITL required: {', '.join(escalation_reasons)}")

            return updates

        except Exception as e:
            return self.handle_error(state, e, "Failed to perform safety validation")

    def _run_safety_checks(self, state: MedSafeState) -> List[Dict[str, str]]:
        """
        Run comprehensive safety checks

        SKILL: @code-review-excellence - Systematic safety validation
        """
        violations = []

        # Check 1: Validate risk assessment consistency
        violations.extend(self._check_risk_consistency(state))

        # Check 2: Detect missing critical warnings
        violations.extend(self._check_critical_warnings(state))

        # Check 3: Validate confidence vs. risk alignment
        violations.extend(self._check_confidence_alignment(state))

        # Check 4: Check for dangerous combinations
        violations.extend(self._check_dangerous_combinations(state))

        # Check 5: Validate completeness
        violations.extend(self._check_completeness(state))

        return violations

    def _check_risk_consistency(self, state: MedSafeState) -> List[Dict[str, str]]:
        """Check if risk level matches interactions/contraindications"""
        violations = []

        risk_level = state.get("risk_level")
        interactions = state.get("interactions", [])
        contraindications = state.get("contraindications", [])

        # Count critical/high severity issues
        critical_count = sum(
            1
            for i in interactions + contraindications
            if i.get("severity") == "critical"
        )
        high_count = sum(
            1 for i in interactions + contraindications if i.get("severity") == "high"
        )

        # Validation logic
        if critical_count > 0 and risk_level != RiskLevel.CRITICAL:
            violations.append(
                {
                    "type": "RISK_INCONSISTENCY",
                    "severity": "critical",
                    "message": f"Found {critical_count} critical issues but risk level is {risk_level.value}",
                }
            )

        if high_count > 0 and risk_level not in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            violations.append(
                {
                    "type": "RISK_INCONSISTENCY",
                    "severity": "high",
                    "message": f"Found {high_count} high-severity issues but risk level is {risk_level.value}",
                }
            )

        return violations

    def _check_critical_warnings(self, state: MedSafeState) -> List[Dict[str, str]]:
        """Check if critical interactions have proper warnings"""
        violations = []

        interactions = state.get("interactions", [])
        contraindications = state.get("contraindications", [])

        critical_issues = [
            i
            for i in interactions + contraindications
            if i.get("severity") == "critical"
        ]

        if critical_issues:
            # Ensure recommendations address critical issues
            recommendations_text = str(state.get("dosage_adjustments", [])) + str(
                state.get("adverse_reactions", [])
            )

            for issue in critical_issues:
                drug_mentioned = False
                if "drug1" in issue:
                    drug_mentioned = (
                        issue["drug1"].lower() in recommendations_text.lower()
                    )
                elif "drug2" in issue:
                    drug_mentioned = (
                        issue["drug2"].lower() in recommendations_text.lower()
                    )

                if not drug_mentioned:
                    violations.append(
                        {
                            "type": "MISSING_CRITICAL_WARNING",
                            "severity": "critical",
                            "message": (
                                "Critical issue not addressed in recommendations: "
                                f'{issue.get("description", "Unknown")[:100]}'
                            ),
                        }
                    )

        return violations

    def _check_confidence_alignment(self, state: MedSafeState) -> List[Dict[str, str]]:
        """Check if confidence score aligns with risk level"""
        violations = []

        confidence = state.get("confidence_score", 0.0)
        risk_level = state.get("risk_level")

        # High risk with high confidence is good
        # Low risk with low confidence is concerning (uncertain about safety)
        if risk_level == RiskLevel.LOW and confidence < 0.6:
            violations.append(
                {
                    "type": "LOW_CONFIDENCE_SAFETY",
                    "severity": "medium",
                    "message": f"Low confidence ({confidence:.2f}) for LOW risk assessment - uncertain about safety",
                }
            )

        # Very low confidence overall
        if confidence < 0.5:
            violations.append(
                {
                    "type": "VERY_LOW_CONFIDENCE",
                    "severity": "high",
                    "message": f"Very low confidence ({confidence:.2f}) - analysis unreliable",
                }
            )

        return violations

    def _check_dangerous_combinations(
        self, state: MedSafeState
    ) -> List[Dict[str, str]]:
        """Check for known dangerous drug combinations"""
        violations = []

        interactions = state.get("interactions", [])

        # Known dangerous patterns (examples)
        dangerous_patterns = [
            {"pattern": ["warfarin", "aspirin"], "reason": "Severe bleeding risk"},
            {"pattern": ["lithium", "nsaid"], "reason": "Lithium toxicity"},
            {"pattern": ["mao inhibitor", "ssri"], "reason": "Serotonin syndrome"},
        ]

        for interaction in interactions:
            drug1 = interaction.get("drug1", "").lower()
            drug2 = interaction.get("drug2", "").lower()

            for dangerous in dangerous_patterns:
                pattern = dangerous["pattern"]
                if any(p in drug1 for p in pattern) and any(
                    p in drug2 for p in pattern
                ):
                    violations.append(
                        {
                            "type": "KNOWN_DANGEROUS_COMBINATION",
                            "severity": "critical",
                            "message": f'Dangerous combination detected: {dangerous["reason"]}',
                        }
                    )

        return violations

    def _check_completeness(self, state: MedSafeState) -> List[Dict[str, str]]:
        """Check if analysis is complete"""
        violations = []

        # Check if clinical analysis was performed
        if not state.get("interactions") and not state.get("contraindications"):
            if state.get("patient_data", {}).get("current_medications"):
                violations.append(
                    {
                        "type": "INCOMPLETE_ANALYSIS",
                        "severity": "high",
                        "message": "No interactions analyzed despite patient having current medications",
                    }
                )

        return violations

    def _classify_safety(
        self, state: MedSafeState, violations: List[Dict[str, str]]
    ) -> SafetyClassification:
        """
        Classify overall safety level

        SKILL: @ultrathink - Clear classification logic
        """
        # If any critical violations → BLOCKED
        critical_violations = [v for v in violations if v.get("severity") == "critical"]
        if critical_violations:
            if self.settings.block_on_critical_violations:
                logger.error(
                    f"🚫 BLOCKED: {len(critical_violations)} critical violations"
                )
                return SafetyClassification.BLOCKED

        # If high violations or high risk → NEEDS_REVIEW
        high_violations = [v for v in violations if v.get("severity") == "high"]
        if high_violations or state.get("risk_level") in [
            RiskLevel.CRITICAL,
            RiskLevel.HIGH,
        ]:
            return SafetyClassification.NEEDS_REVIEW

        # If medium violations → NEEDS_REVIEW (cautious)
        medium_violations = [v for v in violations if v.get("severity") == "medium"]
        if medium_violations:
            return SafetyClassification.NEEDS_REVIEW

        # Otherwise → SAFE
        return SafetyClassification.SAFE

    def _evaluate_hitl_need(
        self, state: MedSafeState, violations: List[Dict[str, str]]
    ) -> tuple[bool, List[str]]:
        """
        Decide if human-in-the-loop review is needed

        PATTERN: HITL escalation logic (PDF pg 22, 32)
        SKILL: @debugging-strategies - Clear escalation criteria
        """
        escalation_reasons = []

        # Rule 1: Always escalate CRITICAL risk
        if state.get("risk_level") == RiskLevel.CRITICAL:
            if self.settings.auto_escalate_critical:
                escalation_reasons.append("CRITICAL risk level")

        # Rule 2: Escalate HIGH risk
        if state.get("risk_level") == RiskLevel.HIGH:
            escalation_reasons.append("HIGH risk level")

        # Rule 3: Escalate critical violations
        critical_violations = [v for v in violations if v.get("severity") == "critical"]
        if critical_violations:
            escalation_reasons.append(
                f"{len(critical_violations)} critical safety violations"
            )

        # Rule 4: Escalate very low confidence ONLY with clinical signal.
        # Confiança < 0.5 (alinha com VERY_LOW_CONFIDENCE em
        # _check_confidence_alignment) num contexto com achados
        # (interações/contraindicações) ou risco >= MEDIUM → humano revisa.
        # Análise vazia e benigna com confiança estruturalmente baixa NÃO
        # deve pagear humano (evita alert fatigue nos controles negativos).
        confidence = state.get("confidence_score", 0.0)
        has_clinical_signal = (
            bool(state.get("interactions"))
            or bool(state.get("contraindications"))
            or state.get("risk_level")
            in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
        )
        if confidence < 0.5 and has_clinical_signal:
            escalation_reasons.append(f"Low confidence ({confidence:.2%})")

        # Rule 5: Escalate vulnerable populations
        patient_data = state.get("patient_data", {})
        conditions = [c.lower() for c in patient_data.get("conditions", [])]
        is_pregnant_condition = any(
            keyword in " ".join(conditions)
            for keyword in ["pregnancy", "pregnant", "gestação"]
        )
        # Gravidez é um CAMPO booleano no MedSafe (não uma condition string)
        if patient_data.get("pregnant") or is_pregnant_condition:
            escalation_reasons.append("Vulnerable population (pregnancy)")

        age = patient_data.get("age")
        if age and (age < 18 or age > 75):
            escalation_reasons.append(f"Vulnerable population (age {age})")

        # Return decision.
        # requires_human_review é informação CLÍNICA e independe do toggle
        # enable_hitl (workflow): o gate de workflow é aplicado no worker
        # (analysis_worker) e no grafo (should_escalate_to_hitl).
        requires_hitl = len(escalation_reasons) > 0

        return requires_hitl, escalation_reasons


# Factory function
def create_safety_agent() -> SafetyAgent:
    """Create SafetyAgent instance"""
    return SafetyAgent()
