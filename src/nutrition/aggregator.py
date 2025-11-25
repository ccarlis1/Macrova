"""Nutrition aggregator for summing nutrition across meals and recipes."""
from typing import List

from src.data_layer.models import Meal, Recipe, NutritionProfile
from src.nutrition.calculator import NutritionCalculator


class NutritionAggregator:
    """Aggregator for combining nutrition from multiple sources."""

    @staticmethod
    def aggregate_meals(meals: List[Meal]) -> NutritionProfile:
        """Aggregate nutrition from multiple meals.
        
        Args:
            meals: List of Meal objects
        
        Returns:
            NutritionProfile with summed nutrition
        """
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0

        for meal in meals:
            total_calories += meal.nutrition.calories
            total_protein += meal.nutrition.protein_g
            total_fat += meal.nutrition.fat_g
            total_carbs += meal.nutrition.carbs_g

        return NutritionProfile(
            calories=total_calories,
            protein_g=total_protein,
            fat_g=total_fat,
            carbs_g=total_carbs,
        )

    @staticmethod
    def aggregate_recipes(
        recipes: List[Recipe], calculator: NutritionCalculator
    ) -> NutritionProfile:
        """Aggregate nutrition from multiple recipes.
        
        Args:
            recipes: List of Recipe objects
            calculator: NutritionCalculator instance
        
        Returns:
            NutritionProfile with summed nutrition
        """
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0

        for recipe in recipes:
            recipe_nutrition = calculator.calculate_recipe_nutrition(recipe)
            total_calories += recipe_nutrition.calories
            total_protein += recipe_nutrition.protein_g
            total_fat += recipe_nutrition.fat_g
            total_carbs += recipe_nutrition.carbs_g

        return NutritionProfile(
            calories=total_calories,
            protein_g=total_protein,
            fat_g=total_fat,
            carbs_g=total_carbs,
        )

