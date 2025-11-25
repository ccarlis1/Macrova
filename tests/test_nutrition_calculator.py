"""Tests for nutrition calculator."""
import pytest
from tempfile import NamedTemporaryFile
import json

from src.nutrition.calculator import NutritionCalculator
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.models import Ingredient, Recipe, NutritionProfile
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

