"""API-path volume-unit conversion check (E2 / §4.4 units channel)."""

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


def _load_recipe(recipe_id: str) -> dict:
    data = json.loads(_RECIPES.read_text(encoding="utf-8"))
    for recipe in data["recipes"]:
        if recipe["id"] == recipe_id:
            return recipe
    raise KeyError(recipe_id)


def test_tbsp_cup_api_path_vs_hand_calculated_grams():
    """NutritionCalculator currently treats tbsp/cup quantities as grams.

    Hand-calculated (approximate culinary densities):
      - 2 tbsp yogurt ≈ 30 g (≈15 g/tbsp)
      - 1 cup tomato ≈ 180 g
      - 4 tbsp carrots ≈ 40 g (≈10 g/tbsp grated)

    The API path via ``_convert_quantity_to_grams`` returns the raw quantity for
    volume units (2 / 1 / 4). This documents the known units gap; fixing the
    converter is a separate follow-up.
    """
    provider = LocalIngredientProvider(NutritionDB(str(_REF)))
    calc = NutritionCalculator(provider)

    # recipe_007: 2 tbsp yogurt; recipe with cup/tbsp veg: recipe pasta sauce area
    yogurt = Ingredient(name="low fat greek yogurt", quantity=2.0, unit="tbsp")
    tomato = Ingredient(name="tomato", quantity=1.0, unit="cup")
    carrots = Ingredient(name="carrots", quantity=4.0, unit="tbsp")

    assert calc._convert_quantity_to_grams(yogurt) == pytest.approx(2.0)
    assert calc._convert_quantity_to_grams(tomato) == pytest.approx(1.0)
    assert calc._convert_quantity_to_grams(carrots) == pytest.approx(4.0)

    hand = {
        "yogurt_tbsp_g": 30.0,
        "tomato_cup_g": 180.0,
        "carrots_tbsp_g": 40.0,
    }
    api = {
        "yogurt_tbsp_g": calc._convert_quantity_to_grams(yogurt),
        "tomato_cup_g": calc._convert_quantity_to_grams(tomato),
        "carrots_tbsp_g": calc._convert_quantity_to_grams(carrots),
    }
    # Document the gap; do not assert equality until the converter is fixed.
    assert api["yogurt_tbsp_g"] < hand["yogurt_tbsp_g"]
    assert api["tomato_cup_g"] < hand["tomato_cup_g"]
    assert api["carrots_tbsp_g"] < hand["carrots_tbsp_g"]


def test_committed_recipe_007_uses_tbsp_unit():
    recipe = _load_recipe("recipe_007")
    units = {i["name"]: i["unit"] for i in recipe["ingredients"]}
    assert units.get("low fat greek yogurt") == "tbsp"
