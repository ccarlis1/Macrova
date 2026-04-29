import yaml
from fastapi.testclient import TestClient

from src.api.server import app
from src.config.llm_settings import LLMSettings
from src.planning.phase0_models import MealSlot, PlanningBatchLock, PlanningUserProfile
from src.planning.phase10_reporting import MealPlanResult
from src.planning.planner import _merge_batch_locks_into_pins


class _DummyRecipeDB:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def get_recipe_by_id(self, recipe_id: str):
        if recipe_id in {"known-recipe", "locked-recipe"}:
            return object()
        return None

    def get_all_recipes(self):
        return []


class _DummyProvider:
    usda_capable = True

    def resolve_all(self, _ingredient_names):
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


def _plan_payload():
    return {
        "daily_calories": 2200,
        "daily_protein_g": 140.0,
        "daily_fat_g_min": 60.0,
        "daily_fat_g_max": 90.0,
        "schedule": {"08:00": 3, "12:00": 3},
        "liked_foods": [],
        "disliked_foods": [],
        "allergies": [],
        "days": 1,
        "ingredient_source": "local",
    }


def test_plan_hydrates_pins_and_clears_remove_effect(tmp_path, monkeypatch):
    profile_path = tmp_path / "user_profile.yaml"
    _write_profile(profile_path)
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(profile_path))
    monkeypatch.setattr("src.api.server.RecipeDB", _DummyRecipeDB)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda *_args, **_kwargs: _DummyProvider())
    monkeypatch.setattr(
        "src.api.server.load_llm_settings",
        lambda: LLMSettings(
            api_key="dummy",
            model="dummy",
            timeout_seconds=1.0,
            max_retries=0,
            rate_limit_qps=1.0,
            enabled=True,
        ),
    )

    captured: list[dict] = []

    def _fake_plan_meals(profile, _pool, _days):
        captured.append(dict(profile.pinned_assignments))
        return MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        )

    monkeypatch.setattr("src.api.server.plan_meals", _fake_plan_meals)

    client = TestClient(app)
    assert client.put("/api/v1/profile/pins/0/0", json={"recipe_id": "known-recipe"}).status_code == 200

    first_plan = client.post("/api/v1/plan", json=_plan_payload())
    assert first_plan.status_code == 200
    assert captured[-1] == {(1, 0): "known-recipe"}

    assert client.delete("/api/v1/profile/pins/0/0").status_code == 200
    second_plan = client.post("/api/v1/plan", json=_plan_payload())
    assert second_plan.status_code == 200
    assert captured[-1] == {}

    assert client.put("/api/v1/profile/pins/0/0", json={"recipe_id": "known-recipe"}).status_code == 200
    assert client.put("/api/v1/profile/pins/0/1", json={"recipe_id": "known-recipe"}).status_code == 200
    assert client.delete("/api/v1/profile/pins").status_code == 200
    third_plan = client.post("/api/v1/plan", json=_plan_payload())
    assert third_plan.status_code == 200
    assert captured[-1] == {}


def test_batch_lock_precedence_still_wins_over_pin():
    profile = PlanningUserProfile(
        daily_calories=2200,
        daily_protein_g=140.0,
        daily_fat_g=(60.0, 90.0),
        daily_carbs_g=200.0,
        schedule=[[MealSlot(time="08:00", busyness_level=3, meal_type="breakfast")]],
        pinned_assignments={(1, 0): "known-recipe"},
        batch_locks=[
            PlanningBatchLock(
                batch_id="batch-1",
                recipe_id="locked-recipe",
                day_index=0,
                slot_index=0,
                servings=1.0,
            )
        ],
    )
    _early_failure, effective_pins, _conflicts, _mismatches = _merge_batch_locks_into_pins(profile, [])
    assert effective_pins[(1, 0)] == "locked-recipe"
