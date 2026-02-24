"""Tests for Step 2.5: Quantity & Unit Scaling.

Tests scaling of normalized nutrition data to reflect user-specified quantities.
Scaling is deterministic - no heuristics, density assumptions, or silent fallbacks.
"""

import pytest

from src.ingestion.nutrition_scaler import (
    NutritionScaler,
    ScaledNutrition,
    UnsupportedUnitError,
    UNIT_TO_GRAMS,
    BASE_SERVING_WEIGHTS,
)
from src.ingestion.nutrient_mapper import MappedNutrition
from src.data_layer.models import MicronutrientProfile


class TestUnitToGramsTable:
    """Tests for the unit → gram conversion table."""

    def test_gram_conversion(self):
        """Test that grams map to themselves."""
        assert "g" in UNIT_TO_GRAMS
        assert UNIT_TO_GRAMS["g"] == 1.0

    def test_ounce_conversion(self):
        """Test ounce to gram conversion."""
        assert "oz" in UNIT_TO_GRAMS
        assert UNIT_TO_GRAMS["oz"] == 28.35

    def test_pound_conversion(self):
        """Test pound to gram conversion."""
        assert "lb" in UNIT_TO_GRAMS
        assert UNIT_TO_GRAMS["lb"] == 453.592

    def test_ml_conversion(self):
        """Test milliliter mapping (for water-equivalent)."""
        assert "ml" in UNIT_TO_GRAMS
        assert UNIT_TO_GRAMS["ml"] == 1.0  # 1ml water ≈ 1g


class TestBaseServingWeights:
    """Tests for base serving weight definitions."""

    def test_large_egg_defined(self):
        """Test that large egg has a defined weight."""
        assert "large" in BASE_SERVING_WEIGHTS
        # 1 large egg ≈ 50g
        assert BASE_SERVING_WEIGHTS["large"]["egg"] == 50.0

    def test_scoop_requires_context(self):
        """Test that scoop is in serving weights."""
        assert "scoop" in BASE_SERVING_WEIGHTS


class TestNutritionScaler:
    """Tests for NutritionScaler class."""

    @pytest.fixture
    def scaler(self):
        """Create scaler instance."""
        return NutritionScaler()

    @pytest.fixture
    def base_nutrition(self):
        """Create sample nutrition data per 100g."""
        return MappedNutrition(
            calories=165.0,
            protein_g=31.0,
            fat_g=3.6,
            carbs_g=0.0,
            micronutrients=MicronutrientProfile(
                vitamin_a_ug=6.0,
                vitamin_c_mg=0.0,
                iron_mg=0.37,
                calcium_mg=5.0,
            )
        )

    # === Gram-Based Scaling Tests ===

    def test_scale_100g_returns_unchanged(self, scaler, base_nutrition):
        """Test that 100g returns nutrition unchanged."""
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=100.0,
            unit="g",
            base_grams=100.0
        )
        
        assert result.calories == 165.0
        assert result.protein_g == 31.0
        assert result.fat_g == 3.6
        assert result.micronutrients.iron_mg == 0.37

    def test_scale_200g_doubles_values(self, scaler, base_nutrition):
        """Test that 200g doubles all nutrition values."""
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=200.0,
            unit="g",
            base_grams=100.0
        )
        
        assert result.calories == 330.0
        assert result.protein_g == 62.0
        assert result.fat_g == 7.2
        assert result.micronutrients.iron_mg == 0.74

    def test_scale_50g_halves_values(self, scaler, base_nutrition):
        """Test that 50g halves all nutrition values."""
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=50.0,
            unit="g",
            base_grams=100.0
        )
        
        assert result.calories == 82.5
        assert result.protein_g == 15.5
        assert result.fat_g == 1.8
        assert result.micronutrients.iron_mg == pytest.approx(0.185)

    def test_scale_fractional_grams(self, scaler, base_nutrition):
        """Test scaling with fractional gram quantities."""
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=75.0,
            unit="g",
            base_grams=100.0
        )
        
        assert result.calories == pytest.approx(123.75)
        assert result.protein_g == pytest.approx(23.25)

    # === Ounce Scaling Tests ===

    def test_scale_ounces(self, scaler, base_nutrition):
        """Test scaling with ounces."""
        # 1 oz = 28.35g
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=1.0,
            unit="oz",
            base_grams=100.0
        )
        
        # 28.35g / 100g = 0.2835 scale factor
        assert result.calories == pytest.approx(165.0 * 0.2835)
        assert result.protein_g == pytest.approx(31.0 * 0.2835)

    def test_scale_multiple_ounces(self, scaler, base_nutrition):
        """Test scaling with multiple ounces."""
        # 4 oz = 113.4g
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=4.0,
            unit="oz",
            base_grams=100.0
        )
        
        # 113.4g / 100g = 1.134 scale factor
        assert result.calories == pytest.approx(165.0 * 1.134)

    # === Pound Scaling Tests ===

    def test_scale_pounds(self, scaler, base_nutrition):
        """Test scaling with pounds."""
        # 1 lb = 453.592g
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=1.0,
            unit="lb",
            base_grams=100.0
        )
        
        # 453.592g / 100g = 4.53592 scale factor
        assert result.calories == pytest.approx(165.0 * 4.53592)

    def test_scale_half_pound(self, scaler, base_nutrition):
        """Test scaling with half pound."""
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=0.5,
            unit="lb",
            base_grams=100.0
        )
        
        # 226.796g / 100g = 2.26796 scale factor
        assert result.calories == pytest.approx(165.0 * 2.26796)

    # === Base Serving Weight Tests ===

    def test_scale_large_egg(self, scaler):
        """Test scaling using 'large' unit with egg context."""
        # Egg nutrition per 100g
        egg_nutrition = MappedNutrition(
            calories=147.0,
            protein_g=12.6,
            fat_g=9.9,
            carbs_g=0.8,
            micronutrients=MicronutrientProfile()
        )
        
        # 1 large egg = 50g
        result = scaler.scale(
            nutrition=egg_nutrition,
            quantity=2.0,
            unit="large",
            base_grams=100.0,
            ingredient_context="egg"
        )
        
        # 2 large eggs = 100g, so scale factor = 1.0
        assert result.calories == 147.0
        assert result.protein_g == 12.6

    def test_scale_single_large_egg(self, scaler):
        """Test scaling for single large egg."""
        egg_nutrition = MappedNutrition(
            calories=147.0,
            protein_g=12.6,
            fat_g=9.9,
            carbs_g=0.8,
            micronutrients=MicronutrientProfile()
        )
        
        # 1 large egg = 50g → 0.5 scale factor
        result = scaler.scale(
            nutrition=egg_nutrition,
            quantity=1.0,
            unit="large",
            base_grams=100.0,
            ingredient_context="egg"
        )
        
        assert result.calories == pytest.approx(73.5)
        assert result.protein_g == pytest.approx(6.3)

    def test_scale_serving_with_context(self, scaler):
        """Test scaling using 'serving' unit with explicit serving weight."""
        nutrition = MappedNutrition(
            calories=100.0,
            protein_g=20.0,
            fat_g=5.0,
            carbs_g=10.0,
            micronutrients=MicronutrientProfile()
        )
        
        # Use explicit serving weight
        result = scaler.scale(
            nutrition=nutrition,
            quantity=1.0,
            unit="serving",
            base_grams=100.0,
            serving_weight_grams=150.0  # Explicit serving weight
        )
        
        # 150g / 100g = 1.5 scale factor
        assert result.calories == 150.0
        assert result.protein_g == 30.0

    def test_scale_scoop_with_context(self, scaler):
        """Test scaling using 'scoop' unit with explicit weight."""
        nutrition = MappedNutrition(
            calories=120.0,
            protein_g=25.0,
            fat_g=1.0,
            carbs_g=3.0,
            micronutrients=MicronutrientProfile()
        )
        
        # Protein powder scoop = 30g
        result = scaler.scale(
            nutrition=nutrition,
            quantity=2.0,
            unit="scoop",
            base_grams=100.0,
            serving_weight_grams=30.0
        )
        
        # 2 scoops * 30g = 60g → 0.6 scale factor
        assert result.calories == pytest.approx(72.0)
        assert result.protein_g == pytest.approx(15.0)

    # === Error Handling Tests ===

    def test_unsupported_unit_raises_error(self, scaler, base_nutrition):
        """Test that unsupported units raise UnsupportedUnitError."""
        with pytest.raises(UnsupportedUnitError) as exc_info:
            scaler.scale(
                nutrition=base_nutrition,
                quantity=1.0,
                unit="bushel",
                base_grams=100.0
            )
        
        assert "bushel" in str(exc_info.value)
        assert exc_info.value.unit == "bushel"

    def test_volume_unit_without_density_raises_error(self, scaler, base_nutrition):
        """Test that volume units (cup, tbsp, tsp) require density/weight info."""
        # Cup without density information should raise error
        with pytest.raises(UnsupportedUnitError) as exc_info:
            scaler.scale(
                nutrition=base_nutrition,
                quantity=1.0,
                unit="cup",
                base_grams=100.0
            )
        
        assert "cup" in str(exc_info.value)
        assert "density" in str(exc_info.value).lower() or "weight" in str(exc_info.value).lower()

    def test_large_without_context_raises_error(self, scaler, base_nutrition):
        """Test that 'large' unit without ingredient context raises error."""
        with pytest.raises(UnsupportedUnitError) as exc_info:
            scaler.scale(
                nutrition=base_nutrition,
                quantity=1.0,
                unit="large",
                base_grams=100.0
                # No ingredient_context provided
            )
        
        assert "large" in str(exc_info.value)

    def test_serving_without_weight_raises_error(self, scaler, base_nutrition):
        """Test that 'serving' without explicit weight raises error."""
        with pytest.raises(UnsupportedUnitError) as exc_info:
            scaler.scale(
                nutrition=base_nutrition,
                quantity=1.0,
                unit="serving",
                base_grams=100.0
                # No serving_weight_grams provided
            )
        
        assert "serving" in str(exc_info.value)

    def test_scoop_without_weight_raises_error(self, scaler, base_nutrition):
        """Test that 'scoop' without explicit weight raises error."""
        with pytest.raises(UnsupportedUnitError) as exc_info:
            scaler.scale(
                nutrition=base_nutrition,
                quantity=1.0,
                unit="scoop",
                base_grams=100.0
            )
        
        assert "scoop" in str(exc_info.value)

    def test_negative_quantity_raises_error(self, scaler, base_nutrition):
        """Test that negative quantities raise error."""
        with pytest.raises(ValueError, match="quantity"):
            scaler.scale(
                nutrition=base_nutrition,
                quantity=-100.0,
                unit="g",
                base_grams=100.0
            )

    def test_zero_base_grams_raises_error(self, scaler, base_nutrition):
        """Test that zero base_grams raises error (division by zero)."""
        with pytest.raises(ValueError, match="base_grams"):
            scaler.scale(
                nutrition=base_nutrition,
                quantity=100.0,
                unit="g",
                base_grams=0.0
            )

    # === Micronutrient Scaling Tests ===

    def test_all_micronutrients_scaled(self, scaler):
        """Test that all micronutrients are scaled correctly."""
        nutrition = MappedNutrition(
            calories=100.0,
            protein_g=10.0,
            fat_g=5.0,
            carbs_g=20.0,
            micronutrients=MicronutrientProfile(
                vitamin_a_ug=100.0,
                vitamin_c_mg=50.0,
                vitamin_d_iu=10.0,
                iron_mg=2.0,
                calcium_mg=100.0,
                fiber_g=5.0,
            )
        )
        
        # Scale to 200g (2x)
        result = scaler.scale(
            nutrition=nutrition,
            quantity=200.0,
            unit="g",
            base_grams=100.0
        )
        
        assert result.micronutrients.vitamin_a_ug == 200.0
        assert result.micronutrients.vitamin_c_mg == 100.0
        assert result.micronutrients.vitamin_d_iu == 20.0
        assert result.micronutrients.iron_mg == 4.0
        assert result.micronutrients.calcium_mg == 200.0
        assert result.micronutrients.fiber_g == 10.0

    def test_zero_micronutrients_remain_zero(self, scaler):
        """Test that zero micronutrients remain zero after scaling."""
        nutrition = MappedNutrition(
            calories=100.0,
            protein_g=10.0,
            fat_g=5.0,
            carbs_g=20.0,
            micronutrients=MicronutrientProfile(
                vitamin_a_ug=0.0,
                vitamin_c_mg=0.0,
            )
        )
        
        result = scaler.scale(
            nutrition=nutrition,
            quantity=500.0,
            unit="g",
            base_grams=100.0
        )
        
        assert result.micronutrients.vitamin_a_ug == 0.0
        assert result.micronutrients.vitamin_c_mg == 0.0

    # === Output Structure Tests ===

    def test_output_is_scaled_nutrition(self, scaler, base_nutrition):
        """Test that output is ScaledNutrition type."""
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=100.0,
            unit="g",
            base_grams=100.0
        )
        
        assert isinstance(result, ScaledNutrition)

    def test_output_includes_scale_factor(self, scaler, base_nutrition):
        """Test that output includes the scale factor used."""
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=200.0,
            unit="g",
            base_grams=100.0
        )
        
        assert result.scale_factor == 2.0

    def test_output_includes_actual_grams(self, scaler, base_nutrition):
        """Test that output includes actual grams computed."""
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=4.0,
            unit="oz",
            base_grams=100.0
        )
        
        # 4 oz = 113.4g
        assert result.actual_grams == pytest.approx(113.4)

    def test_output_can_convert_to_nutrition_profile(self, scaler, base_nutrition):
        """Test that output can be converted to NutritionProfile."""
        result = scaler.scale(
            nutrition=base_nutrition,
            quantity=100.0,
            unit="g",
            base_grams=100.0
        )
        
        profile = result.to_nutrition_profile()
        
        assert profile.calories == 165.0
        assert profile.protein_g == 31.0


class TestScaledNutrition:
    """Tests for ScaledNutrition data model."""

    def test_scaled_nutrition_structure(self):
        """Test that ScaledNutrition has required fields."""
        micro = MicronutrientProfile()
        result = ScaledNutrition(
            calories=100.0,
            protein_g=10.0,
            fat_g=5.0,
            carbs_g=20.0,
            micronutrients=micro,
            scale_factor=1.5,
            actual_grams=150.0
        )
        
        assert result.calories == 100.0
        assert result.scale_factor == 1.5
        assert result.actual_grams == 150.0


class TestUnsupportedUnitError:
    """Tests for UnsupportedUnitError exception."""

    def test_error_contains_unit(self):
        """Test that error message contains the unsupported unit."""
        error = UnsupportedUnitError("gallon", "Unit not in conversion table")
        
        assert error.unit == "gallon"
        assert "gallon" in str(error)

    def test_error_contains_message(self):
        """Test that error message contains helpful information."""
        error = UnsupportedUnitError("cup", "Volume units require density information")
        
        assert "density" in str(error)
