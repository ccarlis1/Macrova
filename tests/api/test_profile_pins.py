"""BE-15: profile pin CRUD + plan interactions (including batch metadata precedence)."""

import yaml
from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer.meal_prep import BatchAssignment, MealPrepBatch
from src.data_layer.models import Ingredient, Recipe
from src.planning.phase0_models import Assignment, DailyTracker
from src.planning.phase10_reporting import MealPlanResult


class _DummyRecipeDB:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def get_recipe_by_id(self, recipe_id: str):
        if recipe_id in {"known-recipe", "known-recipe-2"}:
            return object()
        return None


def _write_profile(path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "nutrition_goals": {
                    "daily_calories": 2200,
                    "daily_protein_g": 140,
                    "daily_fat_g": {"min": 60, "max": 90},
                },
                "preferences": {"liked_foods": [], "disliked_foods": [], "allergies": []},
            }
        ),
        encoding="utf-8",
    )


def test_profile_pins_crud_idempotent_and_clear(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr("src.api.server.RecipeDB", _DummyRecipeDB)

    client = TestClient(app)

    created = client.put("/api/v1/profile/pins/0/1", json={"recipe_id": "known-recipe"})
    assert created.status_code == 200
    assert created.json()["pin"] == {
        "day_index": 0,
        "slot_index": 1,
        "recipe_id": "known-recipe",
    }

    duplicate = client.put("/api/v1/profile/pins/0/1", json={"recipe_id": "known-recipe"})
    assert duplicate.status_code == 200
    assert duplicate.json() == created.json()

    updated = client.put("/api/v1/profile/pins/0/1", json={"recipe_id": "known-recipe-2"})
    assert updated.status_code == 200
    assert updated.json()["pin"]["recipe_id"] == "known-recipe-2"

    _ = client.put("/api/v1/profile/pins/1/0", json={"recipe_id": "known-recipe"})
    listed = client.get("/api/v1/profile/pins")
    assert listed.status_code == 200
    assert listed.json()["pins"] == [
        {"day_index": 0, "slot_index": 1, "recipe_id": "known-recipe-2"},
        {"day_index": 1, "slot_index": 0, "recipe_id": "known-recipe"},
    ]

    cleared_one = client.delete("/api/v1/profile/pins/0/1")
    assert cleared_one.status_code == 200
    assert cleared_one.json() == {
        "deleted": True,
        "pin": {"day_index": 0, "slot_index": 1, "recipe_id": "known-recipe-2"},
    }

    clear_absent = client.delete("/api/v1/profile/pins/0/1")
    assert clear_absent.status_code == 200
    assert clear_absent.json() == {"deleted": False, "pin": None}

    cleared_all = client.delete("/api/v1/profile/pins")
    assert cleared_all.status_code == 200
    assert cleared_all.json() == {"cleared_count": 1}
    assert client.get("/api/v1/profile/pins").json() == {"pins": []}

    saved = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    assert saved["pins"] == []


class _DummyProvider:
    usda_capable = True

    def resolve_all(self, _ingredient_names):
        return None

    def get_ingredient_info(self, name: str):
        return {
            "name": name,
            "per_100g": {
                "calories": 140.0,
                "protein_g": 13.0,
                "fat_g": 10.0,
                "carbs_g": 1.0,
            },
        }


class _RecipeDBPinAndLocked:
    def __init__(self, *_a, **_k) -> None:
        pass

    def get_recipe_by_id(self, recipe_id: str):
        if recipe_id in {"known-recipe", "locked-recipe"}:
            return object()
        return None

    def get_all_recipes(self):
        return [
            Recipe(
                id="known-recipe",
                name="Known Recipe",
                ingredients=[Ingredient("egg", 2.0, "large", is_to_taste=False)],
                cooking_time_minutes=5,
                instructions=["cook"],
            ),
            Recipe(
                id="locked-recipe",
                name="Locked Recipe",
                ingredients=[Ingredient("egg", 2.0, "large", is_to_taste=False)],
                cooking_time_minutes=5,
                instructions=["cook"],
            ),
        ]


def test_plan_meal_source_batch_lock_overrides_pin_on_same_slot(tmp_path, monkeypatch):
    """When batch assignment and pin share a slot, planned meal metadata reflects the batch lock."""
    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr("src.api.server.RecipeDB", _RecipeDBPinAndLocked)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda *_a, **_k: object())
    monkeypatch.setattr(
        "src.api.server.LocalIngredientProvider", lambda *_a, **_k: _DummyProvider()
    )

    batch = MealPrepBatch(
        id="batch-precedence-1",
        recipe_id="locked-recipe",
        total_servings=4,
        cook_date="2026-04-27",
        assignments=[BatchAssignment(day_index=0, slot_index=0, servings=2.0)],
        status="planned",
    )

    class _Repo:
        def list_active(self):
            return [batch]

    monkeypatch.setattr("src.api.server.MealPrepBatchRepository", lambda *_a, **_k: _Repo())
    monkeypatch.setattr(
        "src.api.server.plan_meals",
        lambda *_a, **_k: MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[Assignment(0, 0, "locked-recipe", 0)],
            daily_trackers={
                0: DailyTracker(
                    calories_consumed=100.0,
                    protein_consumed=10.0,
                    fat_consumed=5.0,
                    carbs_consumed=10.0,
                    slots_assigned=1,
                    slots_total=2,
                )
            },
            weekly_tracker=None,
            report={},
            stats=None,
        ),
    )

    client = TestClient(app)
    assert (
        client.put(
            "/api/v1/profile/pins/0/0",
            json={"recipe_id": "known-recipe"},
        ).status_code
        == 200
    )
    resp = client.post(
        "/api/v1/plan",
        json={
            "daily_calories": 2200,
            "daily_protein_g": 140.0,
            "daily_fat_g_min": 60.0,
            "daily_fat_g_max": 90.0,
            "liked_foods": [],
            "disliked_foods": [],
            "allergies": [],
            "days": 1,
            "ingredient_source": "local",
            "schedule": {"08:00": 3, "12:00": 3},
        },
    )
    assert resp.status_code == 200
    meal = resp.json()["daily_plans"][0]["meals"][0]
    assert meal["source"] == "meal_prep_batch"
    assert meal["recipe_id"] == "locked-recipe"
    assert meal["batch_id"] == "batch-precedence-1"
    assert meal["servings"] == 2.0


def test_profile_pins_unknown_recipe_id_returns_structured_not_found(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr("src.api.server.RecipeDB", _DummyRecipeDB)

    client = TestClient(app)
    response = client.put("/api/v1/profile/pins/0/0", json={"recipe_id": "missing-recipe"})
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "RECIPE_NOT_FOUND"
