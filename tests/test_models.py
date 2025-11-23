"""Tests for data layer models."""
import pytest
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

from src.data_layer.models import (
    Ingredient,
    NutritionProfile,
    Recipe,
    Meal,
    DailyMealPlan,
    UserProfile,
    NutritionGoals,
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


class TestMeal:
    """Tests for Meal model."""

    def test_meal_creation(self):
        """Test basic meal creation."""
        recipe = Recipe(
            id="recipe_001",
            name="Preworkout Meal",
            ingredients=[],
            cooking_time_minutes=5,
            instructions=[],
        )
        nutrition = NutritionProfile(
            calories=860.0,
            protein_g=31.5,
            fat_g=6.0,
            carbs_g=167.0,
        )
        meal = Meal(
            recipe=recipe,
            nutrition=nutrition,
            meal_type="breakfast",
            scheduled_time="07:00",
            busyness_level=2,
        )
        assert meal.recipe.id == "recipe_001"
        assert meal.nutrition.calories == 860.0
        assert meal.meal_type == "breakfast"
        assert meal.scheduled_time == "07:00"
        assert meal.busyness_level == 2


class TestNutritionGoals:
    """Tests for NutritionGoals model."""

    def test_nutrition_goals_creation(self):
        """Test basic nutrition goals creation."""
        goals = NutritionGoals(
            calories=2400,
            protein_g=150.0,
            fat_g_min=50.0,
            fat_g_max=100.0,
            carbs_g=281.0,
        )
        assert goals.calories == 2400
        assert goals.protein_g == 150.0
        assert goals.fat_g_min == 50.0
        assert goals.fat_g_max == 100.0
        assert goals.carbs_g == 281.0


class TestDailyMealPlan:
    """Tests for DailyMealPlan model."""

    def test_daily_meal_plan_creation(self):
        """Test basic daily meal plan creation."""
        recipe = Recipe(
            id="recipe_001",
            name="Preworkout Meal",
            ingredients=[],
            cooking_time_minutes=5,
            instructions=[],
        )
        nutrition = NutritionProfile(
            calories=860.0,
            protein_g=31.5,
            fat_g=6.0,
            carbs_g=167.0,
        )
        meal = Meal(
            recipe=recipe,
            nutrition=nutrition,
            meal_type="breakfast",
            scheduled_time="07:00",
            busyness_level=2,
        )
        goals = NutritionGoals(
            calories=2400,
            protein_g=150.0,
            fat_g_min=50.0,
            fat_g_max=100.0,
            carbs_g=281.0,
        )
        total_nutrition = NutritionProfile(
            calories=860.0,
            protein_g=31.5,
            fat_g=6.0,
            carbs_g=167.0,
        )
        plan = DailyMealPlan(
            date="2024-01-15",
            meals=[meal],
            total_nutrition=total_nutrition,
            goals=goals,
            meets_goals=False,
        )
        assert plan.date == "2024-01-15"
        assert len(plan.meals) == 1
        assert plan.meets_goals is False


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

