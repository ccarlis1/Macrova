#!/usr/bin/env python3
"""Command-line interface for the Nutrition Agent meal planner."""

import argparse
import json
import sys
from pathlib import Path

from src.data_layer.user_profile import UserProfileLoader
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.nutrition_db import NutritionDB
from src.nutrition.calculator import NutritionCalculator
from src.ingestion.usda_client import USDAClient
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.planning.converters import convert_recipes, convert_profile, extract_ingredient_names
from src.planning.planner import plan_meals
from src.output.formatters import format_result_markdown, format_result_json_string
from src.providers.local_provider import LocalIngredientProvider
from src.providers.api_provider import APIIngredientProvider, IngredientResolutionError
from src.config.llm_settings import load_llm_settings
from src.llm.client import LLMClient
from src.llm.pipeline import generate_validate_persist_recipes
from src.data_layer.upper_limits import UpperLimitsLoader, resolve_upper_limits



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
    parser.add_argument(
        "--ingredient-source",
        choices=["local", "api"],
        default="local",
        help="Source for ingredient nutrition data (default: local)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        choices=range(1, 8),
        help="Planning horizon: 1-7 days"
    )

    # ---------------------------------------------------------------------
    # LLM recipe generation (optional vertical-slice command)
    # ---------------------------------------------------------------------
    parser.add_argument(
        "--llm-generate-validated",
        action="store_true",
        help="Generate validated LLM recipes and append to the recipes JSON.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of recipes to generate (required with --llm-generate-validated).",
    )
    parser.add_argument(
        "--context-json",
        type=str,
        default=None,
        help="Generation context as inline JSON or a file path (required with --llm-generate-validated).",
    )
    parser.add_argument(
        "--llm-generate-and-plan",
        action="store_true",
        help="After generating recipes, run the planner on the updated recipe pool.",
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
        if args.llm_generate_validated:
            if args.count is None:
                raise ValueError("--count is required when using --llm-generate-validated")
            if not args.context_json:
                raise ValueError("--context-json is required when using --llm-generate-validated")

            context_raw = args.context_json.strip()
            if context_raw.startswith("{") or context_raw.startswith("["):
                context = json.loads(context_raw)
            else:
                context = json.loads(Path(context_raw).read_text(encoding="utf-8"))

            if not isinstance(context, dict):
                raise ValueError("--context-json must resolve to a JSON object (dict)")

            # LLM client + USDA-backed provider (USDA gate is mandatory).
            llm_settings = load_llm_settings()
            client = LLMClient(llm_settings)

            usda_client = USDAClient.from_env()
            cached_lookup = CachedIngredientLookup(usda_client=usda_client)
            validation_provider = APIIngredientProvider(cached_lookup)

            summary = generate_validate_persist_recipes(
                context=context,
                count=args.count,
                recipes_path=str(recipes_path),
                provider=validation_provider,
                client=client,
            )
            # Deterministic output for operators/scripts.
            print(json.dumps(summary))

            if not args.llm_generate_and_plan:
                return

        # Load user profile
        print(f"Loading user profile from {profile_path}...", file=sys.stderr)
        profile_loader = UserProfileLoader(str(profile_path))
        user_profile = profile_loader.load()
        
        # Load recipes
        print(f"Loading recipes from {recipes_path}...", file=sys.stderr)
        recipe_db = RecipeDB(str(recipes_path))
        all_recipes = recipe_db.get_all_recipes()
        print(f"Found {len(all_recipes)} recipes", file=sys.stderr)
        
        # Create ingredient provider (local or API)
        if args.ingredient_source == "api":
            try:
                usda_client = USDAClient.from_env()
                cached_lookup = CachedIngredientLookup(usda_client=usda_client)
                provider = APIIngredientProvider(cached_lookup)
            except Exception as e:
                print("Failed to initialize ingredient API:", file=sys.stderr)
                print(str(e), file=sys.stderr)
                sys.exit(3)
        else:
            print(f"Loading ingredients from {ingredients_path}...", file=sys.stderr)
            nutrition_db = NutritionDB(str(ingredients_path))
            provider = LocalIngredientProvider(nutrition_db)
        
        # Eager ingredient resolution (deterministic, fail-fast; no API calls after this)
        all_ingredient_names = extract_ingredient_names(all_recipes)
        try:
            provider.resolve_all(all_ingredient_names)
        except IngredientResolutionError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(3)

        calculator = NutritionCalculator(provider)
        recipe_pool = convert_recipes(all_recipes, calculator)
        recipe_by_id = {r.id: r for r in recipe_pool}
        planning_profile = convert_profile(user_profile, args.days)


        loader = UpperLimitsLoader("data/reference/ul_by_demographic.json")
        resolved_ul = resolve_upper_limits(loader, demographic="adult_male", overrides=None)

        print("Planning meals...", file=sys.stderr)
        result = plan_meals(planning_profile, recipe_pool, args.days)

        # Format output
        if args.output in ["markdown", "both"]:
            markdown_output = format_result_markdown(result, recipe_by_id, planning_profile, args.days)
            if args.output_file:
                output_path = Path(args.output_file)
                if args.output == "both":
                    output_path = output_path.with_suffix(".md")
                output_path.write_text(markdown_output)
                print(f"Markdown output saved to {output_path}", file=sys.stderr)
            else:
                print(markdown_output)

        if args.output in ["json", "both"]:
            json_output = format_result_json_string(result, recipe_by_id, planning_profile, args.days)
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
            if result.warning:
                for k, v in result.warning.items():
                    print(f"   - {k}: {v}", file=sys.stderr)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

