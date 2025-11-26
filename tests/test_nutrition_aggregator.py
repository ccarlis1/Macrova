"""Tests for nutrition aggregator."""
import pytest

from src.nutrition.aggregator import NutritionAggregator
from src.data_layer.models import Meal, Recipe, NutritionProfile, Ingredient


class TestNutritionAggregator:
    """Tests for NutritionAggregator."""

    def test_aggregate_meals(self):
        """Test aggregating nutrition from multiple meals."""
        meal1 = Meal(
            recipe=Recipe(
                id="r1",
                name="Meal 1",
                ingredients=[],
                cooking_time_minutes=10,
                instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=500.0,
                protein_g=30.0,
                fat_g=20.0,
                carbs_g=50.0,
            ),
            meal_type="breakfast",
        )

        meal2 = Meal(
            recipe=Recipe(
                id="r2",
                name="Meal 2",
                ingredients=[],
                cooking_time_minutes=15,
                instructions=[],
            ),
            nutrition=NutritionProfile(
                calories=600.0,
                protein_g=40.0,
                fat_g=25.0,
                carbs_g=60.0,
            ),
            meal_type="lunch",
        )

        total = NutritionAggregator.aggregate_meals([meal1, meal2])

        assert abs(total.calories - 1100.0) < 0.01
        assert abs(total.protein_g - 70.0) < 0.01
        assert abs(total.fat_g - 45.0) < 0.01
        assert abs(total.carbs_g - 110.0) < 0.01

    def test_aggregate_empty_meals(self):
        """Test aggregating empty meal list returns zero nutrition."""
        total = NutritionAggregator.aggregate_meals([])

        assert total.calories == 0.0
        assert total.protein_g == 0.0
        assert total.fat_g == 0.0
        assert total.carbs_g == 0.0

    def test_aggregate_three_meals(self):
        """Test aggregating three meals."""
        meals = [
            Meal(
                recipe=Recipe(
                    id=f"r{i}",
                    name=f"Meal {i}",
                    ingredients=[],
                    cooking_time_minutes=10,
                    instructions=[],
                ),
                nutrition=NutritionProfile(
                    calories=100.0 * (i + 1),
                    protein_g=10.0 * (i + 1),
                    fat_g=5.0 * (i + 1),
                    carbs_g=15.0 * (i + 1),
                ),
                meal_type="breakfast",
            )
            for i in range(3)
        ]

        total = NutritionAggregator.aggregate_meals(meals)

        assert abs(total.calories - 600.0) < 0.01  # 100 + 200 + 300
        assert abs(total.protein_g - 60.0) < 0.01  # 10 + 20 + 30
        assert abs(total.fat_g - 30.0) < 0.01  # 5 + 10 + 15
        assert abs(total.carbs_g - 90.0) < 0.01  # 15 + 30 + 45

