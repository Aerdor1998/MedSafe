"""
Testes para InteractionClassifierAgent

SKILLS APLICADAS:
- CODE-REVIEW-EXCELLENCE: Testes abrangentes para garantir qualidade
- DEBUGGING-STRATEGIES: Casos de teste baseados em problemas reais identificados
- ULTRATHINK: Cobertura de edge cases e validação de lógica clínica
"""

import pytest

from backend.app.services.interaction_classifier import (
    InteractionClassifierAgent,
    SeverityLevel,
    get_classifier_agent,
)


class TestInteractionClassifierAgent:
    """
    Testes para o agente de classificação de interações
    """

    @pytest.fixture
    def classifier(self):
        """Fixture do classifier agent"""
        return get_classifier_agent()

    # === TESTES DE INTERAÇÕES CRÍTICAS ===

    def test_classify_anticoagulant_interaction_as_critical(self, classifier):
        """
        Testar classificação de interação anticoagulante como CRÍTICA

        Caso real do CSV: Warfarin + Gatifloxacin
        """
        description = (
            "Warfarin may increase the anticoagulant activities of Gatifloxacin."
        )
        result = classifier.classify_interaction(
            description, "Warfarin", "Gatifloxacin"
        )

        assert result.severity == SeverityLevel.CRITICAL
        assert result.confidence >= 0.90
        assert "anticoagulant" in result.reasoning.lower()
        assert "anticoagulant_interaction" in result.matched_patterns

    def test_classify_qt_prolongation_as_critical(self, classifier):
        """
        Testar classificação de prolongamento QT como CRÍTICO
        """
        description = "The risk of QT prolongation may be increased when combined."
        result = classifier.classify_interaction(description, "Drug1", "Drug2")

        assert result.severity == SeverityLevel.CRITICAL
        assert "qt_prolongation" in result.matched_patterns

    def test_classify_qtc_prolonging_as_critical(self, classifier):
        """
        Fraseado dominante no CSV DrugBank: "QTc-prolonging activities".
        Regressão: antes do fix, classificava LOW (regex exigia
        "prolongation" literal).

        Caso real do CSV: Haloperidol + Fluoxetine (risco de torsades)
        """
        description = (
            "Haloperidol may increase the QTc-prolonging activities of Fluoxetine."
        )
        result = classifier.classify_interaction(
            description, "Haloperidol", "Fluoxetine"
        )

        assert result.severity == SeverityLevel.CRITICAL
        assert "qt_prolongation" in result.matched_patterns

    def test_classify_av_block_as_critical(self, classifier):
        """
        Testar classificação de bloqueio AV como CRÍTICO

        Caso real: Clonidine + Digoxin
        """
        description = "Clonidine may increase the atrioventricular blocking (AV block) activities of Digoxin."
        result = classifier.classify_interaction(description, "Clonidine", "Digoxin")

        assert result.severity == SeverityLevel.CRITICAL
        assert "av_block" in result.matched_patterns

    def test_classify_serotonin_syndrome_as_critical(self, classifier):
        """
        Testar classificação de síndrome serotoninérgica como CRÍTICA
        """
        description = "May increase risk of serotonin syndrome when combined."
        result = classifier.classify_interaction(description, "SSRI1", "SSRI2")

        assert result.severity == SeverityLevel.CRITICAL
        assert "serotonin_syndrome" in result.matched_patterns

    # === TESTES DE INTERAÇÕES HIGH ===

    def test_classify_bradycardia_as_high(self, classifier):
        """
        Testar classificação de bradicardia como HIGH

        Caso real: Betaxolol + Digoxin
        """
        description = "Betaxolol may increase the bradycardic activities of Digoxin."
        result = classifier.classify_interaction(description, "Betaxolol", "Digoxin")

        assert result.severity == SeverityLevel.HIGH
        assert "bradycardia" in result.matched_patterns

    def test_classify_neuroexcitatory_as_high(self, classifier):
        """
        Testar classificação de atividade neuroexcitatória como HIGH

        Caso real: Ibuprofen + Quinolone
        """
        description = (
            "Ibuprofen may increase the neuroexcitatory activities of Gatifloxacin."
        )
        result = classifier.classify_interaction(
            description, "Ibuprofen", "Gatifloxacin"
        )

        assert result.severity == SeverityLevel.HIGH
        assert "neuroexcitatory" in result.matched_patterns

    def test_classify_serum_concentration_increase_as_high(self, classifier):
        """
        Testar aumento de concentração sérica como HIGH
        """
        description = "The serum concentration of Digoxin can be increased when combined with Pazopanib."
        result = classifier.classify_interaction(description, "Digoxin", "Pazopanib")

        assert result.severity == SeverityLevel.HIGH
        assert "serum_concentration_increase" in result.matched_patterns

    def test_classify_adverse_effects_increased_as_high(self, classifier):
        """
        Testar aumento de efeitos adversos como HIGH
        """
        description = (
            "The risk or severity of adverse effects can be increased when combined."
        )
        result = classifier.classify_interaction(description, "Drug1", "Drug2")

        assert result.severity == SeverityLevel.HIGH
        assert "adverse_effects_increased" in result.matched_patterns

    # === TESTES DE INTERAÇÕES MEDIUM ===

    def test_classify_metabolism_altered_as_medium(self, classifier):
        """
        Testar alteração de metabolismo como MEDIUM

        Caso real: Metabolism interactions
        """
        description = (
            "The metabolism of Digoxin can be increased when combined with Rifampicin."
        )
        result = classifier.classify_interaction(description, "Digoxin", "Rifampicin")

        assert result.severity == SeverityLevel.MEDIUM
        assert "metabolism_altered" in result.matched_patterns

    def test_classify_photosensitizing_as_medium(self, classifier):
        """
        Testar fotossensibilidade como MEDIUM
        """
        description = (
            "Trioxsalen may increase the photosensitizing activities of Verteporfin."
        )
        result = classifier.classify_interaction(
            description, "Trioxsalen", "Verteporfin"
        )

        assert result.severity == SeverityLevel.MEDIUM
        assert "photosensitizing" in result.matched_patterns

    def test_classify_therapeutic_efficacy_decreased_as_medium(self, classifier):
        """
        Testar que "therapeutic efficacy ... decreased" classifica como MEDIUM

        Caso golden real do DrugBank: Clopidogrel + Omeprazole
        Regressão: antes o padrão só casava "effect", não "efficacy" -> caía em LOW
        """
        description = (
            "The therapeutic efficacy of Clopidogrel can be decreased when used "
            "in combination with Omeprazole."
        )
        result = classifier.classify_interaction(
            description, "Clopidogrel", "Omeprazole"
        )

        assert result.severity == SeverityLevel.MEDIUM
        assert "therapeutic_effect" in result.matched_patterns

    def test_classify_therapeutic_effect_decreased_as_medium(self, classifier):
        """
        Testar que a frase antiga "therapeutic effect ... decreased" continua MEDIUM
        (sem regressão após expandir o regex para effect|efficacy)
        """
        description = (
            "The therapeutic effect of Drug1 can be decreased when combined with Drug2."
        )
        result = classifier.classify_interaction(description, "Drug1", "Drug2")

        assert result.severity == SeverityLevel.MEDIUM
        assert "therapeutic_effect" in result.matched_patterns

    def test_classify_serum_concentration_decrease_as_medium(self, classifier):
        """
        Testar diminuição de concentração sérica como MEDIUM
        """
        description = "The serum concentration of Digoxin can be decreased when combined with Bosentan."
        result = classifier.classify_interaction(description, "Digoxin", "Bosentan")

        assert result.severity == SeverityLevel.MEDIUM
        assert "serum_concentration_decrease" in result.matched_patterns

    # === TESTES DE INTERAÇÕES BENÉFICAS/LOW ===

    def test_classify_decrease_cardiotoxic_as_low(self, classifier):
        """
        Testar redução de cardiotoxicidade como LOW (benéfico)

        Caso real: Muitas interações que REDUZEM toxicidade
        """
        description = (
            "Aminolevulinic acid may decrease the cardiotoxic activities of Digoxin."
        )
        result = classifier.classify_interaction(
            description, "Aminolevulinic acid", "Digoxin"
        )

        assert result.severity == SeverityLevel.LOW
        assert "decrease_toxicity" in result.matched_patterns
        assert (
            "benéf" in result.reasoning.lower() or "reduz" in result.reasoning.lower()
        )

    def test_classify_unknown_interaction_as_low_with_low_confidence(self, classifier):
        """
        Testar interação desconhecida como LOW com baixa confiança
        """
        description = "Some generic interaction with no specific pattern."
        result = classifier.classify_interaction(description, "Drug1", "Drug2")

        assert result.severity == SeverityLevel.LOW
        assert result.confidence < 0.70  # Confiança baixa
        assert len(result.matched_patterns) == 0

    # === TESTES DE REFLECTION PATTERN ===

    def test_reflection_validates_critical_decisions(self, classifier):
        """
        Testar que decisões CRÍTICAS são validadas com Reflection Pattern
        """
        description = "Warfarin may increase the anticoagulant activities."
        result = classifier.classify_interaction(description, "Warfarin", "Drug2")

        # Deve ser critical
        assert result.severity == SeverityLevel.CRITICAL

        # Validar com reflection
        validated = classifier.validate_critical_decision(result, description)

        # Deve continuar critical (não tem fatores mitigantes)
        assert validated.severity == SeverityLevel.CRITICAL

    def test_reflection_downgrades_critical_with_mitigation(self, classifier):
        """
        Testar que decisões CRÍTICAS com fatores mitigantes são rebaixadas
        """
        # Criar resultado crítico artificial com apenas 1 padrão
        from backend.app.services.interaction_classifier import ClassificationResult

        result = ClassificationResult(
            severity=SeverityLevel.CRITICAL,
            confidence=0.95,
            reasoning="Critical pattern detected",
            matched_patterns=["cardiotoxic_increase"],
            clinical_category="Cardiovascular",
        )

        description = (
            "May increase cardiotoxic activities but monitor closely to manage risk."
        )
        validated = classifier.validate_critical_decision(result, description)

        # Deve ser rebaixado para HIGH devido a "monitor closely"
        assert validated.severity == SeverityLevel.HIGH
        assert (
            "rebaixado" in validated.reasoning.lower()
            or "mitiga" in validated.reasoning.lower()
        )

    # === TESTES DE CATEGORIZAÇÃO ===

    def test_categorize_cardiovascular_correctly(self, classifier):
        """
        Testar categorização cardiovascular
        """
        description = "May increase bradycardic activities."
        result = classifier.classify_interaction(description, "Drug1", "Drug2")

        assert result.clinical_category == "Cardiovascular"

    def test_categorize_hepatic_correctly(self, classifier):
        """
        Testar categorização hepática
        """
        description = "May increase hepatotoxic activities."
        result = classifier.classify_interaction(description, "Drug1", "Drug2")

        assert result.clinical_category == "Hepática"

    def test_categorize_renal_correctly(self, classifier):
        """
        Testar categorização renal
        """
        description = "May increase nephrotoxic activities."
        result = classifier.classify_interaction(description, "Drug1", "Drug2")

        assert result.clinical_category == "Renal"

    # === TESTES DE EDGE CASES ===

    def test_handle_empty_description(self, classifier):
        """
        Testar comportamento com descrição vazia
        """
        result = classifier.classify_interaction("", "Drug1", "Drug2")

        assert result.severity == SeverityLevel.LOW
        assert result.confidence < 0.70

    def test_handle_case_insensitivity(self, classifier):
        """
        Testar que classificação é case-insensitive
        """
        desc_lower = "warfarin may increase the anticoagulant activities."
        desc_upper = "WARFARIN MAY INCREASE THE ANTICOAGULANT ACTIVITIES."
        desc_mixed = "WaRfArIn MaY iNcReAsE tHe AnTiCoAgUlAnT aCtIvItIeS."

        result_lower = classifier.classify_interaction(desc_lower, "w", "d")
        result_upper = classifier.classify_interaction(desc_upper, "w", "d")
        result_mixed = classifier.classify_interaction(desc_mixed, "w", "d")

        assert result_lower.severity == result_upper.severity == result_mixed.severity
        assert result_lower.severity == SeverityLevel.CRITICAL

    def test_multiple_patterns_increase_confidence(self, classifier):
        """
        Testar que múltiplos padrões aumentam confiança
        """
        # Descrição com múltiplos padrões críticos
        description = "May increase anticoagulant activities and cause QT prolongation and bleeding."
        result = classifier.classify_interaction(description, "Drug1", "Drug2")

        assert result.severity == SeverityLevel.CRITICAL
        assert len(result.matched_patterns) >= 2
        assert result.confidence >= 0.95


class TestInteractionClassifierIntegration:
    """
    Testes de integração com casos reais do CSV
    """

    @pytest.fixture
    def classifier(self):
        return get_classifier_agent()

    def test_real_case_warfarin_aspirin(self, classifier):
        """
        Caso real: Warfarin + Aspirin (anticoagulante + anticoagulante)
        Esperado: CRITICAL
        """
        description = "Warfarin may increase the anticoagulant activities of Aspirin."
        result = classifier.classify_interaction(description, "Warfarin", "Aspirin")

        assert result.severity == SeverityLevel.CRITICAL
        assert result.clinical_category == "Coagulação"

    def test_real_case_ibuprofen_quinolone(self, classifier):
        """
        Caso real: Ibuprofen + Quinolone (neuroexcitatory)
        Esperado: HIGH
        """
        description = (
            "Ibuprofen may increase the neuroexcitatory activities of Levofloxacin."
        )
        result = classifier.classify_interaction(
            description, "Ibuprofen", "Levofloxacin"
        )

        assert result.severity == SeverityLevel.HIGH
        assert result.clinical_category == "Neurológica"

    def test_real_case_metabolism_interaction(self, classifier):
        """
        Caso real: Interação de metabolismo
        Esperado: MEDIUM
        """
        description = (
            "The metabolism of Digoxin can be increased when combined with Rifampicin."
        )
        result = classifier.classify_interaction(description, "Digoxin", "Rifampicin")

        assert result.severity == SeverityLevel.MEDIUM
        assert result.clinical_category == "Farmacocinética"

    def test_real_case_beneficial_interaction(self, classifier):
        """
        Caso real: Interação benéfica (reduz toxicidade)
        Esperado: LOW
        """
        description = "Prednisolone may decrease the cardiotoxic activities of Digoxin."
        result = classifier.classify_interaction(description, "Prednisolone", "Digoxin")

        assert result.severity == SeverityLevel.LOW
        assert (
            "benéf" in result.reasoning.lower() or "reduz" in result.reasoning.lower()
        )


# === TESTES DE PERFORMANCE ===


class TestClassifierPerformance:
    """
    Testes de performance e eficiência
    """

    @pytest.fixture
    def classifier(self):
        return get_classifier_agent()

    def test_classification_is_fast(self, classifier):
        """
        Testar que classificação é rápida (< 10ms por interação)
        """
        import time

        descriptions = [
            "Warfarin may increase the anticoagulant activities.",
            "May increase bradycardic activities.",
            "The metabolism can be increased when combined.",
            "May decrease the cardiotoxic activities.",
            "Some generic interaction.",
        ]

        start = time.time()
        for desc in descriptions:
            classifier.classify_interaction(desc, "Drug1", "Drug2")
        end = time.time()

        avg_time = (end - start) / len(descriptions)
        assert avg_time < 0.01  # < 10ms por classificação

    def test_singleton_pattern(self):
        """
        Testar que get_classifier_agent retorna sempre a mesma instância
        """
        agent1 = get_classifier_agent()
        agent2 = get_classifier_agent()

        assert agent1 is agent2  # Mesma instância


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
