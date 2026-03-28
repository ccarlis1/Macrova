#!/usr/bin/env python3
"""Export planner debug artifacts for CLI vs Flutter parity investigations.

Derives from the same files the CLI uses (--profile, --recipes, --ingredients):

1) cli_plan_request.json — JSON body shape for POST /api/v1/plan (mirrors YAML profile).
2) recipe_pool_snapshot.json — recipe ids, names, counts, stable hash of id list.
3) planner_run.json — planner outcome using the same ingredient provider as the CLI
   for `--ingredient-source` (local JSON vs USDA api). Previously this always used local;
   that mismatch caused TC-2/FM-4 when cli_plan_request said api but the dry-run used local.

Flutter/API artifacts this script CANNOT produce (must capture on your machine):
- Raw POST /api/v1/plan body from the app (DevTools Network or temporary logging).
- Uvicorn stderr for the API process when that request hits the server.

Usage (from repo root, venv active):

  python3 scripts/export_planner_debug_artifacts.py \\
    --profile config/user_profile.yaml \\
    --recipes data/recipes/recipes.json \\
    --ingredients data/ingredients/custom_ingredients.json \\
    --days 1 \\
    --out-dir debug_artifacts/

Optional: replay the exported request against a running API:

  curl -sS -X POST http://127.0.0.1:8000/api/v1/plan \\
    -H 'Content-Type: application/json' \\
    -d @debug_artifacts/cli_plan_request.json | jq .
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Repo root on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Match `src.cli`: load `.env` so USDAClient.from_env() sees USDA_API_KEY when using api mode.
_env_file = _ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.recipe_db import RecipeDB
from src.data_layer.user_profile import UserProfileLoader
from src.ingestion.ingredient_cache import CachedIngredientLookup
from src.ingestion.usda_client import USDAClient
from src.nutrition.calculator import NutritionCalculator
from src.planning.converters import convert_profile, convert_recipes, extract_ingredient_names
from src.planning.planner import plan_meals
from src.providers.api_provider import APIIngredientProvider
from src.providers.local_provider import LocalIngredientProvider


def _build_ingredient_provider(
    ingredient_source: str,
    ingredients_path: str,
) -> Any:
    """Same construction as `src.cli` / `plan_meals_endpoint` for local vs api."""
    if ingredient_source == "api":
        usda_client = USDAClient.from_env()
        cached_lookup = CachedIngredientLookup(usda_client=usda_client)
        return APIIngredientProvider(cached_lookup)
    nutrition_db = NutritionDB(ingredients_path)
    return LocalIngredientProvider(nutrition_db)


def _user_profile_to_plan_request(
    *,
    loader_path: str,
    days: int,
    ingredient_source: str,
    planning_mode: Optional[str],
    recipe_ids: Optional[List[str]],
) -> Dict[str, Any]:
    user = UserProfileLoader(loader_path).load()
    body: Dict[str, Any] = {
        "daily_calories": user.daily_calories,
        "daily_protein_g": user.daily_protein_g,
        "daily_fat_g_min": user.daily_fat_g[0],
        "daily_fat_g_max": user.daily_fat_g[1],
        "schedule": dict(user.schedule),
        "liked_foods": list(user.liked_foods),
        "disliked_foods": list(user.disliked_foods),
        "allergies": list(user.allergies),
        "days": days,
        "ingredient_source": ingredient_source,
        "micronutrient_weekly_min_fraction": user.micronutrient_weekly_min_fraction,
    }
    if user.daily_micronutrient_targets:
        body["micronutrient_goals"] = dict(user.daily_micronutrient_targets)
    if planning_mode is not None:
        body["planning_mode"] = planning_mode
    if recipe_ids is not None and recipe_ids:
        body["recipe_ids"] = list(recipe_ids)
    return body


def _recipe_pool_snapshot(recipes_path: str) -> Dict[str, Any]:
    db = RecipeDB(recipes_path)
    recipes = db.get_all_recipes()
    rows = []
    ids: List[str] = []
    for r in sorted(recipes, key=lambda x: x.id):
        ids.append(r.id)
        rows.append(
            {
                "id": r.id,
                "name": r.name,
                "cooking_time_minutes": r.cooking_time_minutes,
                "ingredient_line_count": len(r.ingredients),
            }
        )
    id_blob = "\n".join(ids).encode("utf-8")
    return {
        "recipes_path": str(Path(recipes_path).resolve()),
        "recipe_count": len(rows),
        "recipe_ids_sorted": ids,
        "recipe_ids_sha256": hashlib.sha256(id_blob).hexdigest(),
        "recipes": rows,
    }


def _planning_profile_summary(profile: Any) -> Dict[str, Any]:
    day0 = profile.schedule[0] if profile.schedule else []
    return {
        "daily_calories": profile.daily_calories,
        "daily_protein_g": profile.daily_protein_g,
        "daily_fat_g": list(profile.daily_fat_g),
        "daily_carbs_g": profile.daily_carbs_g,
        "micronutrient_targets_count": len(profile.micronutrient_targets or {}),
        "micronutrient_weekly_min_fraction": profile.micronutrient_weekly_min_fraction,
        "excluded_ingredients": list(profile.excluded_ingredients),
        "schedule_day0": [
            {"time": s.time, "busyness_level": s.busyness_level, "meal_type": s.meal_type}
            for s in day0
        ],
        "horizon_days": len(profile.schedule),
    }


def _run_planner(
    *,
    profile_yaml: str,
    recipes_path: str,
    ingredients_path: str,
    days: int,
    ingredient_source: str,
) -> Dict[str, Any]:
    user = UserProfileLoader(profile_yaml).load()
    planning_profile = convert_profile(user, days)

    recipe_db = RecipeDB(recipes_path)
    all_recipes = recipe_db.get_all_recipes()
    try:
        provider = _build_ingredient_provider(ingredient_source, ingredients_path)
        provider.resolve_all(extract_ingredient_names(all_recipes))
    except Exception as exc:  # noqa: BLE001 — surface USDA/env errors in artifact JSON
        return {
            "ingredient_source": ingredient_source,
            "planner_error": "ingredient_provider_init_or_resolve_failed",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "planning_profile": _planning_profile_summary(planning_profile),
            "recipe_pool_count": len(all_recipes),
        }
    calculator = NutritionCalculator(provider)
    recipe_pool = convert_recipes(all_recipes, calculator)

    result = plan_meals(planning_profile, recipe_pool, days)
    return {
        "ingredient_source": ingredient_source,
        "success": result.success,
        "termination_code": result.termination_code,
        "failure_mode": result.failure_mode,
        "stats": result.stats,
        "report": result.report,
        "plan_incomplete_reason": result.plan_incomplete_reason,
        "plan_assignment_count": len(result.plan or []),
        "planning_profile": _planning_profile_summary(planning_profile),
        "recipe_pool_count": len(recipe_pool),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="config/user_profile.yaml")
    parser.add_argument("--recipes", default="data/recipes/recipes.json")
    parser.add_argument("--ingredients", default="data/ingredients/custom_ingredients.json")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--ingredient-source", default="local", choices=("local", "api"))
    parser.add_argument(
        "--planning-mode",
        default=None,
        help="Omit for deterministic parity (default). Else assisted|assisted_cached|assisted_live.",
    )
    parser.add_argument(
        "--recipe-ids",
        default=None,
        help="Comma-separated ids to include in cli_plan_request.json (optional).",
    )
    parser.add_argument(
        "--out-dir",
        default="debug_artifacts",
        help="Directory to write JSON files (created if missing).",
    )
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    recipe_ids = None
    if args.recipe_ids:
        recipe_ids = [x.strip() for x in args.recipe_ids.split(",") if x.strip()]

    plan_request = _user_profile_to_plan_request(
        loader_path=args.profile,
        days=args.days,
        ingredient_source=args.ingredient_source,
        planning_mode=args.planning_mode,
        recipe_ids=recipe_ids,
    )
    (out / "cli_plan_request.json").write_text(
        json.dumps(plan_request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    snapshot = _recipe_pool_snapshot(args.recipes)
    (out / "recipe_pool_snapshot.json").write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    run = _run_planner(
        profile_yaml=args.profile,
        recipes_path=args.recipes,
        ingredients_path=args.ingredients,
        days=args.days,
        ingredient_source=args.ingredient_source,
    )
    (out / "planner_run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    meta = {
        "profile": str(Path(args.profile).resolve()),
        "recipes": str(Path(args.recipes).resolve()),
        "ingredients": str(Path(args.ingredients).resolve()),
        "out_dir": str(out.resolve()),
        "written": [
            "cli_plan_request.json",
            "recipe_pool_snapshot.json",
            "planner_run.json",
        ],
        "next_steps_for_flutter_parity": [
            "Chrome DevTools → Network → filter 'plan' → POST /api/v1/plan → "
            "Payload / Request body → copy JSON into flutter_plan_request.json",
            "Or: Right-click request → Copy → Copy as cURL (includes body)",
            "Run API with stderr visible: uvicorn src.api.server:app --reload 2> api_stderr.log",
        ],
    }
    (out / "README.txt").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote artifacts under {out.resolve()}")
    for name in meta["written"]:
        print(f"  - {name}")
    if "termination_code" in run:
        print(
            f"Summary: ingredient_source={run.get('ingredient_source')} "
            f"termination={run['termination_code']} failure_mode={run['failure_mode']}"
        )
    else:
        print(f"Summary: planner_run failed before search — {run.get('planner_error')}: {run.get('error_message')}")


if __name__ == "__main__":
    main()
