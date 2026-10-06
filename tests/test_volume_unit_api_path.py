"""API-path volume-unit conversion (§4.4 units channel).

``NutritionCalculator.to_grams`` converts via each ingredient's ``grams_per_unit``
(and explicit serving weights). Unknown units raise ``IngredientNotFoundError``
so the recipe leaves the pool with ``warnings.nutrition``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from src.data_layer.models import Ingredient, Recipe
from src.data_layer.nutrition_db import NutritionDB
from src.nutrition.calculator import NutritionCalculator
from src.planning.converters import convert_recipes
from src.providers.local_provider import LocalIngredientProvider

_ROOT = Path(__file__).resolve().parents[1]
_RECIPES = _ROOT / "data" / "recipes" / "recipes.json"
_BENCH_RECIPES = _ROOT / "evaluation" / "benchmark" / "recipes.json"
_REF = _ROOT / "data" / "reference" / "ingredient_nutrition.json"


def _calculator() -> NutritionCalculator:
    return NutritionCalculator(LocalIngredientProvider(NutritionDB(str(_REF))))


def _info_for(name: str) -> Dict[str, Any]:
    return _calculator().provider.get_ingredient_info(name) or {}


# (name, quantity, unit, expected grams from ingredient_nutrition.grams_per_unit)
_TABLE_GRAMS = [
    ("low fat greek yogurt", 2.0, "tbsp", 30.0),  # 15 g/tbsp
    ("tomato", 1.0, "cup", 180.0),
    ("carrots", 4.0, "tbsp", 28.0),  # 7 g/tbsp
]


@pytest.mark.parametrize("name, qty, unit, grams", _TABLE_GRAMS)
def test_volume_units_convert_to_table_grams(name, qty, unit, grams):
    calc = _calculator()
    ingredient = Ingredient(name=name, quantity=qty, unit=unit)
    got = calc.to_grams(ingredient, _info_for(name))
    assert got == pytest.approx(grams)


def test_committed_recipe_007_uses_tbsp_unit():
    """Keeps a committed recipe on the volume path so conversion stays covered."""
    data = json.loads(_RECIPES.read_text(encoding="utf-8"))
    recipe = next(r for r in data["recipes"] if r["id"] == "recipe_007")
    units = {i["name"]: i["unit"] for i in recipe["ingredients"]}
    assert units.get("low fat greek yogurt") == "tbsp"


def _ingredient_unit_pairs(path: Path) -> List[tuple[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pairs: set[tuple[str, str]] = set()
    for recipe in data["recipes"]:
        for ing in recipe["ingredients"]:
            unit = ing.get("unit", "")
            if unit == "to taste" or "to taste" in unit.lower():
                continue
            pairs.add((ing["name"], unit))
    return sorted(pairs)


@pytest.mark.parametrize(
    "path",
    [_RECIPES, _BENCH_RECIPES],
    ids=["production", "benchmark"],
)
def test_every_committed_ingredient_unit_converts(path: Path):
    calc = _calculator()
    for name, unit in _ingredient_unit_pairs(path):
        info = calc.provider.get_ingredient_info(name)
        assert info is not None, f"missing nutrition for {name!r}"
        grams = calc.to_grams(Ingredient(name=name, quantity=1.0, unit=unit), info)
        assert grams > 0.0


def test_unconvertible_unit_drops_recipe_with_nutrition_warning():
    """U1 a: no grams_per_unit for cup → recipe leaves the pool; warning names unit."""
    calc = _calculator()
    # quinoa is in the table with only g; cup has no conversion
    recipe = Recipe(
        id="r_bad_unit",
        name="Cup of quinoa",
        ingredients=[
            Ingredient(name="quinoa", quantity=1.0, unit="cup", is_to_taste=False),
        ],
        cooking_time_minutes=10,
        instructions=[],
    )
    unresolved = calc.unresolved_ingredient_names(recipe)
    assert any("quinoa" in u and "cup" in u for u in unresolved)

    log: List[Dict[str, Any]] = []
    pool = convert_recipes([recipe], calc, unresolved_log=log)
    assert pool == []
    assert log
    names = log[0]["unresolved_ingredients"]
    assert any("quinoa" in n and "cup" in n for n in names)


def test_api_provider_volume_unit_is_unresolved():
    """USDA/api path has no grams_per_unit → volume unit is unresolved (U1 a)."""
    provider = MagicMock()
    provider.get_ingredient_info.return_value = {
        "name": "quinoa",
        "per_100g": {
            "calories": 120.0,
            "protein_g": 4.0,
            "fat_g": 2.0,
            "carbs_g": 21.0,
        },
        # no grams_per_unit
    }
    calc = NutritionCalculator(provider)
    recipe = Recipe(
        id="r_api_vol",
        name="API volume",
        ingredients=[
            Ingredient(name="quinoa", quantity=1.0, unit="cup", is_to_taste=False),
        ],
        cooking_time_minutes=5,
        instructions=[],
    )
    unresolved = calc.unresolved_ingredient_names(recipe)
    assert any("no gram conversion" in u and "cup" in u for u in unresolved)
