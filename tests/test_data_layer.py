"""Tests for data layer components."""
import pytest
import json
import yaml
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.data_layer.models import (
    Ingredient,
    Recipe,
    NutritionProfile,
    UserProfile,
    NutritionGoals,
)
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.ingredient_db import IngredientDB
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.user_profile import UserProfileLoader


class TestRecipeDB:
    """Tests for RecipeDB."""

    def test_load_recipes_from_json(self):
        """Test loading recipes from JSON file."""
        recipe_data = {
            "recipes": [
                {
                    "id": "recipe_001",
                    "name": "Preworkout Meal",
                    "ingredients": [
                        {"quantity": 200, "unit": "g", "name": "cream of rice"},
                        {"quantity": 1, "unit": "scoop", "name": "whey protein powder"},
                    ],
                    "cooking_time_minutes": 5,
                    "instructions": [
                        "Cook cream of rice according to package directions",
                        "Mix in protein powder",
                    ],
                }
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(recipe_data, f)
            temp_path = f.name

        try:
            db = RecipeDB(temp_path)
            recipes = db.get_all_recipes()
            assert len(recipes) == 1
            assert recipes[0].id == "recipe_001"
            assert recipes[0].name == "Preworkout Meal"
            assert len(recipes[0].ingredients) == 2
            assert recipes[0].cooking_time_minutes == 5
        finally:
            Path(temp_path).unlink()

    def test_load_recipe_with_to_taste_ingredients(self):
        """Test loading recipe with 'to taste' ingredients."""
        recipe_data = {
            "recipes": [
                {
                    "id": "recipe_002",
                    "name": "Scramble",
                    "ingredients": [
                        {"quantity": 5, "unit": "large", "name": "eggs"},
                        {"quantity": 1, "unit": "to taste", "name": "salsa"},
                    ],
                    "cooking_time_minutes": 15,
                    "instructions": ["Cook eggs", "Add salsa to taste"],
                }
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(recipe_data, f)
            temp_path = f.name

        try:
            db = RecipeDB(temp_path)
            recipes = db.get_all_recipes()
            assert len(recipes) == 1
            assert len(recipes[0].ingredients) == 2
            # Check that "to taste" ingredient is marked correctly
            salsa_ing = next(
                (ing for ing in recipes[0].ingredients if ing.name == "salsa"), None
            )
            assert salsa_ing is not None
            assert salsa_ing.unit == "to taste"
        finally:
            Path(temp_path).unlink()

    def test_get_recipe_by_id(self):
        """Test getting a recipe by ID."""
        recipe_data = {
            "recipes": [
                {
                    "id": "recipe_001",
                    "name": "Recipe 1",
                    "ingredients": [],
                    "cooking_time_minutes": 5,
                    "instructions": [],
                },
                {
                    "id": "recipe_002",
                    "name": "Recipe 2",
                    "ingredients": [],
                    "cooking_time_minutes": 10,
                    "instructions": [],
                },
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(recipe_data, f)
            temp_path = f.name

        try:
            db = RecipeDB(temp_path)
            recipe = db.get_recipe_by_id("recipe_002")
            assert recipe is not None
            assert recipe.id == "recipe_002"
            assert recipe.name == "Recipe 2"
        finally:
            Path(temp_path).unlink()


class TestIngredientDB:
    """Tests for IngredientDB."""

    def test_load_ingredients_from_json(self):
        """Test loading ingredients from JSON file."""
        ingredient_data = {
            "ingredients": [
                {
                    "name": "cream of rice",
                    "per_100g": {
                        "calories": 370,
                        "protein_g": 7.5,
                        "fat_g": 0.5,
                        "carbs_g": 82.0,
                    },
                    "aliases": ["cream of rice", "rice cereal"],
                }
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(ingredient_data, f)
            temp_path = f.name

        try:
            db = IngredientDB(temp_path)
            ingredients = db.get_all_ingredients()
            assert len(ingredients) == 1
            assert ingredients[0]["name"] == "cream of rice"
            assert "per_100g" in ingredients[0]
            assert "aliases" in ingredients[0]
        finally:
            Path(temp_path).unlink()


class TestNutritionDB:
    """Tests for NutritionDB."""

    def test_load_nutrition_from_json(self):
        """Test loading nutrition data from JSON file."""
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
                    "aliases": ["cream of rice", "rice cereal"],
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
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(nutrition_data, f)
            temp_path = f.name

        try:
            db = NutritionDB(temp_path)
            nutrition = db.get_nutrition("cream of rice", "per_100g")
            assert nutrition is not None
            assert nutrition["calories"] == 370
            assert nutrition["protein_g"] == 7.5

            # Test with alias
            nutrition2 = db.get_nutrition("rice cereal", "per_100g")
            assert nutrition2 is not None
            assert nutrition2["calories"] == 370
        finally:
            Path(temp_path).unlink()

    def test_get_nutrition_by_alias(self):
        """Test getting nutrition data using ingredient alias."""
        nutrition_data = {
            "ingredients": [
                {
                    "name": "eggs",
                    "per_large": {
                        "calories": 72,
                        "protein_g": 6.3,
                        "fat_g": 4.8,
                        "carbs_g": 0.4,
                    },
                    "large_size_g": 50,
                    "aliases": ["egg", "eggs", "large egg"],
                }
            ]
        }
        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(nutrition_data, f)
            temp_path = f.name

        try:
            db = NutritionDB(temp_path)
            # Should find by alias
            nutrition = db.get_nutrition("egg", "per_large")
            assert nutrition is not None
            assert nutrition["calories"] == 72
        finally:
            Path(temp_path).unlink()


class TestUserProfileLoader:
    """Tests for UserProfileLoader."""

    def test_load_user_profile_from_yaml(self):
        """Test loading user profile from YAML file."""
        profile_data = {
            "nutrition_goals": {
                "daily_calories": 2400,
                "daily_protein_g": 150,
                "daily_fat_g": {"min": 50, "max": 100},
            },
            "schedule": {"07:00": 2, "12:00": 3, "18:00": 3},
            "preferences": {
                "liked_foods": ["salmon", "eggs"],
                "disliked_foods": ["brussels sprouts"],
                "allergies": ["shellfish"],
            },
        }
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(profile_data, f)
            temp_path = f.name

        try:
            loader = UserProfileLoader(temp_path)
            profile = loader.load()
            assert profile.daily_calories == 2400
            assert profile.daily_protein_g == 150.0
            assert profile.daily_fat_g == (50.0, 100.0)
            assert profile.schedule["07:00"] == 2
            assert "salmon" in profile.liked_foods
            assert "brussels sprouts" in profile.disliked_foods
            assert "shellfish" in profile.allergies
        finally:
            Path(temp_path).unlink()

    def test_calculate_carbs_from_remaining_calories(self):
        """Test that carbs are calculated from remaining calories."""
        profile_data = {
            "nutrition_goals": {
                "daily_calories": 2400,
                "daily_protein_g": 150,
                "daily_fat_g": {"min": 50, "max": 100},
            },
            "schedule": {"07:00": 2},
            "preferences": {
                "liked_foods": [],
                "disliked_foods": [],
                "allergies": [],
            },
        }
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(profile_data, f)
            temp_path = f.name

        try:
            loader = UserProfileLoader(temp_path)
            profile = loader.load()
            # Carbs should be calculated: (2400 - 150*4 - 75*9) / 4 = 281.25
            # Using median fat (75g) for calculation
            expected_carbs = (2400 - 150 * 4 - 75 * 9) / 4
            assert abs(profile.daily_carbs_g - expected_carbs) < 0.1
        finally:
            Path(temp_path).unlink()

