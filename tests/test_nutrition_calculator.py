"""Tests for nutrition calculator."""
import pytest
from tempfile import NamedTemporaryFile
import json

from src.nutrition.calculator import NutritionCalculator
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.models import Ingredient, Recipe, NutritionProfile, MicronutrientProfile
from src.data_layer.exceptions import IngredientNotFoundError


class TestNutritionCalculator:
    """Tests for NutritionCalculator."""

    @pytest.fixture
    def nutrition_db(self):
        """Create a test nutrition database."""
        nutrition_data = {
            "ingredients": [
                {
                    "name": "cream of rice",
                    "per_100g": {
                        "calories": 370,
                        "protein_g": 7.5,
                        "fat_g": 0.5,
                        "carbs_g": 82.0,
                    },
                    "aliases": ["cream of rice"],
                },
                {
                    "name": "whey protein powder",
                    "per_scoop": {
                        "calories": 120,
                        "protein_g": 24.0,
                        "fat_g": 1.0,
                        "carbs_g": 3.0,
                    },
                    "scoop_size_g": 30,
                    "aliases": ["protein powder", "whey"],
                },
                {
                    "name": "egg",
                    "per_large": {
                        "calories": 72,
                        "protein_g": 6.3,
                        "fat_g": 4.8,
                        "carbs_g": 0.4,
                    },
                    "large_size_g": 50,
                    "aliases": ["eggs"],
                },
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(nutrition_data, f)
            temp_path = f.name

        db = NutritionDB(temp_path)
        yield db
        import os
        os.unlink(temp_path)

    @pytest.fixture
    def calculator(self, nutrition_db):
        """Create a NutritionCalculator instance."""
        return NutritionCalculator(nutrition_db)

    @pytest.fixture
    def nutrition_db_with_micros(self):
        """Create a test nutrition database with micronutrient data."""
        nutrition_data = {
            "ingredients": [
                {
                    "name": "salmon",
                    "per_100g": {
                        "calories": 208,
                        "protein_g": 20.0,
                        "fat_g": 12.0,
                        "carbs_g": 0.0,
                        # Micronutrients
                        "vitamin_d_iu": 526.0,
                        "vitamin_b12_cobalamin_ug": 2.8,
                        "omega_3_g": 2.0,
                        "selenium_ug": 36.5,
                        "phosphorus_mg": 252.0,
                    },
                    "aliases": ["atlantic salmon"],
                },
                {
                    "name": "spinach",
                    "per_100g": {
                        "calories": 23,
                        "protein_g": 2.9,
                        "fat_g": 0.4,
                        "carbs_g": 3.6,
                        # Micronutrients
                        "vitamin_a_ug": 469.0,
                        "vitamin_c_mg": 28.1,
                        "vitamin_k_ug": 482.9,
                        "folate_ug": 194.0,
                        "iron_mg": 2.7,
                        "magnesium_mg": 79.0,
                        "fiber_g": 2.2,
                    },
                    "aliases": ["raw spinach", "fresh spinach"],
                },
                {
                    "name": "egg",
                    "per_large": {
                        "calories": 72,
                        "protein_g": 6.3,
                        "fat_g": 4.8,
                        "carbs_g": 0.4,
                        # Micronutrients
                        "vitamin_a_ug": 80.0,
                        "vitamin_d_iu": 41.0,
                        "vitamin_b12_cobalamin_ug": 0.6,
                        "selenium_ug": 15.4,
                        "phosphorus_mg": 99.0,
                    },
                    "large_size_g": 50,
                    "aliases": ["eggs", "large egg"],
                },
                {
                    # Ingredient with no micronutrient data (macros only)
                    "name": "cream of rice",
                    "per_100g": {
                        "calories": 370,
                        "protein_g": 7.5,
                        "fat_g": 0.5,
                        "carbs_g": 82.0,
                    },
                    "aliases": ["rice cereal"],
                },
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(nutrition_data, f)
            temp_path = f.name

        db = NutritionDB(temp_path)
        yield db
        import os
        os.unlink(temp_path)

    @pytest.fixture
    def calculator_with_micros(self, nutrition_db_with_micros):
        """Create a NutritionCalculator instance with micronutrient data."""
        return NutritionCalculator(nutrition_db_with_micros)

    def test_calculate_ingredient_nutrition_grams(self, calculator):
        """Test calculating nutrition for ingredient in grams."""
        ingredient = Ingredient(
            name="cream of rice",
            quantity=200.0,
            unit="g",
            is_to_taste=False,
        )
        nutrition = calculator.calculate_ingredient_nutrition(ingredient)

        # 200g × (370 cal/100g) = 740 calories
        assert abs(nutrition.calories - 740.0) < 0.01
        assert abs(nutrition.protein_g - 15.0) < 0.01
        assert abs(nutrition.fat_g - 1.0) < 0.01
        assert abs(nutrition.carbs_g - 164.0) < 0.01

    def test_calculate_ingredient_nutrition_scoop(self, calculator):
        """Test calculating nutrition for ingredient in scoops."""
        ingredient = Ingredient(
            name="whey protein powder",
            quantity=1.0,
            unit="scoop",
            is_to_taste=False,
        )
        nutrition = calculator.calculate_ingredient_nutrition(ingredient)

        # 1 scoop × (120 cal/scoop) = 120 calories
        assert abs(nutrition.calories - 120.0) < 0.01
        assert abs(nutrition.protein_g - 24.0) < 0.01

    def test_calculate_ingredient_nutrition_large(self, calculator):
        """Test calculating nutrition for ingredient in 'large' units."""
        ingredient = Ingredient(
            name="egg",
            quantity=2.0,
            unit="large",
            is_to_taste=False,
        )
        nutrition = calculator.calculate_ingredient_nutrition(ingredient)

        # 2 large × (72 cal/large) = 144 calories
        assert abs(nutrition.calories - 144.0) < 0.01
        assert abs(nutrition.protein_g - 12.6) < 0.01

    def test_calculate_ingredient_to_taste_error(self, calculator):
        """Test that 'to taste' ingredients raise ValueError."""
        ingredient = Ingredient(
            name="salt",
            quantity=0.0,
            unit="to taste",
            is_to_taste=True,
        )
        with pytest.raises(ValueError, match="to taste"):
            calculator.calculate_ingredient_nutrition(ingredient)

    def test_calculate_ingredient_not_found(self, calculator):
        """Test that missing ingredients raise IngredientNotFoundError."""
        ingredient = Ingredient(
            name="unknown_ingredient",
            quantity=100.0,
            unit="g",
            is_to_taste=False,
        )
        with pytest.raises(IngredientNotFoundError):
            calculator.calculate_ingredient_nutrition(ingredient)

    def test_calculate_recipe_nutrition(self, calculator):
        """Test calculating nutrition for a recipe."""
        ingredients = [
            Ingredient(
                name="cream of rice",
                quantity=200.0,
                unit="g",
                is_to_taste=False,
            ),
            Ingredient(
                name="whey protein powder",
                quantity=1.0,
                unit="scoop",
                is_to_taste=False,
            ),
            Ingredient(
                name="salsa",
                quantity=1.0,
                unit="to taste",
                is_to_taste=True,
            ),
        ]
        recipe = Recipe(
            id="recipe_001",
            name="Test Recipe",
            ingredients=ingredients,
            cooking_time_minutes=5,
            instructions=[],
        )

        nutrition = calculator.calculate_recipe_nutrition(recipe)

        # Should sum cream of rice (740 cal) + protein (120 cal) = 860 cal
        # Salsa should be excluded
        assert abs(nutrition.calories - 860.0) < 0.01
        assert abs(nutrition.protein_g - 39.0) < 0.01  # 15 + 24

    def test_calculate_recipe_all_to_taste(self, calculator):
        """Test recipe with only 'to taste' ingredients returns zero nutrition."""
        ingredients = [
            Ingredient(
                name="salt",
                quantity=0.0,
                unit="to taste",
                is_to_taste=True,
            ),
            Ingredient(
                name="pepper",
                quantity=0.0,
                unit="to taste",
                is_to_taste=True,
            ),
        ]
        recipe = Recipe(
            id="recipe_002",
            name="All To Taste",
            ingredients=ingredients,
            cooking_time_minutes=1,
            instructions=[],
        )

        nutrition = calculator.calculate_recipe_nutrition(recipe)
        assert nutrition.calories == 0.0
        assert nutrition.protein_g == 0.0
        assert nutrition.fat_g == 0.0
        assert nutrition.carbs_g == 0.0

    def test_calculate_recipe_missing_ingredient(self, calculator):
        """Test recipe with missing ingredient - should skip and continue."""
        ingredients = [
            Ingredient(
                name="cream of rice",
                quantity=200.0,
                unit="g",
                is_to_taste=False,
            ),
            Ingredient(
                name="unknown_ingredient",
                quantity=100.0,
                unit="g",
                is_to_taste=False,
            ),
        ]
        recipe = Recipe(
            id="recipe_003",
            name="With Missing",
            ingredients=ingredients,
            cooking_time_minutes=5,
            instructions=[],
        )

        nutrition = calculator.calculate_recipe_nutrition(recipe)
        # Should only have cream of rice nutrition (740 cal)
        assert abs(nutrition.calories - 740.0) < 0.01

    def test_calculate_recipe_zero_quantity(self, calculator):
        """Test recipe with zero quantity ingredient."""
        ingredients = [
            Ingredient(
                name="cream of rice",
                quantity=0.0,
                unit="g",
                is_to_taste=False,
            ),
        ]
        recipe = Recipe(
            id="recipe_004",
            name="Zero Quantity",
            ingredients=ingredients,
            cooking_time_minutes=5,
            instructions=[],
        )

        nutrition = calculator.calculate_recipe_nutrition(recipe)
        assert nutrition.calories == 0.0


class TestMicronutrientCalculation:
    """Tests for micronutrient calculation in NutritionCalculator."""

    @pytest.fixture
    def nutrition_db_with_micros(self):
        """Create a test nutrition database with micronutrient data."""
        nutrition_data = {
            "ingredients": [
                {
                    "name": "salmon",
                    "per_100g": {
                        "calories": 208,
                        "protein_g": 20.0,
                        "fat_g": 12.0,
                        "carbs_g": 0.0,
                        # Micronutrients
                        "vitamin_d_iu": 526.0,
                        "b12_cobalamin_ug": 2.8,
                        "omega_3_g": 2.0,
                        "selenium_ug": 36.5,
                        "phosphorus_mg": 252.0,
                    },
                    "aliases": ["atlantic salmon"],
                },
                {
                    "name": "spinach",
                    "per_100g": {
                        "calories": 23,
                        "protein_g": 2.9,
                        "fat_g": 0.4,
                        "carbs_g": 3.6,
                        # Micronutrients
                        "vitamin_a_ug": 469.0,
                        "vitamin_c_mg": 28.1,
                        "vitamin_k_ug": 482.9,
                        "folate_ug": 194.0,
                        "iron_mg": 2.7,
                        "magnesium_mg": 79.0,
                        "fiber_g": 2.2,
                    },
                    "aliases": ["raw spinach", "fresh spinach"],
                },
                {
                    "name": "egg",
                    "per_large": {
                        "calories": 72,
                        "protein_g": 6.3,
                        "fat_g": 4.8,
                        "carbs_g": 0.4,
                        # Micronutrients
                        "vitamin_a_ug": 80.0,
                        "vitamin_d_iu": 41.0,
                        "b12_cobalamin_ug": 0.6,
                        "selenium_ug": 15.4,
                        "phosphorus_mg": 99.0,
                    },
                    "large_size_g": 50,
                    "aliases": ["eggs", "large egg"],
                },
                {
                    # Ingredient with no micronutrient data (macros only)
                    "name": "cream of rice",
                    "per_100g": {
                        "calories": 370,
                        "protein_g": 7.5,
                        "fat_g": 0.5,
                        "carbs_g": 82.0,
                    },
                    "aliases": ["rice cereal"],
                },
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(nutrition_data, f)
            temp_path = f.name

        db = NutritionDB(temp_path)
        yield db
        import os
        os.unlink(temp_path)

    @pytest.fixture
    def calculator_with_micros(self, nutrition_db_with_micros):
        """Create a NutritionCalculator instance with micronutrient data."""
        return NutritionCalculator(nutrition_db_with_micros)

    def test_ingredient_micronutrients_per_100g(self, calculator_with_micros):
        """Test micronutrient calculation for ingredient in grams."""
        ingredient = Ingredient(
            name="salmon",
            quantity=200.0,  # 200g
            unit="g",
            is_to_taste=False,
        )
        nutrition = calculator_with_micros.calculate_ingredient_nutrition(ingredient)

        # Verify macros still work
        assert abs(nutrition.calories - 416.0) < 0.01  # 208 * 2
        assert abs(nutrition.protein_g - 40.0) < 0.01  # 20 * 2

        # Verify micronutrients are calculated
        assert nutrition.micronutrients is not None
        # 200g × (526 IU/100g) = 1052 IU
        assert abs(nutrition.micronutrients.vitamin_d_iu - 1052.0) < 0.01
        # 200g × (2.8 ug/100g) = 5.6 ug
        assert abs(nutrition.micronutrients.b12_cobalamin_ug - 5.6) < 0.01
        # 200g × (2.0 g/100g) = 4.0 g
        assert abs(nutrition.micronutrients.omega_3_g - 4.0) < 0.01
        # 200g × (36.5 ug/100g) = 73.0 ug
        assert abs(nutrition.micronutrients.selenium_ug - 73.0) < 0.01
        # 200g × (252 mg/100g) = 504 mg
        assert abs(nutrition.micronutrients.phosphorus_mg - 504.0) < 0.01

    def test_ingredient_micronutrients_per_large(self, calculator_with_micros):
        """Test micronutrient calculation for ingredient in 'large' units."""
        ingredient = Ingredient(
            name="egg",
            quantity=3.0,  # 3 large eggs
            unit="large",
            is_to_taste=False,
        )
        nutrition = calculator_with_micros.calculate_ingredient_nutrition(ingredient)

        # Verify macros
        assert abs(nutrition.calories - 216.0) < 0.01  # 72 * 3

        # Verify micronutrients
        assert nutrition.micronutrients is not None
        # 3 × 80 ug = 240 ug
        assert abs(nutrition.micronutrients.vitamin_a_ug - 240.0) < 0.01
        # 3 × 41 IU = 123 IU
        assert abs(nutrition.micronutrients.vitamin_d_iu - 123.0) < 0.01
        # 3 × 0.6 ug = 1.8 ug
        assert abs(nutrition.micronutrients.b12_cobalamin_ug - 1.8) < 0.01
        # 3 × 15.4 ug = 46.2 ug
        assert abs(nutrition.micronutrients.selenium_ug - 46.2) < 0.01

    def test_ingredient_without_micronutrients_returns_zeros(self, calculator_with_micros):
        """Test that ingredients without micronutrient data return zeros."""
        ingredient = Ingredient(
            name="cream of rice",
            quantity=100.0,
            unit="g",
            is_to_taste=False,
        )
        nutrition = calculator_with_micros.calculate_ingredient_nutrition(ingredient)

        # Verify macros work
        assert abs(nutrition.calories - 370.0) < 0.01

        # Micronutrients should exist but be all zeros
        assert nutrition.micronutrients is not None
        assert nutrition.micronutrients.vitamin_a_ug == 0.0
        assert nutrition.micronutrients.vitamin_c_mg == 0.0
        assert nutrition.micronutrients.iron_mg == 0.0
        assert nutrition.micronutrients.fiber_g == 0.0

    def test_recipe_micronutrients_aggregation(self, calculator_with_micros):
        """Test micronutrient aggregation across multiple ingredients."""
        ingredients = [
            Ingredient(
                name="salmon",
                quantity=150.0,  # 150g
                unit="g",
                is_to_taste=False,
            ),
            Ingredient(
                name="spinach",
                quantity=100.0,  # 100g
                unit="g",
                is_to_taste=False,
            ),
        ]
        recipe = Recipe(
            id="recipe_salmon_spinach",
            name="Salmon with Spinach",
            ingredients=ingredients,
            cooking_time_minutes=20,
            instructions=["Cook salmon", "Add spinach"],
        )

        nutrition = calculator_with_micros.calculate_recipe_nutrition(recipe)

        # Verify macro aggregation
        # Salmon: 208 * 1.5 = 312, Spinach: 23 * 1 = 23, Total: 335
        assert abs(nutrition.calories - 335.0) < 0.01

        # Verify micronutrient aggregation
        assert nutrition.micronutrients is not None

        # Vitamin D: salmon only (150g × 526/100 = 789)
        assert abs(nutrition.micronutrients.vitamin_d_iu - 789.0) < 0.01

        # Vitamin A: spinach only (100g × 469/100 = 469)
        assert abs(nutrition.micronutrients.vitamin_a_ug - 469.0) < 0.01

        # Vitamin C: spinach only (100g × 28.1/100 = 28.1)
        assert abs(nutrition.micronutrients.vitamin_c_mg - 28.1) < 0.01

        # Omega-3: salmon only (150g × 2.0/100 = 3.0)
        assert abs(nutrition.micronutrients.omega_3_g - 3.0) < 0.01

        # Iron: spinach only (100g × 2.7/100 = 2.7)
        assert abs(nutrition.micronutrients.iron_mg - 2.7) < 0.01

        # Fiber: spinach only (100g × 2.2/100 = 2.2)
        assert abs(nutrition.micronutrients.fiber_g - 2.2) < 0.01

    def test_recipe_micronutrients_with_mixed_units(self, calculator_with_micros):
        """Test micronutrient aggregation with different unit types."""
        ingredients = [
            Ingredient(
                name="egg",
                quantity=2.0,  # 2 large eggs (per_large)
                unit="large",
                is_to_taste=False,
            ),
            Ingredient(
                name="spinach",
                quantity=50.0,  # 50g (per_100g)
                unit="g",
                is_to_taste=False,
            ),
        ]
        recipe = Recipe(
            id="recipe_egg_spinach",
            name="Egg and Spinach",
            ingredients=ingredients,
            cooking_time_minutes=10,
            instructions=["Scramble eggs with spinach"],
        )

        nutrition = calculator_with_micros.calculate_recipe_nutrition(recipe)

        # Verify micronutrients from both unit types aggregate correctly
        assert nutrition.micronutrients is not None

        # Vitamin A: egg (2 × 80 = 160) + spinach (50 × 469/100 = 234.5) = 394.5
        assert abs(nutrition.micronutrients.vitamin_a_ug - 394.5) < 0.01

        # Vitamin D: egg only (2 × 41 = 82)
        assert abs(nutrition.micronutrients.vitamin_d_iu - 82.0) < 0.01

        # Vitamin K: spinach only (50 × 482.9/100 = 241.45)
        assert abs(nutrition.micronutrients.vitamin_k_ug - 241.45) < 0.01

    def test_recipe_to_taste_contributes_zero_micronutrients(self, calculator_with_micros):
        """Test that 'to taste' ingredients contribute zero micronutrients."""
        ingredients = [
            Ingredient(
                name="spinach",
                quantity=100.0,
                unit="g",
                is_to_taste=False,
            ),
            Ingredient(
                name="salt",
                quantity=0.0,
                unit="to taste",
                is_to_taste=True,  # Should be excluded
            ),
        ]
        recipe = Recipe(
            id="recipe_spinach_salted",
            name="Salted Spinach",
            ingredients=ingredients,
            cooking_time_minutes=5,
            instructions=["Saute spinach", "Add salt to taste"],
        )

        nutrition = calculator_with_micros.calculate_recipe_nutrition(recipe)

        # Should only have spinach micronutrients
        assert nutrition.micronutrients is not None
        assert abs(nutrition.micronutrients.vitamin_a_ug - 469.0) < 0.01
        assert abs(nutrition.micronutrients.iron_mg - 2.7) < 0.01

    def test_recipe_all_to_taste_zero_micronutrients(self, calculator_with_micros):
        """Test recipe with only 'to taste' ingredients has zero micronutrients."""
        ingredients = [
            Ingredient(
                name="salt",
                quantity=0.0,
                unit="to taste",
                is_to_taste=True,
            ),
            Ingredient(
                name="pepper",
                quantity=0.0,
                unit="to taste",
                is_to_taste=True,
            ),
        ]
        recipe = Recipe(
            id="recipe_seasonings",
            name="Just Seasonings",
            ingredients=ingredients,
            cooking_time_minutes=0,
            instructions=[],
        )

        nutrition = calculator_with_micros.calculate_recipe_nutrition(recipe)

        # Should have micronutrients object with all zeros
        assert nutrition.micronutrients is not None
        assert nutrition.micronutrients.vitamin_a_ug == 0.0
        assert nutrition.micronutrients.vitamin_c_mg == 0.0
        assert nutrition.micronutrients.iron_mg == 0.0
        assert nutrition.micronutrients.fiber_g == 0.0
        assert nutrition.micronutrients.omega_3_g == 0.0

    def test_micronutrients_backward_compatible_with_macros_only_db(self, calculator):
        """Test that calculator works with legacy DB that has no micronutrients."""
        # Using the original fixture without micronutrient data
        ingredient = Ingredient(
            name="cream of rice",
            quantity=100.0,
            unit="g",
            is_to_taste=False,
        )
        nutrition = calculator.calculate_ingredient_nutrition(ingredient)

        # Macros should work
        assert abs(nutrition.calories - 370.0) < 0.01

        # Micronutrients should exist but be zeros
        assert nutrition.micronutrients is not None
        assert nutrition.micronutrients.vitamin_a_ug == 0.0

    @pytest.fixture
    def calculator(self):
        """Create calculator with legacy DB (no micronutrients)."""
        nutrition_data = {
            "ingredients": [
                {
                    "name": "cream of rice",
                    "per_100g": {
                        "calories": 370,
                        "protein_g": 7.5,
                        "fat_g": 0.5,
                        "carbs_g": 82.0,
                    },
                    "aliases": ["cream of rice"],
                },
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(nutrition_data, f)
            temp_path = f.name

        db = NutritionDB(temp_path)
        calc = NutritionCalculator(db)
        yield calc
        import os
        os.unlink(temp_path)

