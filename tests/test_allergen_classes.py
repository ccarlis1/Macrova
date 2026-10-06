"""C6 / Q10: allergen class expansion, coverage, and HC-1 agreement."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer.models import Ingredient, NutritionProfile, UserProfile
from src.llm.recipe_validator import validate_recipe_draft
from src.llm.schemas import RecipeDraft
from src.planning.allergens import (
    exclusions_for_dietary_flags,
    expand_allergy_terms,
    is_classified,
    unmatched_exclusion_terms,
)
from src.planning.converters import convert_profile
from src.planning.phase0_models import MealSlot, PlanningRecipe, PlanningUserProfile
from src.planning.phase1_state import validate_pinned_assignments
from src.planning.phase2_constraints import (
    ConstraintStateView,
    check_hc1_excluded_ingredients,
    _recipe_contains_excluded_ingredient,
)
from src.providers.ingredient_provider import IngredientDataProvider

_ROOT = Path(__file__).resolve().parents[1]


def _load_ingredient_names(*paths: Path) -> set[str]:
    names: set[str] = set()
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "recipes" in data:
            for recipe in data["recipes"]:
                for ing in recipe.get("ingredients", []):
                    n = str(ing.get("name", "")).strip().lower()
                    if n:
                        names.add(n)
        elif isinstance(data, dict) and "ingredients" in data:
            for ing in data["ingredients"]:
                n = str(ing.get("name") or ing.get("canonical_name") or "").strip().lower()
                if n:
                    names.add(n)
    return names


class TestClassExpansion:
    def test_peanuts_includes_peanut_butter(self):
        expanded = expand_allergy_terms(["peanuts"])
        assert "peanuts" in expanded
        assert "peanut butter" in expanded

    def test_dairy_includes_every_milk_member(self):
        table = json.loads(
            (_ROOT / "data/reference/allergen_classes.json").read_text(encoding="utf-8")
        )
        milk_members = {m.lower().strip() for m in table["classes"]["milk"]["members"]}
        expanded = set(expand_allergy_terms(["dairy"]))
        assert milk_members <= expanded
        assert "dairy" in expanded

    def test_egg_includes_eggs_and_yolk(self):
        expanded = expand_allergy_terms(["egg"])
        assert "egg" in expanded
        assert "eggs" in expanded
        assert "egg yolk" in expanded


class TestNoFalsePositives:
    def test_egg_allergy_does_not_exclude_eggplant(self):
        profile = convert_profile(
            UserProfile(
                daily_calories=2000,
                daily_protein_g=100,
                daily_fat_g=(50, 70),
                daily_carbs_g=200,
                schedule={"2": 2},
                liked_foods=[],
                disliked_foods=[],
                allergies=["egg"],
            ),
            days=1,
        )
        recipe = PlanningRecipe(
            id="r_eggplant",
            name="Eggplant bowl",
            ingredients=[Ingredient(name="eggplant", quantity=100, unit="g")],
            cooking_time_minutes=10,
            nutrition=NutritionProfile(200, 5, 5, 20),
        )
        assert _recipe_contains_excluded_ingredient(recipe, profile.excluded_ingredients) is False

    def test_butter_dislike_does_not_exclude_peanut_butter(self):
        profile = convert_profile(
            UserProfile(
                daily_calories=2000,
                daily_protein_g=100,
                daily_fat_g=(50, 70),
                daily_carbs_g=200,
                schedule={"2": 2},
                liked_foods=[],
                disliked_foods=["butter"],
                allergies=[],
            ),
            days=1,
        )
        assert profile.excluded_ingredients == ["butter"]
        recipe = PlanningRecipe(
            id="r_pb",
            name="PB toast",
            ingredients=[Ingredient(name="peanut butter", quantity=30, unit="g")],
            cooking_time_minutes=5,
            nutrition=NutritionProfile(200, 8, 16, 6),
        )
        assert _recipe_contains_excluded_ingredient(recipe, profile.excluded_ingredients) is False

    def test_dislikes_stay_exact_dairy_does_not_expand(self):
        profile = convert_profile(
            UserProfile(
                daily_calories=2000,
                daily_protein_g=100,
                daily_fat_g=(50, 70),
                daily_carbs_g=200,
                schedule={"2": 2},
                liked_foods=[],
                disliked_foods=["dairy"],
                allergies=[],
            ),
            days=1,
        )
        assert profile.excluded_ingredients == ["dairy"]
        recipe = PlanningRecipe(
            id="r_cheese",
            name="Cheese plate",
            ingredients=[Ingredient(name="sharp cheddar cheese", quantity=50, unit="g")],
            cooking_time_minutes=5,
            nutrition=NutritionProfile(200, 12, 16, 1),
        )
        assert _recipe_contains_excluded_ingredient(recipe, profile.excluded_ingredients) is False


class TestCoverage:
    def test_committed_and_benchmark_ingredients_are_classified(self):
        names = _load_ingredient_names(
            _ROOT / "evaluation/benchmark/recipes.json",
            _ROOT / "data/recipes/recipes.json.example",
            _ROOT / "data/ingredients/custom_ingredients.json.example",
        )
        missing = sorted(n for n in names if not is_classified(n))
        assert missing == [], f"unclassified ingredients: {missing}"

    def test_intent_excluded_is_covered_by_expansion(self):
        scenarios = json.loads(
            (_ROOT / "evaluation/benchmark/scenarios.json").read_text(encoding="utf-8")
        )["scenarios"]
        for sc in scenarios:
            intent = sc["profile"].get("intent_excluded_ingredients")
            if not intent:
                continue
            terms = sc["profile"].get("excluded_ingredients", [])
            expanded = set(expand_allergy_terms(terms)) | set(
                exclusions_for_dietary_flags(sc["profile"].get("dietary_flags") or [])
            )
            missing = sorted(
                n.strip().lower() for n in intent if n.strip().lower() not in expanded
            )
            assert missing == [], f"{sc['id']} missing from expansion: {missing}"


class TestMatcherAgreement:
    def test_pin_validation_and_hc1_agree(self):
        recipe = PlanningRecipe(
            id="r_pb",
            name="PB toast",
            ingredients=[Ingredient(name="peanut butter", quantity=30, unit="g")],
            cooking_time_minutes=5,
            nutrition=NutritionProfile(200, 8, 16, 6),
        )
        excluded = expand_allergy_terms(["peanuts"])
        profile = PlanningUserProfile(
            daily_calories=2000,
            daily_protein_g=100,
            daily_fat_g=(50.0, 70.0),
            daily_carbs_g=200.0,
            schedule=[[MealSlot("08:00", 2, "breakfast")]],
            excluded_ingredients=excluded,
            pinned_assignments={(1, 0): "r_pb"},
        )
        pin = validate_pinned_assignments(profile, {"r_pb": recipe}, 1)
        hc1_allowed = check_hc1_excluded_ingredients(
            recipe,
            profile.schedule[0][0],
            0,
            ConstraintStateView(daily_trackers={}),
            profile,
            None,
        )
        assert pin.success is False
        assert pin.failed_hc == "HC-1"
        assert hc1_allowed is False


class _Provider(IngredientDataProvider):
    usda_capable = True

    def __init__(self, table):
        self.table = table

    def get_ingredient_info(self, name):
        key = name.lower()
        if key not in self.table:
            return None
        return {"name": key, "per_100g": self.table[key]}

    def resolve_all(self, names):
        return None


def test_validator_rejects_unclassified_ingredient():
    table = {
        "chicken breast": {"calories": 165, "protein_g": 31, "fat_g": 3.6, "carbs_g": 0},
        "mystery spice blend xyz": {"calories": 100, "protein_g": 1, "fat_g": 1, "carbs_g": 20},
    }
    draft = RecipeDraft.model_validate(
        {
            "name": "Mystery bowl",
            "ingredients": [
                {"name": "chicken breast", "quantity": 200.0, "unit": "g"},
                {"name": "mystery spice blend xyz", "quantity": 10.0, "unit": "g"},
            ],
            "instructions": ["Mix."],
        }
    )
    ok, res = validate_recipe_draft(draft, _Provider(table))
    assert ok is False
    assert res.error_code == "UNCLASSIFIED_INGREDIENT"


def test_unmatched_term_helper():
    assert unmatched_exclusion_terms(["unobtainium"], [], ["eggs"]) == ["unobtainium"]
    assert unmatched_exclusion_terms(["egg"], [], ["eggs"]) == []
    assert unmatched_exclusion_terms([], ["eggs"], ["eggs"]) == []
    assert unmatched_exclusion_terms([], ["unobtainium"], ["eggs"]) == ["unobtainium"]


def test_api_plan_warns_on_unmatched_allergy(tmp_path, monkeypatch):
    recipes_path = tmp_path / "recipes.json"
    recipes_path.write_text(
        json.dumps(
            {
                "recipes": [
                    {
                        "id": "r1",
                        "name": "Rice bowl",
                        "ingredients": [
                            {"name": "cream of rice", "quantity": 100, "unit": "g"}
                        ],
                        "cooking_time_minutes": 5,
                        "instructions": ["Cook."],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    ingredients_path = tmp_path / "ingredients.json"
    ingredients_path.write_text(
        json.dumps(
            {
                "ingredients": [
                    {
                        "name": "cream of rice",
                        "per_100g": {
                            "calories": 370,
                            "protein_g": 7.5,
                            "fat_g": 0.5,
                            "carbs_g": 82.0,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.api.server.recipes_path", str(recipes_path))
    monkeypatch.setattr("src.api.server.ingredients_path", str(ingredients_path))

    client = TestClient(app)
    response = client.post(
        "/api/v1/plan",
        json={
            "daily_calories": 2000,
            "daily_protein_g": 100,
            "daily_fat_g_min": 50,
            "daily_fat_g_max": 70,
            "days": 1,
            "schedule_days": [
                {
                    "day_index": 1,
                    "meals": [
                        {"index": 1, "busyness_level": 2, "tags": ["breakfast"]},
                    ],
                    "workouts": [],
                }
            ],
            "liked_foods": [],
            "disliked_foods": [],
            "allergies": ["unobtainium"],
            "recipe_ids": ["r1"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    warnings = body.get("warnings") or {}
    exclusion_warnings = warnings.get("exclusions") or []
    assert any("unobtainium" in str(w) for w in exclusion_warnings)
