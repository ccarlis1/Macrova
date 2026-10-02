"""§4.4 / Q2(d+a): committed ingredient nutrition table, coverage, plausibility, no silent zeros."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data_layer.models import Ingredient, Recipe
from src.data_layer.nutrition_db import NutritionDB
from src.ingestion.ingredient_cache import (
    check_nutrition_plausibility,
    NutritionPlausibilityError,
)
from src.nutrition.calculator import NutritionCalculator
from src.planning.converters import convert_recipes
from src.providers.local_provider import LocalIngredientProvider

_ROOT = Path(__file__).resolve().parents[1]
_REF = _ROOT / "data" / "reference" / "ingredient_nutrition.json"


def _load_recipe_ingredient_names(*paths: Path) -> set[str]:
    names: set[str] = set()
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        for recipe in data.get("recipes", []):
            for ing in recipe.get("ingredients", []):
                if ing.get("unit") == "to taste":
                    continue
                n = str(ing.get("name", "")).strip().lower()
                if n:
                    names.add(n)
    return names


def _table_names() -> set[str]:
    data = json.loads(_REF.read_text(encoding="utf-8"))
    names: set[str] = set()
    for ing in data["ingredients"]:
        names.add(str(ing["name"]).strip().lower())
        for alias in ing.get("aliases") or []:
            names.add(str(alias).strip().lower())
    return names


class TestCoverage:
    def test_committed_and_benchmark_ingredients_are_in_reference_table(self):
        needed = _load_recipe_ingredient_names(
            _ROOT / "evaluation" / "benchmark" / "recipes.json",
            _ROOT / "data" / "recipes" / "recipes.json",
            _ROOT / "data" / "recipes" / "recipes.json.example",
        )
        have = _table_names()
        missing = sorted(n for n in needed if n not in have)
        assert missing == [], f"ingredients missing from reference table: {missing}"


class TestPlausibility:
    def test_accepts_balanced_macros(self):
        check_nutrition_plausibility(
            calories=165, protein_g=31, carbs_g=0, fat_g=3.6, query_name="chicken breast"
        )

    def test_rejects_zero_kcal_with_carbs(self):
        with pytest.raises(NutritionPlausibilityError):
            check_nutrition_plausibility(
                calories=0, protein_g=1, carbs_g=14, fat_g=0.5, query_name="kiwi"
            )

    def test_rejects_pure_fat_for_non_oil_query(self):
        with pytest.raises(NutritionPlausibilityError):
            check_nutrition_plausibility(
                calories=884, protein_g=0, carbs_g=0, fat_g=100, query_name="oats"
            )

    def test_allows_pure_fat_for_oil_query(self):
        check_nutrition_plausibility(
            calories=884, protein_g=0, carbs_g=0, fat_g=100, query_name="olive oil"
        )


class TestNoSilentZeros:
    def test_convert_recipes_drops_unresolved(self):
        provider = LocalIngredientProvider(NutritionDB(str(_REF)))
        calc = NutritionCalculator(provider)
        recipes = [
            Recipe(
                id="ok",
                name="Ok",
                ingredients=[
                    Ingredient(name="chicken breast", quantity=100, unit="g"),
                ],
                cooking_time_minutes=5,
                instructions=[],
            ),
            Recipe(
                id="bad",
                name="Bad",
                ingredients=[
                    Ingredient(name="chicken breast", quantity=100, unit="g"),
                    Ingredient(name="not_in_table_xyz", quantity=50, unit="g"),
                ],
                cooking_time_minutes=5,
                instructions=[],
            ),
        ]
        log: list = []
        pool = convert_recipes(recipes, calc, unresolved_log=log)
        assert [r.id for r in pool] == ["ok"]
        assert len(log) == 1
        assert log[0]["recipe_id"] == "bad"
        assert "not_in_table_xyz" in log[0]["unresolved_ingredients"]

    def test_unresolved_ingredient_names_lists_gaps(self):
        provider = LocalIngredientProvider(NutritionDB(str(_REF)))
        calc = NutritionCalculator(provider)
        recipe = Recipe(
            id="r",
            name="R",
            ingredients=[
                Ingredient(name="chicken breast", quantity=100, unit="g"),
                Ingredient(name="missing_thing", quantity=10, unit="g"),
            ],
            cooking_time_minutes=1,
            instructions=[],
        )
        assert calc.unresolved_ingredient_names(recipe) == ["missing_thing"]
