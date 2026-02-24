"""Tests for ingredient name normalization.

Step 2.1: Ingredient Name Normalization.

Normalization prepares parsed ingredient names for reliable USDA API lookup.
"""

import pytest

from src.ingestion.ingredient_normalizer import (
    IngredientNormalizer,
    NormalizationResult,
    CONTROLLED_DESCRIPTORS,
)


class TestNormalizationResult:
    """Tests for NormalizationResult data model."""

    def test_result_contains_original_and_canonical(self):
        """Test that result contains both original and canonical names."""
        result = NormalizationResult(
            original_name="Large Chicken Breast",
            canonical_name="chicken breast",
            removed_descriptors=["large"]
        )
        
        assert result.original_name == "Large Chicken Breast"
        assert result.canonical_name == "chicken breast"
        assert result.removed_descriptors == ["large"]

    def test_result_with_no_descriptors_removed(self):
        """Test result when no descriptors were removed."""
        result = NormalizationResult(
            original_name="salmon",
            canonical_name="salmon",
            removed_descriptors=[]
        )
        
        assert result.removed_descriptors == []


class TestControlledDescriptors:
    """Tests for the controlled descriptors list."""

    def test_size_descriptors_defined(self):
        """Test that common size descriptors are in the list."""
        assert "large" in CONTROLLED_DESCRIPTORS
        assert "small" in CONTROLLED_DESCRIPTORS
        assert "medium" in CONTROLLED_DESCRIPTORS
        assert "extra large" in CONTROLLED_DESCRIPTORS

    def test_preparation_descriptors_defined(self):
        """Test that preparation descriptors are in the list."""
        assert "raw" in CONTROLLED_DESCRIPTORS
        assert "cooked" in CONTROLLED_DESCRIPTORS
        assert "fresh" in CONTROLLED_DESCRIPTORS
        assert "frozen" in CONTROLLED_DESCRIPTORS

    def test_cut_descriptors_defined(self):
        """Test that cut/portion descriptors are in the list."""
        assert "boneless" in CONTROLLED_DESCRIPTORS
        assert "skinless" in CONTROLLED_DESCRIPTORS
        assert "diced" in CONTROLLED_DESCRIPTORS
        assert "sliced" in CONTROLLED_DESCRIPTORS

    def test_quality_descriptors_defined(self):
        """Test that quality descriptors are in the list."""
        assert "organic" in CONTROLLED_DESCRIPTORS


class TestIngredientNormalizer:
    """Tests for IngredientNormalizer."""

    @pytest.fixture
    def normalizer(self):
        """Create normalizer instance."""
        return IngredientNormalizer()

    # === Lowercasing Tests ===

    def test_normalize_converts_to_lowercase(self, normalizer):
        """Test that names are converted to lowercase."""
        result = normalizer.normalize("CHICKEN BREAST")
        assert result.canonical_name == "chicken breast"

    def test_normalize_mixed_case(self, normalizer):
        """Test mixed case normalization."""
        result = normalizer.normalize("Chicken Breast")
        assert result.canonical_name == "chicken breast"

    # === Whitespace Tests ===

    def test_normalize_trims_whitespace(self, normalizer):
        """Test that leading/trailing whitespace is removed."""
        result = normalizer.normalize("  salmon  ")
        assert result.canonical_name == "salmon"

    def test_normalize_collapses_internal_whitespace(self, normalizer):
        """Test that multiple internal spaces are collapsed to single space."""
        result = normalizer.normalize("chicken   breast")
        assert result.canonical_name == "chicken breast"

    # === Descriptor Removal Tests ===

    def test_normalize_removes_large(self, normalizer):
        """Test removal of 'large' descriptor."""
        result = normalizer.normalize("large egg")
        assert result.canonical_name == "egg"
        assert "large" in result.removed_descriptors

    def test_normalize_removes_raw(self, normalizer):
        """Test removal of 'raw' descriptor."""
        result = normalizer.normalize("raw chicken breast")
        assert result.canonical_name == "chicken breast"
        assert "raw" in result.removed_descriptors

    def test_normalize_removes_fresh(self, normalizer):
        """Test removal of 'fresh' descriptor."""
        result = normalizer.normalize("fresh spinach")
        assert result.canonical_name == "spinach"
        assert "fresh" in result.removed_descriptors

    def test_normalize_removes_boneless_skinless(self, normalizer):
        """Test removal of 'boneless' and 'skinless' descriptors."""
        result = normalizer.normalize("boneless skinless chicken thigh")
        assert result.canonical_name == "chicken thigh"
        assert "boneless" in result.removed_descriptors
        assert "skinless" in result.removed_descriptors

    def test_normalize_removes_organic(self, normalizer):
        """Test removal of 'organic' descriptor."""
        result = normalizer.normalize("organic broccoli")
        assert result.canonical_name == "broccoli"
        assert "organic" in result.removed_descriptors

    def test_normalize_removes_multiple_descriptors(self, normalizer):
        """Test removal of multiple descriptors in one name."""
        result = normalizer.normalize("large raw organic chicken breast")
        assert result.canonical_name == "chicken breast"
        assert "large" in result.removed_descriptors
        assert "raw" in result.removed_descriptors
        assert "organic" in result.removed_descriptors

    def test_normalize_removes_extra_large(self, normalizer):
        """Test removal of multi-word descriptor 'extra large'."""
        result = normalizer.normalize("extra large egg")
        assert result.canonical_name == "egg"
        assert "extra large" in result.removed_descriptors

    def test_normalize_removes_cooked(self, normalizer):
        """Test removal of 'cooked' descriptor."""
        result = normalizer.normalize("cooked rice")
        assert result.canonical_name == "rice"
        assert "cooked" in result.removed_descriptors

    def test_normalize_removes_frozen(self, normalizer):
        """Test removal of 'frozen' descriptor."""
        result = normalizer.normalize("frozen peas")
        assert result.canonical_name == "peas"
        assert "frozen" in result.removed_descriptors

    def test_normalize_removes_diced(self, normalizer):
        """Test removal of 'diced' descriptor."""
        result = normalizer.normalize("diced tomatoes")
        assert result.canonical_name == "tomatoes"
        assert "diced" in result.removed_descriptors

    # === Preservation Tests ===

    def test_normalize_preserves_core_ingredient_name(self, normalizer):
        """Test that core ingredient name is preserved."""
        result = normalizer.normalize("chicken breast")
        assert result.canonical_name == "chicken breast"

    def test_normalize_preserves_original_name(self, normalizer):
        """Test that original name is preserved in result."""
        result = normalizer.normalize("Large Chicken Breast")
        assert result.original_name == "Large Chicken Breast"

    def test_normalize_no_changes_needed(self, normalizer):
        """Test when no normalization changes are needed."""
        result = normalizer.normalize("salmon")
        assert result.canonical_name == "salmon"
        assert result.removed_descriptors == []

    # === Edge Cases ===

    def test_normalize_empty_string(self, normalizer):
        """Test normalization of empty string."""
        result = normalizer.normalize("")
        assert result.canonical_name == ""
        assert result.removed_descriptors == []

    def test_normalize_only_descriptors(self, normalizer):
        """Test when name is only descriptors (edge case)."""
        result = normalizer.normalize("large raw fresh")
        # Should result in empty canonical name
        assert result.canonical_name == ""

    def test_normalize_descriptor_as_part_of_word(self, normalizer):
        """Test that descriptors embedded in words are NOT removed."""
        # "organic" should not be removed from "organically" if that were a word
        # "raw" should not be removed from "strawberry"
        result = normalizer.normalize("strawberry")
        assert result.canonical_name == "strawberry"
        assert "raw" not in result.removed_descriptors

    def test_normalize_descriptor_case_insensitive(self, normalizer):
        """Test that descriptor removal is case-insensitive."""
        result = normalizer.normalize("LARGE EGG")
        assert result.canonical_name == "egg"
        assert "large" in result.removed_descriptors

    # === Complex Real-World Examples ===

    def test_normalize_complex_chicken(self, normalizer):
        """Test complex chicken ingredient."""
        result = normalizer.normalize("Boneless Skinless Chicken Breast, raw")
        assert result.canonical_name == "chicken breast"

    def test_normalize_complex_egg(self, normalizer):
        """Test complex egg ingredient."""
        result = normalizer.normalize("2 Large Organic Eggs")
        # Note: "2" is not a descriptor, should remain (but will be weird)
        # Actually the quantity should be parsed separately - this tests name only
        result = normalizer.normalize("Large Organic Eggs")
        assert result.canonical_name == "eggs"

    def test_normalize_with_comma_separated_descriptors(self, normalizer):
        """Test handling of comma-separated format."""
        result = normalizer.normalize("chicken, breast, boneless, skinless")
        # Commas should be handled - the canonical should extract core ingredient
        assert "chicken" in result.canonical_name
        assert "breast" in result.canonical_name


class TestNormalizerDeterminism:
    """Tests to ensure normalization is deterministic."""

    @pytest.fixture
    def normalizer(self):
        """Create normalizer instance."""
        return IngredientNormalizer()

    def test_same_input_same_output(self, normalizer):
        """Test that same input always produces same output."""
        input_name = "Large Raw Chicken Breast"
        
        result1 = normalizer.normalize(input_name)
        result2 = normalizer.normalize(input_name)
        result3 = normalizer.normalize(input_name)
        
        assert result1.canonical_name == result2.canonical_name == result3.canonical_name
        assert result1.removed_descriptors == result2.removed_descriptors == result3.removed_descriptors

    def test_different_case_same_canonical(self, normalizer):
        """Test that different cases produce same canonical name."""
        assert normalizer.normalize("CHICKEN").canonical_name == normalizer.normalize("chicken").canonical_name
        assert normalizer.normalize("Chicken").canonical_name == normalizer.normalize("CHICKEN").canonical_name
