"""Tests for Step 2.6: NutritionProfile Construction.

Tests for building clean NutritionProfile instances from scaled nutrition data.
NutritionProfile is the boundary between external (USDA) data and internal logic.
"""

import pytest
from dataclasses import fields, asdict

from src.ingestion.nutrition_profile_builder import (
    NutritionProfileBuilder,
    build_nutrition_profile,
)
from src.ingestion.nutrition_scaler import ScaledNutrition
from src.ingestion.nutrient_mapper import MappedNutrition
from src.data_layer.models import NutritionProfile, MicronutrientProfile


class TestNutritionProfileBuilder:
    """Tests for NutritionProfileBuilder class."""

    @pytest.fixture
    def builder(self):
        """Create builder instance."""
        return NutritionProfileBuilder()

    @pytest.fixture
    def scaled_nutrition(self):
        """Create sample scaled nutrition data."""
        return ScaledNutrition(
            calories=330.0,
            protein_g=62.0,
            fat_g=7.2,
            carbs_g=0.0,
            micronutrients=MicronutrientProfile(
                vitamin_a_ug=12.0,
                vitamin_c_mg=0.0,
                iron_mg=0.74,
                calcium_mg=10.0,
                fiber_g=0.0,
            ),
            scale_factor=2.0,
            actual_grams=200.0
        )

    # === Basic Construction Tests ===

    def test_build_returns_nutrition_profile(self, builder, scaled_nutrition):
        """Test that build returns a NutritionProfile instance."""
        result = builder.build(scaled_nutrition)
        
        assert isinstance(result, NutritionProfile)

    def test_build_transfers_macronutrients(self, builder, scaled_nutrition):
        """Test that macronutrients are transferred correctly."""
        result = builder.build(scaled_nutrition)
        
        assert result.calories == 330.0
        assert result.protein_g == 62.0
        assert result.fat_g == 7.2
        assert result.carbs_g == 0.0

    def test_build_transfers_micronutrients(self, builder, scaled_nutrition):
        """Test that micronutrients are transferred correctly."""
        result = builder.build(scaled_nutrition)
        
        assert result.micronutrients is not None
        assert result.micronutrients.vitamin_a_ug == 12.0
        assert result.micronutrients.iron_mg == 0.74
        assert result.micronutrients.calcium_mg == 10.0

    def test_build_from_mapped_nutrition(self, builder):
        """Test building from MappedNutrition (pre-scaling)."""
        mapped = MappedNutrition(
            calories=165.0,
            protein_g=31.0,
            fat_g=3.6,
            carbs_g=0.0,
            micronutrients=MicronutrientProfile(iron_mg=0.37)
        )
        
        result = builder.build_from_mapped(mapped)
        
        assert isinstance(result, NutritionProfile)
        assert result.calories == 165.0
        assert result.protein_g == 31.0
        assert result.micronutrients.iron_mg == 0.37

    # === Field Completeness Tests ===

    def test_all_macro_fields_present(self, builder, scaled_nutrition):
        """Test that all macronutrient fields are present."""
        result = builder.build(scaled_nutrition)
        
        assert hasattr(result, 'calories')
        assert hasattr(result, 'protein_g')
        assert hasattr(result, 'fat_g')
        assert hasattr(result, 'carbs_g')

    def test_all_micro_fields_present(self, builder, scaled_nutrition):
        """Test that all micronutrient fields are present (even if zero)."""
        result = builder.build(scaled_nutrition)
        
        micro = result.micronutrients
        
        # Vitamins
        assert hasattr(micro, 'vitamin_a_ug')
        assert hasattr(micro, 'vitamin_c_mg')
        assert hasattr(micro, 'vitamin_d_iu')
        assert hasattr(micro, 'vitamin_e_mg')
        assert hasattr(micro, 'vitamin_k_ug')
        
        # B vitamins
        assert hasattr(micro, 'b1_thiamine_mg')
        assert hasattr(micro, 'b2_riboflavin_mg')
        assert hasattr(micro, 'b3_niacin_mg')
        assert hasattr(micro, 'b5_pantothenic_acid_mg')
        assert hasattr(micro, 'b6_pyridoxine_mg')
        assert hasattr(micro, 'b12_cobalamin_ug')
        assert hasattr(micro, 'folate_ug')
        
        # Minerals
        assert hasattr(micro, 'calcium_mg')
        assert hasattr(micro, 'iron_mg')
        assert hasattr(micro, 'magnesium_mg')
        assert hasattr(micro, 'zinc_mg')
        
        # Other
        assert hasattr(micro, 'fiber_g')

    # === No USDA Fields Tests ===

    def test_no_scale_factor_in_output(self, builder, scaled_nutrition):
        """Test that scale_factor (internal metadata) is not in output."""
        result = builder.build(scaled_nutrition)
        
        assert not hasattr(result, 'scale_factor')

    def test_no_actual_grams_in_output(self, builder, scaled_nutrition):
        """Test that actual_grams (internal metadata) is not in output."""
        result = builder.build(scaled_nutrition)
        
        assert not hasattr(result, 'actual_grams')

    def test_no_usda_ids_in_output(self, builder, scaled_nutrition):
        """Test that no USDA-specific fields leak into output."""
        result = builder.build(scaled_nutrition)
        
        # Check NutritionProfile has no USDA fields
        assert not hasattr(result, 'fdc_id')
        assert not hasattr(result, 'nutrient_id')
        assert not hasattr(result, 'raw_payload')
        
        # Check MicronutrientProfile has no USDA fields
        micro = result.micronutrients
        for field in fields(micro):
            assert not field.name.startswith('usda_')
            assert not field.name.startswith('fdc_')
            # Check for USDA ID patterns (not words containing "id" like "acid")
            assert not field.name.endswith('_id')
            assert 'nutrient_id' not in field.name

    # === Zero Default Tests ===

    def test_missing_micronutrients_default_to_zero(self, builder):
        """Test that unset micronutrients default to zero."""
        # Create scaled nutrition with minimal micronutrients
        scaled = ScaledNutrition(
            calories=100.0,
            protein_g=10.0,
            fat_g=5.0,
            carbs_g=20.0,
            micronutrients=MicronutrientProfile(),  # All defaults (0.0)
            scale_factor=1.0,
            actual_grams=100.0
        )
        
        result = builder.build(scaled)
        
        # All micronutrients should be 0.0
        micro = result.micronutrients
        assert micro.vitamin_a_ug == 0.0
        assert micro.vitamin_c_mg == 0.0
        assert micro.iron_mg == 0.0
        assert micro.calcium_mg == 0.0
        assert micro.fiber_g == 0.0
        assert micro.omega_3_g == 0.0

    def test_zero_macros_preserved(self, builder):
        """Test that zero macronutrient values are preserved."""
        scaled = ScaledNutrition(
            calories=0.0,
            protein_g=0.0,
            fat_g=0.0,
            carbs_g=0.0,
            micronutrients=MicronutrientProfile(),
            scale_factor=0.0,
            actual_grams=0.0
        )
        
        result = builder.build(scaled)
        
        assert result.calories == 0.0
        assert result.protein_g == 0.0
        assert result.fat_g == 0.0
        assert result.carbs_g == 0.0

    # === Numeric Type Tests ===

    def test_all_values_are_numeric(self, builder, scaled_nutrition):
        """Test that all values are numeric (float)."""
        result = builder.build(scaled_nutrition)
        
        # Macros
        assert isinstance(result.calories, (int, float))
        assert isinstance(result.protein_g, (int, float))
        assert isinstance(result.fat_g, (int, float))
        assert isinstance(result.carbs_g, (int, float))
        
        # Micros
        micro = result.micronutrients
        for field in fields(micro):
            value = getattr(micro, field.name)
            assert isinstance(value, (int, float)), f"{field.name} is not numeric"

    def test_no_none_values_in_micronutrients(self, builder, scaled_nutrition):
        """Test that no None values exist in micronutrients."""
        result = builder.build(scaled_nutrition)
        
        micro = result.micronutrients
        for field in fields(micro):
            value = getattr(micro, field.name)
            assert value is not None, f"{field.name} is None"

    # === Immutability Tests ===

    def test_output_is_independent_copy(self, builder, scaled_nutrition):
        """Test that output is independent from input (no shared references)."""
        result = builder.build(scaled_nutrition)
        
        # Modifying input should not affect output
        # (This tests that we're not sharing MicronutrientProfile reference)
        original_iron = result.micronutrients.iron_mg
        
        # Build again to ensure independence
        result2 = builder.build(scaled_nutrition)
        
        assert result.micronutrients.iron_mg == original_iron
        assert result2.micronutrients.iron_mg == original_iron

    # === Aggregation Safety Tests ===

    def test_profile_can_be_added(self, builder, scaled_nutrition):
        """Test that profiles can be safely aggregated (added)."""
        profile1 = builder.build(scaled_nutrition)
        profile2 = builder.build(scaled_nutrition)
        
        # Should be able to add values without errors
        total_calories = profile1.calories + profile2.calories
        total_protein = profile1.protein_g + profile2.protein_g
        total_iron = profile1.micronutrients.iron_mg + profile2.micronutrients.iron_mg
        
        assert total_calories == 660.0
        assert total_protein == 124.0
        assert total_iron == 1.48

    def test_profile_can_be_converted_to_dict(self, builder, scaled_nutrition):
        """Test that profile can be converted to dict (for serialization)."""
        result = builder.build(scaled_nutrition)
        
        # Should be convertible to dict via asdict
        profile_dict = asdict(result)
        
        assert 'calories' in profile_dict
        assert 'protein_g' in profile_dict
        assert 'micronutrients' in profile_dict
        assert isinstance(profile_dict['micronutrients'], dict)


class TestBuildNutritionProfileFunction:
    """Tests for the convenience build_nutrition_profile function."""

    def test_build_from_scaled(self):
        """Test convenience function with ScaledNutrition."""
        scaled = ScaledNutrition(
            calories=200.0,
            protein_g=20.0,
            fat_g=10.0,
            carbs_g=15.0,
            micronutrients=MicronutrientProfile(iron_mg=2.0),
            scale_factor=1.5,
            actual_grams=150.0
        )
        
        result = build_nutrition_profile(scaled)
        
        assert isinstance(result, NutritionProfile)
        assert result.calories == 200.0
        assert result.micronutrients.iron_mg == 2.0

    def test_build_from_mapped(self):
        """Test convenience function with MappedNutrition."""
        mapped = MappedNutrition(
            calories=100.0,
            protein_g=10.0,
            fat_g=5.0,
            carbs_g=20.0,
            micronutrients=MicronutrientProfile(calcium_mg=50.0)
        )
        
        result = build_nutrition_profile(mapped)
        
        assert isinstance(result, NutritionProfile)
        assert result.calories == 100.0
        assert result.micronutrients.calcium_mg == 50.0


class TestNutritionProfileSchemaConsistency:
    """Tests ensuring NutritionProfile matches expected schema."""

    @pytest.fixture
    def builder(self):
        """Create builder instance."""
        return NutritionProfileBuilder()

    def test_macro_field_names_match_schema(self, builder):
        """Test that macro field names match NutritionProfile schema."""
        scaled = ScaledNutrition(
            calories=100.0,
            protein_g=10.0,
            fat_g=5.0,
            carbs_g=20.0,
            micronutrients=MicronutrientProfile(),
            scale_factor=1.0,
            actual_grams=100.0
        )
        
        result = builder.build(scaled)
        
        # Field names must exactly match
        assert 'calories' in [f.name for f in fields(result)]
        assert 'protein_g' in [f.name for f in fields(result)]
        assert 'fat_g' in [f.name for f in fields(result)]
        assert 'carbs_g' in [f.name for f in fields(result)]

    def test_micro_field_names_match_schema(self, builder):
        """Test that micro field names match MicronutrientProfile schema."""
        scaled = ScaledNutrition(
            calories=100.0,
            protein_g=10.0,
            fat_g=5.0,
            carbs_g=20.0,
            micronutrients=MicronutrientProfile(),
            scale_factor=1.0,
            actual_grams=100.0
        )
        
        result = builder.build(scaled)
        micro = result.micronutrients
        
        # Verify expected field names
        expected_fields = [
            'vitamin_a_ug', 'vitamin_c_mg', 'vitamin_d_iu', 'vitamin_e_mg', 'vitamin_k_ug',
            'b1_thiamine_mg', 'b2_riboflavin_mg', 'b3_niacin_mg', 'b5_pantothenic_acid_mg',
            'b6_pyridoxine_mg', 'b12_cobalamin_ug', 'folate_ug',
            'calcium_mg', 'copper_mg', 'iron_mg', 'magnesium_mg', 'manganese_mg',
            'phosphorus_mg', 'potassium_mg', 'selenium_ug', 'sodium_mg', 'zinc_mg',
            'fiber_g', 'omega_3_g', 'omega_6_g'
        ]
        
        actual_fields = [f.name for f in fields(micro)]
        
        for expected in expected_fields:
            assert expected in actual_fields, f"Missing field: {expected}"
