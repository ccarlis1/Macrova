"""API-path volume-unit conversion check (E2 / §4.4 units channel).

Known gap, tracked as its own follow-up: ``NutritionCalculator._convert_quantity_to_grams``
returns the raw quantity for ``tbsp``/``tsp``/``cup``/``ml``, so 2 tbsp yogurt counts
as 2 g. The hand-calculated checks below are strict xfails: fixing the converter
makes them pass, which fails the run until the xfail marks are removed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data_layer.models import Ingredient
from src.data_layer.nutrition_db import NutritionDB
from src.nutrition.calculator import NutritionCalculator
from src.providers.local_provider import LocalIngredientProvider

_ROOT = Path(__file__).resolve().parents[1]
_RECIPES = _ROOT / "data" / "recipes" / "recipes.json"
_REF = _ROOT / "data" / "reference" / "ingredient_nutrition.json"


def _calculator() -> NutritionCalculator:
    return NutritionCalculator(LocalIngredientProvider(NutritionDB(str(_REF))))


# (name, quantity, unit, hand-calculated grams from culinary densities)
_HAND_GRAMS = [
    ("low fat greek yogurt", 2.0, "tbsp", 30.0),  # ~15 g/tbsp
    ("tomato", 1.0, "cup", 180.0),  # chopped
    ("carrots", 4.0, "tbsp", 40.0),  # ~10 g/tbsp grated
]


@pytest.mark.xfail(strict=True, reason="volume units are counted as grams on the API path (open follow-up)")
@pytest.mark.parametrize("name, qty, unit, grams", _HAND_GRAMS)
def test_volume_units_convert_to_hand_calculated_grams(name, qty, unit, grams):
    got = _calculator()._convert_quantity_to_grams(Ingredient(name=name, quantity=qty, unit=unit))
    assert got == pytest.approx(grams, rel=0.25)


def test_committed_recipe_007_uses_tbsp_unit():
    """Keeps a committed recipe on the volume path so the gap stays visible in production data."""
    data = json.loads(_RECIPES.read_text(encoding="utf-8"))
    recipe = next(r for r in data["recipes"] if r["id"] == "recipe_007")
    units = {i["name"]: i["unit"] for i in recipe["ingredients"]}
    assert units.get("low fat greek yogurt") == "tbsp"
