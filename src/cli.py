#!/usr/bin/env python3
"""Command-line interface for the Nutrition Agent meal planner."""

import argparse
import sys
from pathlib import Path

from src.data_layer.user_profile import UserProfileLoader
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.ingredient_db import IngredientDB
from src.nutrition.calculator import NutritionCalculator
from src.nutrition.aggregator import NutritionAggregator
from src.scoring.recipe_scorer import RecipeScorer
from src.ingestion.recipe_retriever import RecipeRetriever
from src.planning.meal_planner import MealPlanner, DailySchedule
from src.output.formatters import format_plan_markdown, format_plan_json_string


def create_daily_schedule(user_profile) -> DailySchedule:
    """Convert UserProfile schedule dict to DailySchedule object.
    
    Args:
        user_profile: UserProfile object with schedule dict
        
    Returns:
        DailySchedule object
        
    Raises:
        ValueError: If schedule doesn't have required meal times
    """
    schedule = user_profile.schedule
    
    # Separate workout time (busyness level 0) from meal times
    workout_time = None
    meal_times = []
    for time_str, busyness in schedule.items():
        if busyness == 0:
            workout_time = time_str
        else:
            meal_times.append(time_str)
    
    # Sort meal times chronologically
    meal_times = sorted(meal_times)
    
    if len(meal_times) < 3:
        raise ValueError(f"Schedule must have at least 3 meal times, found {len(meal_times)}")
    
    # Assume first meal is breakfast, second is lunch, third is dinner
    breakfast_time = meal_times[0]
    lunch_time = meal_times[1]
    dinner_time = meal_times[2]
    
    return DailySchedule(
        breakfast_time=breakfast_time,
        breakfast_busyness=schedule[breakfast_time],
        lunch_time=lunch_time,
        lunch_busyness=schedule[lunch_time],
        dinner_time=dinner_time,
        dinner_busyness=schedule[dinner_time],
        workout_time=workout_time
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate daily meal plans based on nutrition goals and schedule"
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="config/user_profile.yaml",
        help="Path to user profile YAML file (default: config/user_profile.yaml)"
    )
    parser.add_argument(
        "--recipes",
        type=str,
        default="data/recipes/recipes.json",
        help="Path to recipes JSON file (default: data/recipes/recipes.json)"
    )
    parser.add_argument(
        "--ingredients",
        type=str,
        default="data/ingredients/custom_ingredients.json",
        help="Path to ingredients JSON file (default: data/ingredients/custom_ingredients.json)"
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["markdown", "json", "both"],
        default="markdown",
        help="Output format: markdown (default), json, or both"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        help="Optional file path to save output (default: print to stdout)"
    )
    
    args = parser.parse_args()
    
    # Validate file paths
    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(f"Error: User profile file not found: {profile_path}", file=sys.stderr)
        print(f"Hint: Copy config/user_profile.yaml.example to {profile_path} and customize it", file=sys.stderr)
        sys.exit(1)
    
    recipes_path = Path(args.recipes)
    if not recipes_path.exists():
        print(f"Error: Recipes file not found: {recipes_path}", file=sys.stderr)
        sys.exit(1)
    
    ingredients_path = Path(args.ingredients)
    if not ingredients_path.exists():
        print(f"Error: Ingredients file not found: {ingredients_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Load user profile
        print(f"Loading user profile from {profile_path}...", file=sys.stderr)
        profile_loader = UserProfileLoader(str(profile_path))
        user_profile = profile_loader.load()
        
        # Load data
        print(f"Loading recipes from {recipes_path}...", file=sys.stderr)
        recipe_db = RecipeDB(str(recipes_path))
        
        print(f"Loading ingredients from {ingredients_path}...", file=sys.stderr)
        ingredient_db = IngredientDB(str(ingredients_path))
        nutrition_db = NutritionDB(str(ingredients_path))
        
        # Initialize components
        nutrition_calculator = NutritionCalculator(nutrition_db)
        nutrition_aggregator = NutritionAggregator()
        recipe_scorer = RecipeScorer(nutrition_calculator)
        recipe_retriever = RecipeRetriever(recipe_db)
        meal_planner = MealPlanner(recipe_scorer, recipe_retriever, nutrition_aggregator)
        
        # Create daily schedule
        daily_schedule = create_daily_schedule(user_profile)
        
        # Get all available recipes
        all_recipes = recipe_db.get_all_recipes()
        print(f"Found {len(all_recipes)} recipes", file=sys.stderr)
        
        # Plan meals
        print("Planning meals...", file=sys.stderr)
        result = meal_planner.plan_daily_meals(
            user_profile=user_profile,
            schedule=daily_schedule,
            available_recipes=all_recipes
        )
        
        # Format output
        if args.output in ["markdown", "both"]:
            markdown_output = format_plan_markdown(result)
            if args.output_file:
                output_path = Path(args.output_file)
                if args.output == "both":
                    output_path = output_path.with_suffix(".md")
                output_path.write_text(markdown_output)
                print(f"Markdown output saved to {output_path}", file=sys.stderr)
            else:
                print(markdown_output)
        
        if args.output in ["json", "both"]:
            json_output = format_plan_json_string(result, indent=2)
            if args.output_file:
                output_path = Path(args.output_file)
                if args.output == "both":
                    output_path = output_path.with_suffix(".json")
                else:
                    output_path = Path(args.output_file)
                output_path.write_text(json_output)
                print(f"JSON output saved to {output_path}", file=sys.stderr)
            else:
                if args.output == "both":
                    print("\n" + "="*80 + "\n", file=sys.stdout)
                print(json_output)
        
        # Print summary to stderr
        if result.success:
            print("\n✅ Meal plan generated successfully!", file=sys.stderr)
        else:
            print("\n⚠️  Meal plan generated with warnings:", file=sys.stderr)
            for warning in result.warnings:
                print(f"   - {warning}", file=sys.stderr)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

