"""Sprint 2 BE-18: /api/v1/plan drops committed recipes that hide nutrients behind `to taste`.

The committed pool (data/recipes/recipes.json, read-only here) is planned as-is;
no quantities are edited. Each affected recipe must be named in
``warnings.nutrition`` with the ingredient that needs grams.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer.recipe_db import RecipeDB

COMMITTED_RECIPES = "data/recipes/recipes.json"

EXPECTED_DROPS = {
    "llm_0415c122c1511957": "cherry tomatoes (to taste: needs grams)",  # Quinoa Salad
    "llm_59834f6218eb974e": "rolled oats (to taste: needs grams)",  # Oatmeal with Fruits
    # Grilled Chicken with Vegetables (5 copies): fresh garlic is a vegetable, not a seasoning.
    "llm_26427200aaed5fee": "garlic (to taste: needs grams)",
    "llm_922a991802b00168": "garlic (to taste: needs grams)",
    "llm_b9f9293329997a31": "garlic (to taste: needs grams)",
    "llm_e404d7d8e053dacb": "garlic (to taste: needs grams)",
    "llm_ee4f05b19ed0ee4a": "garlic (to taste: needs grams)",
}


def test_plan_lists_committed_to_taste_recipes_in_nutrition_warnings(monkeypatch):
    monkeypatch.setattr("src.api.server.recipes_path", COMMITTED_RECIPES)
    recipe_ids = sorted(r.id for r in RecipeDB(COMMITTED_RECIPES).get_all_recipes())

    res = TestClient(app).post(
        "/api/v1/plan",
        json={
            "daily_calories": 2000,
            "daily_protein_g": 120.0,
            "daily_fat_g_min": 50.0,
            "daily_fat_g_max": 80.0,
            "schedule_days": [
                {
                    "day_index": 1,
                    "meals": [
                        {"index": 1, "busyness_level": 4},
                        {"index": 2, "busyness_level": 4},
                        {"index": 3, "busyness_level": 4},
                    ],
                }
            ],
            "days": 1,
            "recipe_ids": recipe_ids,
            "planning_mode": "deterministic",
        },
    )
    assert res.status_code == 200, res.text
    nutrition_warnings = res.json()["warnings"]["nutrition"]

    dropped = {
        rid: line
        for rid in EXPECTED_DROPS
        for line in nutrition_warnings
        if f"'{rid}'" in line
    }
    assert set(dropped) == set(EXPECTED_DROPS)
    for rid, reason in EXPECTED_DROPS.items():
        assert reason in dropped[rid]
    # Only to-taste drops: every other committed recipe resolves.
    assert len(nutrition_warnings) == len(EXPECTED_DROPS)
