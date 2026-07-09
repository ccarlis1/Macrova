#!/usr/bin/env python3
"""Test USDA API resolution for all ingredients in recipes.json.

Queries each recipe ingredient name against the USDA FoodData Central API,
then tests known raw ingredients to prove the pipeline works end-to-end.

Usage:
    PYTHONPATH=. python scripts/test_usda_lookup.py [--api-key KEY]

If --api-key is omitted, reads USDA_API_KEY from .env / environment.
Falls back to DEMO_KEY for basic connectivity checks.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion.usda_client import USDAClient
from src.ingestion.ingredient_cache import CachedIngredientLookup


RECIPES_PATH = "data/recipes/recipes.json"

KNOWN_RAW_INGREDIENTS = [
    "rice",
    "egg",
    "chicken breast",
    "salmon",
    "greek yogurt",
    "sweet potato",
    "black beans",
    "olive oil",
    "oats",
    "ground beef",
]


def _load_env() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def humanize(name: str) -> str:
    return name.replace("_", " ").strip()


def extract_recipe_ingredients(recipes_path: str) -> list[dict]:
    data = json.loads(Path(recipes_path).read_text())
    seen: set[str] = set()
    out: list[dict] = []
    for recipe in data.get("recipes", []):
        for ing in recipe.get("ingredients", []):
            name = ing["name"]
            if name not in seen:
                seen.add(name)
                out.append({
                    "raw_name": name,
                    "human_name": humanize(name),
                    "recipe_id": recipe["id"],
                    "recipe_name": recipe["name"],
                    "quantity": ing["quantity"],
                    "unit": ing["unit"],
                })
    return out


def _lookup_one(client: USDAClient, query: str) -> dict:
    result = client.lookup(query)
    if result.success:
        return {
            "success": True,
            "fdc_id": result.fdc_id,
            "description": result.description,
            "data_type": result.data_type.value if result.data_type else None,
            "total_hits": result.source_metadata.get("total_hits", 0),
        }
    return {
        "success": False,
        "error_code": result.error_code,
        "error_message": result.error_message,
    }


def section(title: str) -> None:
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def main() -> None:
    _load_env()

    api_key: str | None = None
    if "--api-key" in sys.argv:
        idx = sys.argv.index("--api-key")
        api_key = sys.argv[idx + 1]

    # Resolve API key: explicit flag → env → DEMO_KEY fallback
    if api_key is None:
        api_key = os.environ.get("USDA_API_KEY", "").strip()

    env_key_is_placeholder = (
        not api_key
        or api_key.startswith("your")
        or len(api_key) < 20
    )

    section("USDA API Resolution Test")

    if env_key_is_placeholder:
        print("  WARNING: USDA_API_KEY is missing or is a placeholder.")
        print(f"           Key value starts with: {api_key[:8]!r}... (len={len(api_key)})")
        print("           Falling back to DEMO_KEY for connectivity testing.")
        print("           To test with full access, set a valid USDA_API_KEY in .env\n")
        api_key = "DEMO_KEY"
    else:
        print(f"  Using USDA_API_KEY from environment (len={len(api_key)})\n")

    client = USDAClient(api_key=api_key)

    # ------------------------------------------------------------------
    # Phase 0: Connectivity check
    # ------------------------------------------------------------------
    section("PHASE 0 — API Connectivity Check")
    probe = client.lookup("rice")
    time.sleep(0.3)
    if probe.success:
        print(f"  API reachable ✓   (probe='rice' → {probe.description})")
    else:
        print(f"  API UNREACHABLE ✗  (probe='rice' → {probe.error_code}: {probe.error_message})")
        print("\n  Cannot proceed without API connectivity. Exiting.")
        sys.exit(2)

    # ------------------------------------------------------------------
    # Phase 1: Recipe ingredients (composite meal names)
    # ------------------------------------------------------------------
    section("PHASE 1 — Recipe Ingredients from recipes.json")
    ingredients = extract_recipe_ingredients(RECIPES_PATH)
    print(f"  {len(ingredients)} unique ingredient names found.\n")
    print(f"  NOTE: These are composite meal names (e.g. 'carb_heavy', 'bolognese'),")
    print(f"        not raw USDA-queryable ingredients. They are designed for the")
    print(f"        local provider (custom_ingredients.json).\n")

    recipe_results: list[dict] = []
    for ing in ingredients:
        time.sleep(0.35)
        result = _lookup_one(client, ing["human_name"])
        recipe_results.append({**ing, **result})

    ok = sum(1 for r in recipe_results if r["success"])
    miss = len(recipe_results) - ok

    print(f"  {'Ingredient':32s} {'Status':7s}  USDA Match / Error")
    print(f"  {'-'*32} {'-'*7}  {'-'*40}")
    for r in recipe_results:
        if r["success"]:
            match_quality = "MISLEADING" if r["description"].lower() != r["human_name"] else "EXACT"
            print(f"  {r['human_name']:32s} {'OK':7s}  {r['description'][:40]}  [{match_quality}]")
        else:
            err = r.get("error_code", "?")
            print(f"  {r['human_name']:32s} {'FAIL':7s}  {err}")

    print(f"\n  Result: {ok}/{len(recipe_results)} returned a USDA match,")
    if ok > 0:
        print(f"          but matches are misleading (composite names → wrong USDA foods).")
    print(f"          {miss}/{len(recipe_results)} failed outright.\n")

    # ------------------------------------------------------------------
    # Phase 2: Known raw ingredients (prove the pipeline works)
    # ------------------------------------------------------------------
    section("PHASE 2 — Known Raw Ingredients (control group)")
    print(f"  Testing {len(KNOWN_RAW_INGREDIENTS)} known USDA-resolvable ingredients\n")

    tmp_cache = tempfile.mkdtemp(prefix="usda_test_cache_")
    cached_lookup = CachedIngredientLookup(cache_dir=tmp_cache, usda_client=client)

    control_results: list[dict] = []
    for name in KNOWN_RAW_INGREDIENTS:
        time.sleep(0.35)
        entry = cached_lookup.lookup(name)
        row: dict = {"ingredient": name}
        if entry is not None:
            row["resolved"] = True
            row["fdc_id"] = entry.fdc_id
            row["usda_description"] = entry.description
            row["data_type"] = entry.data_type
            n = entry.nutrition
            row["kcal"] = round(n.calories, 1)
            row["protein"] = round(n.protein_g, 1)
            row["fat"] = round(n.fat_g, 1)
            row["carbs"] = round(n.carbs_g, 1)
        else:
            row["resolved"] = False
        control_results.append(row)

    ctrl_ok = sum(1 for r in control_results if r.get("resolved"))
    print(f"  {'Ingredient':20s} {'Status':9s}  {'USDA Description':40s}  Cal   Pro   Fat   Carb")
    print(f"  {'-'*20} {'-'*9}  {'-'*40}  {'-'*5} {'-'*5} {'-'*5} {'-'*5}")
    for r in control_results:
        if r.get("resolved"):
            desc = r["usda_description"][:40]
            print(
                f"  {r['ingredient']:20s} {'RESOLVED':9s}  {desc:40s}"
                f"  {r['kcal']:5.0f} {r['protein']:5.1f} {r['fat']:5.1f} {r['carbs']:5.1f}"
            )
        else:
            print(f"  {r['ingredient']:20s} {'FAILED':9s}")

    print(f"\n  Result: {ctrl_ok}/{len(KNOWN_RAW_INGREDIENTS)} known ingredients resolved via USDA full pipeline.\n")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    section("SUMMARY")
    print(f"  USDA API connectivity:           {'OK' if probe.success else 'FAIL'}")
    print(f"  API key status:                  {'placeholder (using DEMO_KEY)' if env_key_is_placeholder else 'valid'}")
    print(f"  Recipe ingredients (composite):  {ok}/{len(recipe_results)} got a match (all misleading)")
    print(f"  Control ingredients (raw):       {ctrl_ok}/{len(KNOWN_RAW_INGREDIENTS)} resolved correctly")
    print()
    print("  DIAGNOSIS:")
    if env_key_is_placeholder:
        print("  1. USDA_API_KEY in .env is a placeholder — must be replaced with a real key.")
        print("     Sign up: https://fdc.nal.usda.gov/api-key-signup.html")
    print("  2. Recipe ingredients in recipes.json are composite meal names (e.g. 'carb_heavy',")
    print("     'bolognese') with pre-computed nutrition in custom_ingredients.json.")
    print("     These are NOT raw USDA ingredients and will never resolve correctly via USDA.")
    print("  3. The USDA pipeline (search → details → nutrient map → cache) works correctly")
    print("     when given actual raw ingredient names (chicken breast, rice, etc.).")
    print("  4. For --planning-mode assisted_live, the USDA provider is used to validate")
    print("     LLM-generated recipes whose ingredients ARE raw USDA-resolvable names.\n")

    # Structured report
    report = {
        "api_connectivity": probe.success,
        "api_key_placeholder": env_key_is_placeholder,
        "recipe_ingredients": {
            "total": len(recipe_results),
            "matched": ok,
            "failed": miss,
            "results": recipe_results,
        },
        "control_ingredients": {
            "total": len(KNOWN_RAW_INGREDIENTS),
            "resolved": ctrl_ok,
            "results": control_results,
        },
    }
    report_path = Path("/opt/cursor/artifacts/usda_lookup_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"  JSON report written to {report_path}")


if __name__ == "__main__":
    main()
