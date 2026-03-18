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
from src.planning.orchestrator import plan_with_llm_feedback
from src.output.formatters import format_result_markdown, format_result_json_string
from src.providers.local_provider import LocalIngredientProvider
from src.providers.api_provider import APIIngredientProvider, IngredientResolutionError
from src.config.llm_settings import load_llm_settings
from src.llm.client import LLMClient
from src.llm.pipeline import generate_validate_persist_recipes
from src.data_layer.upper_limits import UpperLimitsLoader, resolve_upper_limits
from src.llm.tag_filter import filter_recipe_ids_by_preferences
from src.llm.recipe_tagger import tag_recipes
from src.llm.tag_repository import load_recipe_tags, upsert_recipe_tags


DEFAULT_TAG_PATH = "data/recipes/recipe_tags.json"


def _normalize_tag_pref_value(value: object) -> object:
    """Normalize incoming tag preference values to plain JSON types."""

    if value is None:
        return None

    if hasattr(value, "value"):
        try:
            return getattr(value, "value")
        except Exception:
            pass

    return value


def _extract_tag_preferences(obj: object) -> dict[str, object]:
    """Extract tag filter preferences from a CLI args-like object."""

    cuisine = getattr(obj, "cuisine", None)
    cost_level = getattr(obj, "cost_level", None)
    prep_time_bucket = getattr(obj, "prep_time_bucket", None)
    dietary_flags = getattr(obj, "dietary_flags", None)

    preferences: dict[str, object] = {}

    if cuisine is not None:
        if isinstance(cuisine, list) and cuisine:
            preferences["cuisine"] = [
                _normalize_tag_pref_value(v) for v in cuisine
            ]
        elif isinstance(cuisine, str) and cuisine.strip():
            preferences["cuisine"] = _normalize_tag_pref_value(cuisine)
        elif not isinstance(cuisine, list) and cuisine:
            preferences["cuisine"] = _normalize_tag_pref_value(cuisine)

    cost_level = _normalize_tag_pref_value(cost_level)
    if isinstance(cost_level, str) and cost_level.strip():
        preferences["cost_level"] = cost_level

    prep_time_bucket = _normalize_tag_pref_value(prep_time_bucket)
    if isinstance(prep_time_bucket, str) and prep_time_bucket.strip():
        preferences["prep_time_bucket"] = prep_time_bucket

    if dietary_flags is not None:
        if isinstance(dietary_flags, list) and dietary_flags:
            preferences["dietary_flags"] = [
                _normalize_tag_pref_value(v) for v in dietary_flags
            ]
        elif isinstance(dietary_flags, str) and dietary_flags.strip():
            preferences["dietary_flags"] = [_normalize_tag_pref_value(dietary_flags)]
        elif not isinstance(dietary_flags, list) and dietary_flags:
            preferences["dietary_flags"] = [_normalize_tag_pref_value(dietary_flags)]

    return preferences


def _apply_recipe_tag_filter_pre_convert(
    *, recipes: list[object], request_like: object, tag_path: str
) -> tuple[list[object], dict[str, object]]:
    """Optionally filter recipes deterministically based on strict tag metadata."""

    input_recipe_count = len(recipes)
    if input_recipe_count == 0:
        return (
            recipes,
            {
                "filter_applied": False,
                "input_recipe_count": 0,
                "output_recipe_count": 0,
            },
        )

    preferences = _extract_tag_preferences(request_like)
    if not preferences:
        return (
            recipes,
            {
                "filter_applied": False,
                "input_recipe_count": input_recipe_count,
                "output_recipe_count": input_recipe_count,
            },
        )

    tags_by_id = load_recipe_tags(tag_path)

    cuisine_pref = preferences.get("cuisine")
    if isinstance(cuisine_pref, list) and cuisine_pref:
        accepted_ids: list[str] = []
        for cuisine in cuisine_pref:
            single_prefs = dict(preferences)
            single_prefs["cuisine"] = cuisine
            accepted_ids_for_cuisine = filter_recipe_ids_by_preferences(
                tags_by_id,
                preferences=single_prefs,
            )
            accepted_ids.extend(accepted_ids_for_cuisine)
        filtered_ids_set = set(accepted_ids)
    else:
        filtered_ids = filter_recipe_ids_by_preferences(
            tags_by_id,
            preferences=preferences,
        )
        filtered_ids_set = set(filtered_ids)

    if not filtered_ids_set:
        filtered_recipes = list(recipes)
    else:
        filtered_recipes = [
            r for r in recipes if getattr(r, "id", None) in filtered_ids_set
        ]

    log_payload = {
        "filter_applied": True,
        "input_recipe_count": input_recipe_count,
        "output_recipe_count": len(filtered_recipes),
    }
    return filtered_recipes, log_payload



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
    parser.add_argument(
        "--planning-mode",
        type=str,
        choices=["deterministic", "assisted", "assisted_cached", "assisted_live"],
        default=None,
        help=(
            "Planner behavior selection. If omitted, falls back to legacy "
            "behavior based on LLM_ENABLED (LLM config)."
        ),
    )

    # ---------------------------------------------------------------------
    # Optional tag-based recipe pool filtering (deterministic)
    # ---------------------------------------------------------------------
    parser.add_argument(
        "--recipe-tags-path",
        type=str,
        default=None,
        help=f"Path to recipe tags JSON (default: {DEFAULT_TAG_PATH})",
    )
    parser.add_argument(
        "--cuisine",
        action="append",
        default=None,
        help="Cuisine tag preference (repeatable: --cuisine mexican --cuisine italian)",
    )
    parser.add_argument(
        "--cost-level",
        type=str,
        choices=["cheap", "standard", "premium"],
        default=None,
        help="Budget/cost tag preference: cheap|standard|premium",
    )
    parser.add_argument(
        "--prep-time-bucket",
        type=str,
        choices=["snack", "quick_meal", "weeknight_meal", "meal_prep"],
        default=None,
        help="Prep time bucket tag preference",
    )
    parser.add_argument(
        "--dietary-flags",
        action="append",
        default=None,
        choices=["vegetarian", "vegan", "gluten_free", "dairy_free"],
        help="Dietary tag preference (repeatable: --dietary-flags vegan --dietary-flags gluten_free)",
    )

    parser.add_argument(
        "--tag-recipes",
        action="store_true",
        help="Generate and persist recipe tags (writes to --recipe-tags-path).",
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
        if args.tag_recipes:
            # Deterministic recipe tags are generated via the LLM and persisted
            # to the tag repository file. This command does not run planning.
            llm_settings = load_llm_settings()
            client = LLMClient(llm_settings)

            recipe_db = RecipeDB(str(recipes_path))
            all_recipes = recipe_db.get_all_recipes()

            tags_by_id = tag_recipes(client, all_recipes)

            tag_path = getattr(args, "recipe_tags_path", None) or DEFAULT_TAG_PATH
            upsert_recipe_tags(str(tag_path), tags_by_id)
            print(json.dumps({"tagged_recipe_count": len(tags_by_id)}))
            return

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

        tag_path = getattr(args, "recipe_tags_path", None) or DEFAULT_TAG_PATH
        all_recipes, filter_log = _apply_recipe_tag_filter_pre_convert(
            recipes=all_recipes,
            request_like=args,
            tag_path=str(tag_path),
        )
        print(json.dumps(filter_log, sort_keys=True, ensure_ascii=True), file=sys.stderr)
        
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
        llm_settings = load_llm_settings()
        effective_mode = (
            args.planning_mode
            if args.planning_mode is not None
            else ("assisted" if llm_settings.enabled else "deterministic")
        )

        if effective_mode == "deterministic":
            result = plan_meals(planning_profile, recipe_pool, args.days)
        else:
            if not llm_settings.enabled:
                raise ValueError(
                    f"planning_mode={effective_mode!r} requires LLM_API_KEY/LLM_ENABLED."
                )

            # Feedback-enabled planning route: validate persisted recipes via USDA.
            client = LLMClient(llm_settings)
            usda_client = USDAClient.from_env()
            cached_lookup = CachedIngredientLookup(usda_client=usda_client)
            validation_provider = APIIngredientProvider(cached_lookup)

            deterministic_strict_override = None
            use_feedback_cache = True
            force_live_generation = False

            if args.planning_mode is not None:
                if effective_mode == "assisted":
                    deterministic_strict_override = False
                elif effective_mode == "assisted_cached":
                    deterministic_strict_override = True
                elif effective_mode == "assisted_live":
                    deterministic_strict_override = False
                    use_feedback_cache = False
                    force_live_generation = True

            result = plan_with_llm_feedback(
                planning_profile,
                recipe_pool,
                args.days,
                max_feedback_retries=3,
                recipes_path=str(recipes_path),
                client=client,
                provider=validation_provider,
                deterministic_strict_override=deterministic_strict_override,
                use_feedback_cache=use_feedback_cache,
                force_live_generation=force_live_generation,
            )

            # Formatter must see any recipes persisted by the feedback loop.
            recipe_db_updated = RecipeDB(str(recipes_path))
            all_recipes_updated = recipe_db_updated.get_all_recipes()
            ingredient_names_updated = extract_ingredient_names(all_recipes_updated)
            validation_provider.resolve_all(ingredient_names_updated)
            calculator_updated = NutritionCalculator(validation_provider)
            recipe_pool_updated = convert_recipes(all_recipes_updated, calculator_updated)
            recipe_by_id = {r.id: r for r in recipe_pool_updated}

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

