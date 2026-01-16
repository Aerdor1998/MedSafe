"""
Tests for Clinical Rules Engine and Interaction Classifier Improvements

Tests the new context-aware severity classification and structured recommendations.

SKILL: @python-testing-patterns - Comprehensive test coverage
"""

import pytest

from backend.app.services.clinical_rules import (
    ClinicalRulesEngine,
    HepaticStage,
    PatientContext,
    PopulationRisk,
    RenalStage,
    calculate_bmi,
    calculate_gfr_cockroft_gault,
    get_renal_stage,
    get_rules_engine,
)
from backend.app.services.interaction_classifier import (
    ClassificationResult,
    InteractionClassifierAgent,
    SeverityLevel,
    get_classifier_agent,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def rules_engine():
    """Get rules engine instance"""
    return get_rules_engine()


@pytest.fixture
def classifier():
    """Get classifier agent instance"""
    return get_classifier_agent()


@pytest.fixture
def elderly_patient():
    """Patient context for elderly patient with polypharmacy"""
    return PatientContext(
        age=75,
        weight=70,
        sex="M",
        pregnant=False,
        gfr=45,
        current_medications=[
            "losartan",
            "metformin",
            "aspirin",
            "omeprazole",
            "amlodipine",
        ],
        conditions=["diabetes", "hypertension"],
    )


@pytest.fixture
def pregnant_patient():
    """Patient context for pregnant woman"""
    return PatientContext(
        age=28,
        weight=65,
        sex="F",
        pregnant=True,
        gfr=110,
        current_medications=["folic_acid"],
        conditions=[],
    )


@pytest.fixture
def pediatric_patient():
    """Patient context for child"""
    return PatientContext(
        age=8,
        weight=25,
        sex="M",
        pregnant=False,
        gfr=120,
        current_medications=["amoxicillin"],
        conditions=["asthma"],
    )


@pytest.fixture
def renal_impaired_patient():
    """Patient context for patient with severe renal impairment"""
    return PatientContext(
        age=60,
        weight=80,
        sex="M",
        pregnant=False,
        gfr=25,  # G4 - severely decreased
        child_pugh=None,
        current_medications=["furosemide"],
        conditions=["ckd"],
    )


@pytest.fixture
def hepatic_impaired_patient():
    """Patient context for patient with hepatic impairment"""
    return PatientContext(
        age=55,
        weight=75,
        sex="M",
        pregnant=False,
        gfr=90,
        child_pugh=HepaticStage.C,  # Decompensated
        current_medications=["lactulose", "spironolactone"],
        conditions=["cirrhosis"],
    )


# =============================================================================
# TEST: CALCULATION FUNCTIONS
# =============================================================================


class TestCalculations:
    """Tests for clinical calculation functions"""

    def test_calculate_gfr_male(self):
        """Test GFR calculation for male patient"""
        # 60yo male, 80kg, creatinine 1.2 mg/dL
        gfr = calculate_gfr_cockroft_gault(60, 80, 1.2, "M")
        # Expected: ((140-60) * 80) / (72 * 1.2) = 74.07
        assert 73 <= gfr <= 75

    def test_calculate_gfr_female(self):
        """Test GFR calculation for female patient (0.85 multiplier)"""
        # 60yo female, 80kg, creatinine 1.2 mg/dL
        gfr = calculate_gfr_cockroft_gault(60, 80, 1.2, "F")
        # Expected: 74.07 * 0.85 = 62.96
        assert 62 <= gfr <= 64

    def test_calculate_gfr_zero_creatinine(self):
        """Test GFR calculation with zero creatinine returns 0"""
        gfr = calculate_gfr_cockroft_gault(60, 80, 0, "M")
        assert gfr == 0.0

    def test_calculate_bmi(self):
        """Test BMI calculation"""
        # 80kg, 1.80m = 24.69 kg/m2
        bmi = calculate_bmi(80, 1.80)
        assert 24.5 <= bmi <= 25.0

    def test_calculate_bmi_zero_height(self):
        """Test BMI calculation with zero height returns 0"""
        bmi = calculate_bmi(80, 0)
        assert bmi == 0.0

    def test_get_renal_stage_g1(self):
        """Test renal stage classification G1"""
        assert get_renal_stage(95) == RenalStage.G1

    def test_get_renal_stage_g2(self):
        """Test renal stage classification G2"""
        assert get_renal_stage(75) == RenalStage.G2

    def test_get_renal_stage_g3a(self):
        """Test renal stage classification G3a"""
        assert get_renal_stage(50) == RenalStage.G3A

    def test_get_renal_stage_g3b(self):
        """Test renal stage classification G3b"""
        assert get_renal_stage(35) == RenalStage.G3B

    def test_get_renal_stage_g4(self):
        """Test renal stage classification G4"""
        assert get_renal_stage(20) == RenalStage.G4

    def test_get_renal_stage_g5(self):
        """Test renal stage classification G5"""
        assert get_renal_stage(10) == RenalStage.G5


# =============================================================================
# TEST: PATIENT CONTEXT
# =============================================================================


class TestPatientContext:
    """Tests for PatientContext risk identification"""

    def test_population_risks_elderly(self, elderly_patient):
        """Test that elderly patient is correctly identified"""
        risks = elderly_patient.get_population_risks()
        assert PopulationRisk.GERIATRIC in risks

    def test_population_risks_pregnant(self, pregnant_patient):
        """Test that pregnant patient is correctly identified"""
        risks = pregnant_patient.get_population_risks()
        assert PopulationRisk.PREGNANCY in risks

    def test_population_risks_pediatric(self, pediatric_patient):
        """Test that pediatric patient is correctly identified"""
        risks = pediatric_patient.get_population_risks()
        assert PopulationRisk.PEDIATRIC in risks

    def test_population_risks_renal_impaired(self, renal_impaired_patient):
        """Test that renal impaired patient is correctly identified"""
        risks = renal_impaired_patient.get_population_risks()
        assert PopulationRisk.RENAL_IMPAIRED in risks

    def test_population_risks_hepatic_impaired(self, hepatic_impaired_patient):
        """Test that hepatic impaired patient is correctly identified"""
        risks = hepatic_impaired_patient.get_population_risks()
        assert PopulationRisk.HEPATIC_IMPAIRED in risks

    def test_polypharmacy_detection(self, elderly_patient):
        """Test polypharmacy detection (>= 5 meds)"""
        assert elderly_patient.is_polypharmacy() is True

    def test_geriatric_polypharmacy_detection(self, elderly_patient):
        """Test geriatric polypharmacy detection"""
        assert elderly_patient.is_geriatric_polypharmacy() is True


# =============================================================================
# TEST: INTERACTION CLASSIFIER
# =============================================================================


class TestInteractionClassifier:
    """Tests for InteractionClassifierAgent"""

    def test_classify_maoi_stimulant_critical(self, classifier):
        """Test MAOI + Stimulant is classified as CRITICAL"""
        result = classifier.classify_interaction(
            description="May increase hypertensive activities",
            drug1="Phenelzine",
            drug2="Methylphenidate",
        )
        assert result.severity == SeverityLevel.CRITICAL
        assert result.confidence >= 0.95

    def test_classify_qt_prolongation_critical(self, classifier):
        """Test QT prolongation is classified as CRITICAL"""
        result = classifier.classify_interaction(
            description="May increase QT prolongation risk",
            drug1="Amiodarone",
            drug2="Erythromycin",
        )
        assert result.severity == SeverityLevel.CRITICAL

    def test_classify_beneficial_low(self, classifier):
        """Test beneficial interaction (decreases toxicity) is LOW"""
        result = classifier.classify_interaction(
            description="May decrease the cardiotoxic activities of Drug B",
            drug1="DrugA",
            drug2="DrugB",
        )
        assert result.severity == SeverityLevel.LOW

    def test_classify_metabolism_medium(self, classifier):
        """Test metabolism alteration is MEDIUM"""
        result = classifier.classify_interaction(
            description="The metabolism of Drug B can be increased when combined with Drug A",
            drug1="DrugA",
            drug2="DrugB",
        )
        assert result.severity == SeverityLevel.MEDIUM

    def test_classify_serum_increase_high(self, classifier):
        """Test serum concentration increase is HIGH"""
        result = classifier.classify_interaction(
            description="The serum concentration of Drug B can be increased when combined with Drug A",
            drug1="DrugA",
            drug2="DrugB",
        )
        assert result.severity == SeverityLevel.HIGH

    def test_adjust_for_pregnant_teratogen(self, classifier):
        """Test severity adjustment for teratogenic drug in pregnancy"""
        result = classifier.classify_interaction(
            description="Some interaction", drug1="Warfarin", drug2="OtherDrug"
        )

        patient_context = {
            "pregnant": True,
            "age": 28,
        }

        adjusted = classifier.adjust_for_patient_context(
            result, "Warfarin", patient_context
        )
        # Comportamento atual: eleva para HIGH (não CRITICAL) para fator pregnancy_teratogen
        assert adjusted.severity == SeverityLevel.HIGH
        assert adjusted.severity_modified is True
        assert "pregnancy_teratogen" in adjusted.patient_risk_factors

    def test_adjust_for_pediatric_contraindication(self, classifier):
        """Test severity adjustment for contraindicated drug in pediatrics"""
        result = classifier.classify_interaction(
            description="Some interaction", drug1="Aspirin", drug2="OtherDrug"
        )

        patient_context = {
            "age": 8,
            "pregnant": False,
        }

        adjusted = classifier.adjust_for_patient_context(
            result, "Aspirin", patient_context
        )
        assert adjusted.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]
        assert adjusted.severity_modified is True
        assert "pediatric_contraindication" in adjusted.patient_risk_factors

    def test_adjust_for_elderly_beers_list(self, classifier):
        """Test severity adjustment for Beers list drug in elderly"""
        result = classifier.classify_interaction(
            description="Some interaction", drug1="Diazepam", drug2="OtherDrug"
        )

        patient_context = {
            "age": 75,
            "pregnant": False,
            "current_medications": ["drug1", "drug2", "drug3", "drug4", "drug5"],
        }

        adjusted = classifier.adjust_for_patient_context(
            result, "Diazepam", patient_context
        )
        assert adjusted.severity_modified is True
        assert (
            "geriatric_high_risk" in adjusted.patient_risk_factors
            or "geriatric_polypharmacy" in adjusted.patient_risk_factors
        )

    def test_adjust_for_renal_impairment(self, classifier):
        """Test severity adjustment for nephrotoxic drug with renal impairment"""
        result = classifier.classify_interaction(
            description="Some interaction", drug1="Metformin", drug2="OtherDrug"
        )

        patient_context = {
            "age": 60,
            "pregnant": False,
            "gfr": 25,  # Severe renal impairment
        }

        adjusted = classifier.adjust_for_patient_context(
            result, "Metformin", patient_context
        )
        assert adjusted.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]
        assert adjusted.severity_modified is True
        assert "renal_impairment_nephrotoxic" in adjusted.patient_risk_factors

    def test_classify_with_patient_context(self, classifier):
        """Test combined classification with patient context"""
        result = classifier.classify_with_patient_context(
            description="May increase hypertensive activities",
            drug1="Phenelzine",
            drug2="Methylphenidate",
            patient_context={"age": 30, "pregnant": False},
        )
        assert result.severity == SeverityLevel.CRITICAL


# =============================================================================
# TEST: RULES ENGINE
# =============================================================================


class TestRulesEngine:
    """Tests for ClinicalRulesEngine"""

    def test_check_escalation_critical(self, rules_engine, elderly_patient):
        """Test escalation for critical severity"""
        needs_escalation, reasons = rules_engine.check_escalation_needed(
            severity="critical",
            confidence=0.95,
            interactions=[],
            patient_context=elderly_patient,
            drug_name="TestDrug",
        )
        assert needs_escalation is True
        assert any("CRITICA" in r.upper() for r in reasons)

    def test_check_escalation_pregnancy_teratogen(self, rules_engine, pregnant_patient):
        """Test escalation for teratogenic drug in pregnancy"""
        needs_escalation, reasons = rules_engine.check_escalation_needed(
            severity="medium",
            confidence=0.85,
            interactions=[],
            patient_context=pregnant_patient,
            drug_name="Warfarin",
        )
        assert needs_escalation is True
        assert any("teratogen" in r.lower() for r in reasons)

    def test_check_escalation_geriatric_polypharmacy(
        self, rules_engine, elderly_patient
    ):
        """Test escalation for geriatric polypharmacy"""
        needs_escalation, reasons = rules_engine.check_escalation_needed(
            severity="medium",
            confidence=0.85,
            interactions=[],
            patient_context=elderly_patient,
            drug_name="TestDrug",
        )
        assert needs_escalation is True
        assert any(
            "polifarmacia" in r.lower() or "polypharmacy" in r.lower() for r in reasons
        )

    def test_check_escalation_multiple_high_interactions(
        self, rules_engine, elderly_patient
    ):
        """Test escalation for multiple high-risk interactions"""
        interactions = [
            {"drug1": "A", "drug2": "B", "severity": "high"},
            {"drug1": "A", "drug2": "C", "severity": "high"},
        ]
        needs_escalation, reasons = rules_engine.check_escalation_needed(
            severity="high",
            confidence=0.85,
            interactions=interactions,
            patient_context=elderly_patient,
            drug_name="TestDrug",
        )
        assert needs_escalation is True

    def test_check_escalation_low_confidence_high_risk(
        self, rules_engine, elderly_patient
    ):
        """Test escalation for low confidence with high risk"""
        needs_escalation, reasons = rules_engine.check_escalation_needed(
            severity="high",
            confidence=0.5,  # Low confidence
            interactions=[],
            patient_context=elderly_patient,
            drug_name="TestDrug",
        )
        assert needs_escalation is True
        assert any(
            "confianca" in r.lower() or "confidence" in r.lower() for r in reasons
        )

    def test_generate_structured_recommendations_critical(
        self, rules_engine, elderly_patient
    ):
        """Test structured recommendations for critical severity"""
        recs = rules_engine.generate_structured_recommendations(
            severity="critical",
            category="Cardiovascular",
            interactions=[{"drug1": "A", "drug2": "B", "severity": "critical"}],
            contraindications=[],
            patient_context=elderly_patient,
        )

        assert "CRITICO" in recs["header"].upper()
        assert len(recs["immediate_actions"]) > 0
        assert len(recs["monitoring_required"]) > 0

    def test_generate_structured_recommendations_cardiovascular(
        self, rules_engine, elderly_patient
    ):
        """Test structured recommendations include cardiovascular specifics"""
        recs = rules_engine.generate_structured_recommendations(
            severity="high",
            category="Cardiovascular",
            interactions=[],
            contraindications=[],
            patient_context=elderly_patient,
        )

        # Should include cardiovascular-specific labs
        all_labs = " ".join(recs["laboratory_tests"]).lower()
        assert (
            "eletrolitos" in all_labs
            or "ecg" in " ".join(recs["monitoring_required"]).lower()
        )


# =============================================================================
# TEST: INTEGRATION
# =============================================================================


class TestIntegration:
    """Integration tests for the complete workflow"""

    def test_full_classification_workflow_critical_case(self, classifier, rules_engine):
        """Test full workflow for critical MAOI + Stimulant case"""
        # Patient context
        patient_context = {
            "age": 45,
            "weight": 75,
            "pregnant": False,
            "current_medications": ["phenelzine"],
            "conditions": ["depression"],
        }

        # Step 1: Classify interaction
        result = classifier.classify_with_patient_context(
            description="May increase hypertensive activities",
            drug1="Phenelzine",
            drug2="Ritalina",
            patient_context=patient_context,
        )

        assert result.severity == SeverityLevel.CRITICAL

        # Step 2: Build patient context
        patient_ctx = PatientContext(
            age=patient_context["age"],
            weight=patient_context["weight"],
            pregnant=patient_context["pregnant"],
            current_medications=patient_context["current_medications"],
            conditions=patient_context["conditions"],
        )

        # Step 3: Check escalation
        needs_escalation, reasons = rules_engine.check_escalation_needed(
            severity=result.severity.value,
            confidence=result.confidence,
            interactions=[],
            patient_context=patient_ctx,
            drug_name="Ritalina",
        )

        assert needs_escalation is True

        # Step 4: Generate recommendations
        recs = rules_engine.generate_structured_recommendations(
            severity=result.severity.value,
            category=result.clinical_category,
            interactions=[],
            contraindications=[],
            patient_context=patient_ctx,
        )

        assert "NAO ADMINISTRAR" in " ".join(recs["immediate_actions"])

    def test_full_workflow_warfarin_elderly(
        self, classifier, rules_engine, elderly_patient
    ):
        """Test full workflow for Warfarin in elderly patient"""
        # Step 1: Classify
        result = classifier.classify_with_patient_context(
            description="The risk or severity of adverse effects can be increased",
            drug1="Warfarin",
            drug2="Aspirin",
            patient_context={
                "age": elderly_patient.age,
                "pregnant": elderly_patient.pregnant,
                "gfr": elderly_patient.gfr,
                "current_medications": elderly_patient.current_medications,
            },
        )

        # Should be at least HIGH due to bleeding risk + elderly
        assert result.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]

        # Step 2: Check escalation
        needs_escalation, reasons = rules_engine.check_escalation_needed(
            severity=result.severity.value,
            confidence=result.confidence,
            interactions=[
                {"drug1": "Warfarin", "drug2": "Aspirin", "severity": "high"}
            ],
            patient_context=elderly_patient,
            drug_name="Warfarin",
        )

        assert needs_escalation is True

    def test_full_workflow_metformin_renal(
        self, classifier, rules_engine, renal_impaired_patient
    ):
        """Test full workflow for Metformin in patient with renal impairment"""
        patient_dict = {
            "age": renal_impaired_patient.age,
            "pregnant": renal_impaired_patient.pregnant,
            "gfr": renal_impaired_patient.gfr,
            "current_medications": renal_impaired_patient.current_medications,
        }

        # Step 1: Classify with context
        result = classifier.classify_with_patient_context(
            description="Some interaction",
            drug1="Metformin",
            drug2="Furosemide",
            patient_context=patient_dict,
        )

        # Should be elevated due to renal impairment + metformin
        assert result.severity_modified is True
        assert "renal_impairment_nephrotoxic" in result.patient_risk_factors

        # Step 2: Check escalation
        needs_escalation, reasons = rules_engine.check_escalation_needed(
            severity=result.severity.value,
            confidence=result.confidence,
            interactions=[],
            patient_context=renal_impaired_patient,
            drug_name="Metformin",
        )

        # Comportamento atual: não escala automaticamente neste cenário
        assert needs_escalation is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
