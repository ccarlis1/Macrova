import json
from pathlib import Path
import tempfile

import pytest

from src.data_layer.recipe_db import RecipeDB
from src.llm.pipeline import generate_validate_persist_recipes
from src.nutrition.calculator import NutritionCalculator
from src.planning.converters import convert_recipes, extract_ingredient_names
from src.planning.phase0_models import MealSlot, PlanningUserProfile
from src.planning.planner import plan_meals
from src.providers.ingredient_provider import IngredientDataProvider


class DummyLLMClient:
    """Mock LLM boundary: returns deterministic JSON envelope only."""

    def generate_json(self, *, system_prompt, user_prompt, schema_name, temperature=0.0):
        assert schema_name == "RecipeDraftEnvelope"
        assert temperature == 0.0
        # Generate exactly one draft (count=1).
        return {
            "drafts": [
                {
                    "name": "LLM Recipe",
                    "ingredients": [
                        {"name": "chicken breast", "quantity": 200.0, "unit": "g"},
                        {"name": "white rice", "quantity": 250.0, "unit": "g"},
                    ],
                    "instructions": ["Cook it.", "Serve it."],
                }
            ]
        }


class FakeUSDAProvider(IngredientDataProvider):
    """Mock USDA-backed provider boundary: deterministic per-100g nutrition."""

    usda_capable = True

    def __init__(self, *, per_100g_by_name):
        self._per_100g_by_name = per_100g_by_name

    def get_ingredient_info(self, name: str):
        key = str(name).lower().strip()
        if key not in self._per_100g_by_name:
            return None
        return {"name": key, "per_100g": self._per_100g_by_name[key]}

    def resolve_all(self, ingredient_names):
        # No-op: data is already in memory in this fake provider.
        return None


def test_vertical_slice_llm_to_planner_minimal():
    chicken = {"calories": 165.0, "protein_g": 31.0, "fat_g": 3.6, "carbs_g": 0.0}
    rice = {"calories": 130.0, "protein_g": 2.7, "fat_g": 0.3, "carbs_g": 28.0}

    provider = FakeUSDAProvider(
        per_100g_by_name={
            "chicken breast": chicken,
            "white rice": rice,
        }
    )
    client = DummyLLMClient()

    with tempfile.TemporaryDirectory() as td:
        recipes_path = str(Path(td) / "recipes.json")

        summary = generate_validate_persist_recipes(
            context={},
            count=1,
            recipes_path=recipes_path,
            provider=provider,
            client=client,
        )

        assert summary["requested"] == 1
        assert summary["generated"] == 1
        assert summary["accepted"] == 1
        assert summary["rejected"] == []
        assert len(summary["persisted_ids"]) == 1
        persisted_id = summary["persisted_ids"][0]

        # Load persisted recipe via RecipeDB.
        recipe_db = RecipeDB(recipes_path)
        all_recipes = recipe_db.get_all_recipes()
        assert any(r.id == persisted_id for r in all_recipes)

        # Convert with NutritionCalculator backed by the same fake provider.
        # (Planner uses these precomputed nutrition values only.)
        provider.resolve_all(extract_ingredient_names(all_recipes))
        recipe_pool = convert_recipes(all_recipes, NutritionCalculator(provider))

        # Build a minimal 1-day schedule with 1 slot.
        slot = MealSlot(time="12:00", busyness_level=2, meal_type="lunch")
        schedule = [[slot]]

        # Expected nutrition from fake provider + recipe ingredients:
        # chicken 200g: cal 330, protein 62, fat 7.2, carbs 0
        # rice 250g: cal 325, protein 6.75, fat 0.75, carbs 70
        # total: cal 655, protein 68.75, fat 7.95, carbs 70
        profile = PlanningUserProfile(
            daily_calories=655,
            daily_protein_g=68.75,
            daily_fat_g=(7.0, 8.5),
            daily_carbs_g=70.0,
            schedule=schedule,
            excluded_ingredients=[],
            liked_foods=[],
            demographic="adult_male",
            pinned_assignments={},
            micronutrient_targets={},
            upper_limits_overrides=None,
            activity_schedule={},
            enable_primary_carb_downscaling=False,
        )

        result = plan_meals(profile, recipe_pool, days=1)
        assert result.success is True
        assert result.plan is not None

