from fastapi.testclient import TestClient

from src.api.server import app
from src.config.llm_settings import LLMSettings
from src.data_layer.models import Ingredient, NutritionProfile
from src.planning.phase0_models import (
    Assignment,
    DailyTracker,
    PlanningRecipe,
)
from src.planning.phase10_reporting import MealPlanResult


class DummyRecipeDB:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def get_all_recipes(self):
        return []


class DummyProvider:
    def resolve_all(self, ingredient_names):
        return None


def test_planner_regression_llm_disabled_golden_json(monkeypatch):
    # Disable any external-data effects by stubbing recipe conversion and the planner.
    recipe = PlanningRecipe(
        id="r1",
        name="Test Chicken",
        ingredients=[
            Ingredient(
                name="chicken breast",
                quantity=100.0,
                unit="g",
                normalized_unit="g",
                normalized_quantity=100.0,
            )
        ],
        cooking_time_minutes=10,
        nutrition=NutritionProfile(
            calories=500.0,
            protein_g=50.0,
            fat_g=20.0,
            carbs_g=100.0,
            micronutrients=None,
        ),
        primary_carb_contribution=None,
        primary_carb_source=None,
    )

    daily_tracker = DailyTracker(
        calories_consumed=1000.0,
        protein_consumed=100.0,
        fat_consumed=40.0,
        carbs_consumed=200.0,
    )

    expected_golden_json = {
        "success": True,
        "termination_code": "TC-1",
        "days": 1,
        "daily_plans": [
            {
                "day": 1,
                "meals": [
                    {
                        "recipe_id": "r1",
                        "name": "Test Chicken",
                        "meal_type": "breakfast",
                        "cooking_time_minutes": 10,
                        "ingredients": ["100 g chicken breast"],
                        "nutrition": {
                            "calories": 500.0,
                            "protein_g": 50.0,
                            "fat_g": 20.0,
                            "carbs_g": 100.0,
                        },
                        "busyness_level": 2,
                    },
                    {
                        "recipe_id": "r1",
                        "name": "Test Chicken",
                        "meal_type": "lunch",
                        "cooking_time_minutes": 10,
                        "ingredients": ["100 g chicken breast"],
                        "nutrition": {
                            "calories": 500.0,
                            "protein_g": 50.0,
                            "fat_g": 20.0,
                            "carbs_g": 100.0,
                        },
                        "busyness_level": 3,
                    },
                ],
                "totals": {
                    "calories": 1000.0,
                    "protein_g": 100.0,
                    "fat_g": 40.0,
                    "carbs_g": 200.0,
                },
            }
        ],
        "warnings": {
            "schedule_migration": {
                "deprecated": True,
                "message": (
                    "Legacy flat schedule (HH:MM -> int) is deprecated; use "
                    "schedule_days with MealSlot and WorkoutSlot."
                ),
            },
        },
        "goals": {
            "daily_calories": 2400,
            "daily_protein_g": 150.0,
            "daily_fat_g_min": 50.0,
            "daily_fat_g_max": 100.0,
            "daily_carbs_g": 281.25,
        },
    }

    monkeypatch.setattr("src.api.server.RecipeDB", DummyRecipeDB)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda _: object())
    monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda _: DummyProvider())

    # Avoid needing nutrition DB contents by stubbing ingredient name extraction.
    monkeypatch.setattr("src.api.server.extract_ingredient_names", lambda recipes: [])

    monkeypatch.setattr(
        "src.api.server.convert_recipes",
        lambda recipes, calculator: [recipe],
    )

    def _fake_plan_meals(profile, recipe_pool, days):
        return MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[
                Assignment(day_index=0, slot_index=0, recipe_id="r1"),
                Assignment(day_index=0, slot_index=1, recipe_id="r1"),
            ],
            daily_trackers={0: daily_tracker},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
            warning=None,
        )

    monkeypatch.setattr("src.api.server.plan_meals", _fake_plan_meals)

    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="",
            model="",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=False,
        ),
    )

    client = TestClient(app)
    payload = {
        "daily_calories": 2400,
        "daily_protein_g": 150.0,
        "daily_fat_g_min": 50.0,
        "daily_fat_g_max": 100.0,
        "schedule": {"07:00": 2, "12:00": 3, "18:00": 3},
        "liked_foods": ["egg"],
        "disliked_foods": ["mushroom"],
        "allergies": [],
        "days": 1,
        "ingredient_source": "local",
        "micronutrient_goals": None,
    }

    resp_disabled_1 = client.post("/api/plan", json=payload)
    resp_disabled_2 = client.post("/api/plan", json=payload)
    assert resp_disabled_1.status_code == 200
    assert resp_disabled_2.status_code == 200

    out1 = resp_disabled_1.json()
    out2 = resp_disabled_2.json()
    assert out1 == out2
    assert out1 == expected_golden_json

