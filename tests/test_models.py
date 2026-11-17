"""Tests for data layer models."""
import pytest
from dataclasses import dataclass, fields
from typing import List, Optional, Tuple, Dict

from src.data_layer.models import (
    Ingredient,
    NutritionProfile,
    Recipe,
    UserProfile,
    MicronutrientProfile,
)


class TestIngredient:
    """Tests for Ingredient model."""

    def test_ingredient_creation_basic(self):
        """Test basic ingredient creation."""
        ing = Ingredient(
            name="cream of rice",
            quantity=200.0,
            unit="g",
            is_to_taste=False,
            normalized_unit="g",
            normalized_quantity=200.0,
        )
        assert ing.name == "cream of rice"
        assert ing.quantity == 200.0
        assert ing.unit == "g"
        assert ing.is_to_taste is False
        assert ing.normalized_unit == "g"
        assert ing.normalized_quantity == 200.0

    def test_ingredient_to_taste(self):
        """Test ingredient marked as 'to taste'."""
        ing = Ingredient(
            name="salt",
            quantity=0.0,
            unit="to taste",
            is_to_taste=True,
            normalized_unit="to taste",
            normalized_quantity=0.0,
        )
        assert ing.is_to_taste is True
        assert ing.quantity == 0.0
        assert ing.unit == "to taste"

    def test_ingredient_imperial_conversion(self):
        """Test ingredient with imperial unit conversion."""
        ing = Ingredient(
            name="cheese",
            quantity=1.0,
            unit="oz",
            is_to_taste=False,
            normalized_unit="g",
            normalized_quantity=28.0,  # 1oz = 28g
        )
        assert ing.unit == "oz"
        assert ing.normalized_unit == "g"
        assert ing.normalized_quantity == 28.0


class TestNutritionProfile:
    """Tests for NutritionProfile model."""

    def test_nutrition_profile_creation(self):
        """Test basic nutrition profile creation."""
        profile = NutritionProfile(
            calories=860.0,
            protein_g=31.5,
            fat_g=6.0,
            carbs_g=167.0,
        )
        assert profile.calories == 860.0
        assert profile.protein_g == 31.5
        assert profile.fat_g == 6.0
        assert profile.carbs_g == 167.0

    def test_nutrition_profile_zero_values(self):
        """Test nutrition profile with zero values."""
        profile = NutritionProfile(
            calories=0.0,
            protein_g=0.0,
            fat_g=0.0,
            carbs_g=0.0,
        )
        assert profile.calories == 0.0
        assert profile.protein_g == 0.0


class TestRecipe:
    """Tests for Recipe model."""

    def test_recipe_creation(self):
        """Test basic recipe creation."""
        ingredients = [
            Ingredient(
                name="cream of rice",
                quantity=200.0,
                unit="g",
                is_to_taste=False,
                normalized_unit="g",
                normalized_quantity=200.0,
            ),
            Ingredient(
                name="whey protein powder",
                quantity=1.0,
                unit="scoop",
                is_to_taste=False,
                normalized_unit="scoop",
                normalized_quantity=1.0,
            ),
        ]
        recipe = Recipe(
            id="recipe_001",
            name="Preworkout Meal",
            ingredients=ingredients,
            cooking_time_minutes=5,
            instructions=[
                "Cook cream of rice according to package directions",
                "Mix in protein powder",
            ],
        )
        assert recipe.id == "recipe_001"
        assert recipe.name == "Preworkout Meal"
        assert len(recipe.ingredients) == 2
        assert recipe.cooking_time_minutes == 5
        assert len(recipe.instructions) == 2

    def test_recipe_with_to_taste_ingredients(self):
        """Test recipe with 'to taste' ingredients."""
        ingredients = [
            Ingredient(
                name="eggs",
                quantity=5.0,
                unit="large",
                is_to_taste=False,
                normalized_unit="large",
                normalized_quantity=5.0,
            ),
            Ingredient(
                name="salsa",
                quantity=1.0,
                unit="to taste",
                is_to_taste=True,
                normalized_unit="to taste",
                normalized_quantity=0.0,
            ),
        ]
        recipe = Recipe(
            id="recipe_002",
            name="Scramble",
            ingredients=ingredients,
            cooking_time_minutes=15,
            instructions=["Cook eggs", "Add salsa to taste"],
        )
        assert len(recipe.ingredients) == 2
        assert recipe.ingredients[1].is_to_taste is True


class TestUserProfile:
    """Tests for UserProfile model."""

    def test_user_profile_creation(self):
        """Test basic user profile creation."""
        profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=281.0,
            schedule={"07:00": 2, "12:00": 3, "18:00": 3},
            liked_foods=["salmon", "eggs", "rice"],
            disliked_foods=["brussels sprouts", "liver"],
            allergies=["shellfish", "peanuts"],
        )
        assert profile.daily_calories == 2400
        assert profile.daily_protein_g == 150.0
        assert profile.daily_fat_g == (50.0, 100.0)
        assert profile.daily_carbs_g == 281.0
        assert profile.schedule["07:00"] == 2
        assert "salmon" in profile.liked_foods
        assert "brussels sprouts" in profile.disliked_foods
        assert "shellfish" in profile.allergies
        assert profile.micronutrient_weekly_min_fraction == 1.0

    def test_user_profile_with_daily_micronutrient_targets(self):
        """Test user profile with daily micronutrient RDI targets."""
        daily_micro = {
            "vitamin_a_ug": 900.0,
            "vitamin_c_mg": 90.0,
            "calcium_mg": 1000.0,
            "iron_mg": 8.0,
        }
        profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=281.0,
            schedule={"07:00": 2},
            liked_foods=[],
            disliked_foods=[],
            allergies=[],
            daily_micronutrient_targets=daily_micro,
        )
        assert profile.daily_micronutrient_targets is not None
        assert profile.daily_micronutrient_targets["vitamin_a_ug"] == 900.0
        assert profile.daily_micronutrient_targets["calcium_mg"] == 1000.0

    def test_user_profile_daily_micronutrient_targets_defaults_to_none(self):
        """Test that daily_micronutrient_targets defaults to None."""
        profile = UserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(50.0, 100.0),
            daily_carbs_g=281.0,
            schedule={"07:00": 2},
            liked_foods=[],
            disliked_foods=[],
            allergies=[],
        )
        assert profile.daily_micronutrient_targets is None


class TestMicronutrientProfile:
    """Tests for MicronutrientProfile model."""

    def test_micronutrient_profile_creation_with_values(self):
        """Test creating a micronutrient profile with specific values."""
        micros = MicronutrientProfile(
            vitamin_a_ug=900.0,
            vitamin_c_mg=90.0,
            vitamin_d_iu=600.0,
            vitamin_e_mg=15.0,
            vitamin_k_ug=120.0,
            calcium_mg=1000.0,
            iron_mg=8.0,
            fiber_g=38.0,
            omega_3_g=1.6,
        )
        assert micros.vitamin_a_ug == 900.0
        assert micros.vitamin_c_mg == 90.0
        assert micros.vitamin_d_iu == 600.0
        assert micros.vitamin_e_mg == 15.0
        assert micros.vitamin_k_ug == 120.0
        assert micros.calcium_mg == 1000.0
        assert micros.iron_mg == 8.0
        assert micros.fiber_g == 38.0
        assert micros.omega_3_g == 1.6

    def test_micronutrient_profile_defaults_to_zero(self):
        """Test that all micronutrient fields default to 0.0."""
        micros = MicronutrientProfile()
        # All fields should default to 0.0
        assert micros.vitamin_a_ug == 0.0
        assert micros.vitamin_c_mg == 0.0
        assert micros.vitamin_d_iu == 0.0
        assert micros.vitamin_e_mg == 0.0
        assert micros.vitamin_k_ug == 0.0
        assert micros.b1_thiamine_mg == 0.0
        assert micros.b2_riboflavin_mg == 0.0
        assert micros.b3_niacin_mg == 0.0
        assert micros.b5_pantothenic_acid_mg == 0.0
        assert micros.b6_pyridoxine_mg == 0.0
        assert micros.b12_cobalamin_ug == 0.0
        assert micros.folate_ug == 0.0
        assert micros.calcium_mg == 0.0
        assert micros.copper_mg == 0.0
        assert micros.iron_mg == 0.0
        assert micros.magnesium_mg == 0.0
        assert micros.manganese_mg == 0.0
        assert micros.phosphorus_mg == 0.0
        assert micros.potassium_mg == 0.0
        assert micros.selenium_ug == 0.0
        assert micros.sodium_mg == 0.0
        assert micros.zinc_mg == 0.0
        assert micros.fiber_g == 0.0
        assert micros.omega_3_g == 0.0
        assert micros.omega_6_g == 0.0

    def test_micronutrient_profile_partial_values(self):
        """Test creating profile with only some micronutrients specified."""
        micros = MicronutrientProfile(
            vitamin_c_mg=90.0,
            iron_mg=18.0,
        )
        assert micros.vitamin_c_mg == 90.0
        assert micros.iron_mg == 18.0
        # Others should be 0.0
        assert micros.vitamin_a_ug == 0.0
        assert micros.calcium_mg == 0.0

    def test_micronutrient_profile_has_all_expected_fields(self):
        """Test that MicronutrientProfile has all required micronutrient fields."""
        micros = MicronutrientProfile()
        field_names = {f.name for f in fields(micros)}
        
        # Vitamins
        assert "vitamin_a_ug" in field_names
        assert "vitamin_c_mg" in field_names
        assert "vitamin_d_iu" in field_names
        assert "vitamin_e_mg" in field_names
        assert "vitamin_k_ug" in field_names
        assert "b1_thiamine_mg" in field_names
        assert "b2_riboflavin_mg" in field_names
        assert "b3_niacin_mg" in field_names
        assert "b5_pantothenic_acid_mg" in field_names
        assert "b6_pyridoxine_mg" in field_names
        assert "b12_cobalamin_ug" in field_names
        assert "folate_ug" in field_names
        
        # Minerals
        assert "calcium_mg" in field_names
        assert "copper_mg" in field_names
        assert "iron_mg" in field_names
        assert "magnesium_mg" in field_names
        assert "manganese_mg" in field_names
        assert "phosphorus_mg" in field_names
        assert "potassium_mg" in field_names
        assert "selenium_ug" in field_names
        assert "sodium_mg" in field_names
        assert "zinc_mg" in field_names
        
        # Other
        assert "fiber_g" in field_names
        assert "omega_3_g" in field_names
        assert "omega_6_g" in field_names


class TestNutritionProfileWithMicronutrients:
    """Tests for NutritionProfile with optional micronutrients."""

    def test_nutrition_profile_with_micronutrients(self):
        """Test NutritionProfile can include micronutrients."""
        micros = MicronutrientProfile(
            vitamin_c_mg=45.0,
            iron_mg=4.0,
            fiber_g=8.0,
        )
        profile = NutritionProfile(
            calories=500.0,
            protein_g=30.0,
            fat_g=20.0,
            carbs_g=50.0,
            micronutrients=micros,
        )
        assert profile.calories == 500.0
        assert profile.micronutrients is not None
        assert profile.micronutrients.vitamin_c_mg == 45.0
        assert profile.micronutrients.iron_mg == 4.0

    def test_nutrition_profile_micronutrients_defaults_to_none(self):
        """Test that micronutrients default to None for backward compatibility."""
        profile = NutritionProfile(
            calories=500.0,
            protein_g=30.0,
            fat_g=20.0,
            carbs_g=50.0,
        )
        assert profile.micronutrients is None

    def test_nutrition_profile_backward_compatible(self):
        """Test existing code creating NutritionProfile still works."""
        # This mirrors how existing tests create NutritionProfile
        profile = NutritionProfile(
            calories=860.0,
            protein_g=31.5,
            fat_g=6.0,
            carbs_g=167.0,
        )
        assert profile.calories == 860.0
        assert profile.protein_g == 31.5
        assert profile.fat_g == 6.0
        assert profile.carbs_g == 167.0
