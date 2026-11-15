"""DATA-2: vitamin D in the reference ingredient table stays in a plausible range.

The draft table once carried vitamin D about 40 times too high (the USDA mapper
multiplied the IU entry by 40 and added the µg entry). These checks fail on that
data: 5 entries were above the per-100 g ceiling and 6 starter recipes were above
the 4,000 IU daily upper limit on their own.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.recipe_db import RecipeDB
from src.nutrition.calculator import NutritionCalculator
from src.providers.local_provider import LocalIngredientProvider

_ROOT = Path(__file__).resolve().parents[1]
_REF = _ROOT / "data" / "reference" / "ingredient_nutrition.json"
_UL = _ROOT / "data" / "reference" / "ul_by_demographic.json"
_STARTER = _ROOT / "data" / "recipes" / "recipes.json.example"
_TAGS = _ROOT / "data" / "recipes" / "recipe_tags.json"

# Per-100 g ceiling for vitamin D (IU). In FDC SR Legacy the richest ordinary
# foods are fatty fish and UV-exposed mushrooms, at roughly 100-1,100 IU/100 g
# (canned pink salmon 761, the highest entry in this table after DATA-2). Only
# fish-liver oils go far beyond that (cod liver oil 10,000 IU/100 g). 2,000 IU
# leaves headroom for any ordinary food and still catches a x40 unit error on
# anything with a real vitamin D content (eggs 82 -> 3,282, tilapia 124 -> 4,963).
# A fish-liver oil added later must be listed here explicitly with its FDC id.
VITAMIN_D_IU_PER_100G_CEILING = 2000.0
CEILING_EXCEPTIONS: dict[str, str] = {}


def _table() -> list[dict]:
    return json.loads(_REF.read_text(encoding="utf-8"))["ingredients"]


def test_no_ingredient_exceeds_the_vitamin_d_ceiling():
    over = [
        (e["name"], e["per_100g"]["vitamin_d_iu"])
        for e in _table()
        if e["name"] not in CEILING_EXCEPTIONS
        and (e["per_100g"].get("vitamin_d_iu") or 0.0) > VITAMIN_D_IU_PER_100G_CEILING
    ]
    assert over == []


def test_corrected_vitamin_d_entries_cite_their_fdc_source():
    """Every non-zero vitamin D value carries the DATA-2 provenance note."""
    missing = [
        e["name"]
        for e in _table()
        if (e["per_100g"].get("vitamin_d_iu") or 0.0) > 0
        and f"FDC {e['fdc_id']} nutrient 1110" not in (e.get("notes") or "")
    ]
    assert missing == []


def _daily_vitamin_d_uls() -> set[float]:
    data = json.loads(_UL.read_text(encoding="utf-8"))
    uls = set()
    for block in data.values():
        if isinstance(block, dict):
            for limits in block.values():
                if isinstance(limits, dict) and limits.get("vitamin_d_iu"):
                    uls.add(float(limits["vitamin_d_iu"]))
    return uls


@pytest.mark.parametrize("recipe_index", range(18))
def test_no_starter_recipe_exceeds_the_vitamin_d_daily_ul(recipe_index):
    uls = _daily_vitamin_d_uls()
    assert uls, "no vitamin D UL found in ul_by_demographic.json"
    lowest_ul = min(uls)

    recipes = RecipeDB(str(_STARTER), tag_repo_path=str(_TAGS)).get_all_recipes()
    assert len(recipes) == 18
    recipe = recipes[recipe_index]
    calc = NutritionCalculator(LocalIngredientProvider(NutritionDB(str(_REF))))
    assert calc.unresolved_ingredient_names(recipe) == []

    vitamin_d = calc.calculate_recipe_nutrition(recipe).micronutrients.vitamin_d_iu
    assert vitamin_d <= lowest_ul, f"{recipe.id} {recipe.name}: {vitamin_d:.0f} IU"
