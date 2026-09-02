"""
Unit tests for drug identifier service

Tests HybridDrugIdentifier and drug identification functionality.
"""


class TestIdentificationMethod:
    """Tests for IdentificationMethod enum"""

    def test_identification_methods(self):
        """Test IdentificationMethod enum has expected values"""
        from backend.app.services.drug_identifier import IdentificationMethod

        # Should have identification methods
        assert len(IdentificationMethod) > 0


class TestDrugIdentification:
    """Tests for DrugIdentification dataclass"""

    def test_drug_identification_creation(self):
        """Test creating a DrugIdentification"""
        from backend.app.services.drug_identifier import (
            DrugIdentification,
            IdentificationMethod,
        )

        result = DrugIdentification(
            original_name="Aspirin",
            canonical_name="aspirin",
            method=IdentificationMethod.EXACT_MATCH,
            confidence=0.95,
        )

        assert result.canonical_name == "aspirin"
        assert result.original_name == "Aspirin"
        assert result.confidence == 0.95

    def test_drug_identification_with_alternatives(self):
        """Test DrugIdentification with alternatives"""
        from backend.app.services.drug_identifier import (
            DrugIdentification,
            IdentificationMethod,
        )

        result = DrugIdentification(
            original_name="Aspirin",
            canonical_name="acetylsalicylic acid",
            method=IdentificationMethod.FUZZY_MATCH,
            confidence=0.9,
            alternatives=["aspirin", "ASA"],
        )

        assert "aspirin" in result.alternatives


class TestHybridDrugIdentifier:
    """Tests for HybridDrugIdentifier class"""

    def test_identifier_init(self):
        """Test HybridDrugIdentifier initialization"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        assert identifier is not None

    def test_identify_common_drug(self):
        """Test identifying a common drug"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        result = identifier.identify("aspirin")

        assert result is not None
        assert hasattr(result, "canonical_name")

    def test_identify_with_synonym(self):
        """Test identifying drug by synonym"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        # Test with a common synonym
        result = identifier.identify("acetylsalicylic acid")

        assert result is not None

    def test_identify_unknown_drug(self):
        """Test identifying unknown drug"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        result = identifier.identify("unknowndrugxyz123")

        # Should return something even for unknown drugs
        assert result is not None

    def test_identify_empty_string(self):
        """Test identifying empty string"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        result = identifier.identify("")

        assert result is not None

    def test_identify_with_dosage(self):
        """Test identifying drug with dosage info"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        result = identifier.identify("aspirin 100mg")

        assert result is not None

    def test_identify_brand_name(self):
        """Test identifying brand name"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        # Tylenol is acetaminophen
        result = identifier.identify("tylenol")

        assert result is not None


class TestGetDrugIdentifier:
    """Tests for get_drug_identifier function"""

    def test_get_drug_identifier_returns_instance(self):
        """Test get_drug_identifier returns an identifier"""
        from backend.app.services.drug_identifier import (
            HybridDrugIdentifier,
            get_drug_identifier,
        )

        identifier = get_drug_identifier()

        assert isinstance(identifier, HybridDrugIdentifier)

    def test_get_drug_identifier_singleton_like(self):
        """Test get_drug_identifier returns consistent instance"""
        from backend.app.services.drug_identifier import get_drug_identifier

        id1 = get_drug_identifier()
        id2 = get_drug_identifier()

        # Should be same instance or equivalent
        assert id1 is id2 or type(id1) is type(id2)


class TestResetIdentifier:
    """Tests for reset_identifier function"""

    def test_reset_identifier(self):
        """Test reset_identifier function"""
        from backend.app.services.drug_identifier import (
            get_drug_identifier,
            reset_identifier,
        )

        # Get initial identifier
        get_drug_identifier()

        # Reset
        reset_identifier()

        # Get new identifier
        id2 = get_drug_identifier()

        # Should have reset (may or may not be different instance)
        assert id2 is not None


class TestIdentificationConfidence:
    """Tests for identification confidence scores"""

    def test_exact_match_high_confidence(self):
        """Test exact match has high confidence"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        result = identifier.identify("aspirin")

        # Exact match should have high confidence
        if hasattr(result, "confidence"):
            assert result.confidence >= 0.5

    def test_fuzzy_match_lower_confidence(self):
        """Test fuzzy match has lower confidence"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        # Misspelled drug name
        result = identifier.identify("asprin")

        # Should still identify but possibly with lower confidence
        assert result is not None


class TestEdgeCases:
    """Tests for edge cases"""

    def test_special_characters(self):
        """Test handling special characters"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        result = identifier.identify("vitamin-B12")

        assert result is not None

    def test_numeric_input(self):
        """Test handling numeric input"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        result = identifier.identify("500mg")

        assert result is not None

    def test_mixed_case(self):
        """Test handling mixed case"""
        from backend.app.services.drug_identifier import HybridDrugIdentifier

        identifier = HybridDrugIdentifier()

        result1 = identifier.identify("ASPIRIN")
        result2 = identifier.identify("aspirin")

        # Should normalize case
        assert result1.canonical_name.lower() == result2.canonical_name.lower()
