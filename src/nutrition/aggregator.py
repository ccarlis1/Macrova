"""Nutrition aggregator for summing nutrition across meals and recipes."""
from dataclasses import fields
from typing import List, Dict

from src.data_layer.models import (
    Meal,
    Recipe,
    NutritionProfile,
    MicronutrientProfile,
    DailyNutritionTracker,
    WeeklyNutritionTracker,
)
from src.nutrition.calculator import NutritionCalculator


class NutritionAggregator:
    """Aggregator for combining nutrition from multiple sources.
    
    Supports aggregation at multiple levels:
    - Meals -> NutritionProfile (daily total)
    - Meals -> DailyNutritionTracker
    - DailyNutritionTrackers -> WeeklyNutritionTracker
    
    Weekly tracking uses a fixed 7-day week (Monday-Sunday) approach rather than
    a rolling window. This aligns with REASONING_LOGIC.md which describes weekly
    RDIs and carryover logic that assumes distinct weeks.
    """

    # Cache micronutrient field names for efficient aggregation
    _MICRO_FIELDS: List[str] = [f.name for f in fields(MicronutrientProfile)]

    @staticmethod
    def _create_empty_micro_totals() -> Dict[str, float]:
        """Create a dict of micronutrient fields initialized to 0.0."""
        return {field: 0.0 for field in NutritionAggregator._MICRO_FIELDS}

    @staticmethod
    def _add_micronutrients_to_totals(
        totals: Dict[str, float], micros: MicronutrientProfile
    ) -> None:
        """Add micronutrient values to running totals dict (in place)."""
        for field in NutritionAggregator._MICRO_FIELDS:
            totals[field] += getattr(micros, field, 0.0)

    @staticmethod
    def aggregate_meals(meals: List[Meal]) -> NutritionProfile:
        """Aggregate nutrition from multiple meals.
        
        Args:
            meals: List of Meal objects
        
        Returns:
            NutritionProfile with summed nutrition (macros and micronutrients)
        """
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0
        total_micros = NutritionAggregator._create_empty_micro_totals()

        for meal in meals:
            total_calories += meal.nutrition.calories
            total_protein += meal.nutrition.protein_g
            total_fat += meal.nutrition.fat_g
            total_carbs += meal.nutrition.carbs_g
            # Aggregate micronutrients if present
            if meal.nutrition.micronutrients is not None:
                NutritionAggregator._add_micronutrients_to_totals(
                    total_micros, meal.nutrition.micronutrients
                )

        return NutritionProfile(
            calories=total_calories,
            protein_g=total_protein,
            fat_g=total_fat,
            carbs_g=total_carbs,
            micronutrients=MicronutrientProfile(**total_micros),
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
            NutritionProfile with summed nutrition (macros and micronutrients)
        """
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0
        total_micros = NutritionAggregator._create_empty_micro_totals()

        for recipe in recipes:
            recipe_nutrition = calculator.calculate_recipe_nutrition(recipe)
            total_calories += recipe_nutrition.calories
            total_protein += recipe_nutrition.protein_g
            total_fat += recipe_nutrition.fat_g
            total_carbs += recipe_nutrition.carbs_g
            # Aggregate micronutrients if present
            if recipe_nutrition.micronutrients is not None:
                NutritionAggregator._add_micronutrients_to_totals(
                    total_micros, recipe_nutrition.micronutrients
                )

        return NutritionProfile(
            calories=total_calories,
            protein_g=total_protein,
            fat_g=total_fat,
            carbs_g=total_carbs,
            micronutrients=MicronutrientProfile(**total_micros),
        )

    @staticmethod
    def aggregate_to_daily_tracker(
        date: str, meals: List[Meal]
    ) -> DailyNutritionTracker:
        """Aggregate meals into a DailyNutritionTracker.
        
        Args:
            date: ISO date string (e.g., "2024-01-15")
            meals: List of Meal objects for this day
        
        Returns:
            DailyNutritionTracker with aggregated nutrition and meal IDs
        """
        # Get aggregated nutrition
        total = NutritionAggregator.aggregate_meals(meals)
        
        # Extract meal IDs
        meal_ids = [meal.recipe.id for meal in meals]
        
        return DailyNutritionTracker(
            date=date,
            calories=total.calories,
            protein_g=total.protein_g,
            fat_g=total.fat_g,
            carbs_g=total.carbs_g,
            micronutrients=total.micronutrients if total.micronutrients else MicronutrientProfile(),
            meal_ids=meal_ids,
        )

    @staticmethod
    def aggregate_to_weekly_tracker(
        week_start_date: str, daily_trackers: List[DailyNutritionTracker]
    ) -> WeeklyNutritionTracker:
        """Aggregate daily trackers into a WeeklyNutritionTracker.
        
        Uses a fixed 7-day week approach (not rolling window) which aligns with
        REASONING_LOGIC.md's weekly RDI tracking and carryover logic.
        
        Args:
            week_start_date: ISO date string for Monday of the week
            daily_trackers: List of DailyNutritionTracker objects
        
        Returns:
            WeeklyNutritionTracker with aggregated totals
            
        Note:
            - carryover_needs is NOT calculated here (that's decision logic)
            - This is a passive data container only
        """
        total_calories = 0.0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0
        total_micros = NutritionAggregator._create_empty_micro_totals()

        for daily in daily_trackers:
            total_calories += daily.calories
            total_protein += daily.protein_g
            total_fat += daily.fat_g
            total_carbs += daily.carbs_g
            # Aggregate micronutrients
            NutritionAggregator._add_micronutrients_to_totals(
                total_micros, daily.micronutrients
            )

        return WeeklyNutritionTracker(
            week_start_date=week_start_date,
            days_completed=len(daily_trackers),
            total_calories=total_calories,
            total_protein_g=total_protein,
            total_fat_g=total_fat,
            total_carbs_g=total_carbs,
            total_micronutrients=MicronutrientProfile(**total_micros),
            daily_trackers=daily_trackers,
            # carryover_needs is left as empty dict (decision logic, not aggregation)
        )

