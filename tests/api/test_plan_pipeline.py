"""build_plan_inputs / format_plan_response: the plan pipeline without user files.

The MCP server plans from recipes, tags, pins and batches sent in the call. These
tests check that the in-memory path matches ``POST /api/v1/plan`` and that it reads
none of the stores the HTTP route loads from.
"""

from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

from src.api import server
from src.api.server import (
    DEFAULT_TAG_PATH,
    PlanRequest,
    PlanResponse,
    PlanTagData,
    app,
    build_plan_inputs,
    format_plan_response,
    ingredients_path,
    load_plan_tag_data,
    recipes_path,
)
from src.data_layer.meal_prep import BatchAssignment, MealPrepBatch
from src.data_layer.models import Ingredient, ProfilePin, Recipe
from src.data_layer.nutrition_db import NutritionDB
from src.data_layer.recipe_db import RecipeDB
from src.llm.schemas import RecipeTagsJson
from src.models.legacy_schedule_migration import merge_schedule_warnings_into_result
from src.planning.orchestrator import ParityPlanContext, planning_batch_locks_from_batches
from src.planning.planner import plan_meals
from src.providers.local_provider import LocalIngredientProvider

PAYLOAD = {
    "daily_calories": 2200,
    "daily_protein_g": 140.0,
    "daily_fat_g_min": 60.0,
    "daily_fat_g_max": 90.0,
    "schedule": {"08:00": 3, "12:00": 3, "18:00": 3},
    "liked_foods": [],
    "disliked_foods": [],
    "allergies": [],
    "days": 2,
    "ingredient_source": "local",
}
PIN = ProfilePin(day_index=0, slot_index=0, recipe_id="recipe_007")
BATCH = MealPrepBatch(
    id="batch-1",
    recipe_id="recipe_006",
    total_servings=2,
    cook_date="2026-11-02",
    # One day only: HC-8 rejects a batch on consecutive non-workout days (FM-3).
    assignments=[BatchAssignment(day_index=0, slot_index=2)],
    status="active",
)


@pytest.fixture
def profile_env(tmp_path, monkeypatch):
    path = tmp_path / "user_profile.yaml"
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
    monkeypatch.setenv("NUTRITION_USER_PROFILE_PATH", str(path))


def test_in_memory_pipeline_matches_plan_route(profile_env, monkeypatch):
    monkeypatch.setattr(
        "src.api.server.hydrate_parity_plan_context",
        lambda seed=None: ParityPlanContext(
            active_batches=[BATCH],
            persisted_pins=[PIN],
            seed=None,
            batch_locks=planning_batch_locks_from_batches([BATCH]),
        ),
    )
    resp = TestClient(app).post("/api/v1/plan", json=PAYLOAD)
    assert resp.status_code == 200, resp.text
    from_route = resp.json()

    plan_request = PlanRequest(**PAYLOAD)
    user_profile, sched_warnings = server._build_user_profile(plan_request, persisted_pins=[PIN])
    inputs = build_plan_inputs(
        user_profile=user_profile,
        days=PAYLOAD["days"],
        recipes=RecipeDB(recipes_path).get_all_recipes(),
        tag_data=load_plan_tag_data(DEFAULT_TAG_PATH),
        tag_preferences=plan_request,
        provider=LocalIngredientProvider(NutritionDB(ingredients_path)),
        pins=[PIN],
        batches=[BATCH],
        keep_batch_recipes=True,
    )
    result = plan_meals(inputs.planning_profile, inputs.recipe_pool, PAYLOAD["days"])
    out = format_plan_response(
        result, inputs, user_profile=user_profile, days=PAYLOAD["days"], pins=[PIN], batches=[BATCH]
    )
    merge_schedule_warnings_into_result(out, sched_warnings, deprecated_legacy=True)
    in_memory = PlanResponse.model_validate(out).model_dump(mode="json", exclude_none=True)

    assert in_memory == from_route
    # The pin and the batch both reached the planner.
    first_day = {m["slot_index"]: m for m in from_route["daily_plans"][0]["meals"]}
    assert first_day[0]["recipe_id"] == "recipe_007"
    assert first_day[2]["batch_id"] == "batch-1"


class _Provider:
    def resolve_all(self, _names):
        return None

    def get_ingredient_info(self, name):
        return {"name": name, "per_100g": {"calories": 200.0, "protein_g": 20.0, "fat_g": 8.0, "carbs_g": 12.0}}


def _refuse(*_a, **_k):
    raise AssertionError("build_plan_inputs must not read user files")


def test_build_plan_inputs_reads_no_user_files(monkeypatch):
    for name in (
        "RecipeDB",
        "load_recipe_tags",
        "load_canonical_recipe_tag_slugs",
        "load_hard_eligible_recipe_tag_slugs",
        "hydrate_parity_plan_context",
        "MealPrepBatchRepository",
        "load_profile_pins",
    ):
        monkeypatch.setattr(f"src.api.server.{name}", _refuse)
    monkeypatch.setattr("src.planning.orchestrator.MealPrepBatchRepository", _refuse)
    monkeypatch.setattr("src.planning.orchestrator.load_profile_pins", _refuse)

    recipes = [
        Recipe(
            id=rid,
            name=rid,
            ingredients=[Ingredient("chicken breast", 150.0, "g", is_to_taste=False)],
            cooking_time_minutes=10,
            instructions=["cook"],
        )
        for rid in ("a", "b")
    ]
    tag_data = PlanTagData(
        tags_by_id={
            "a": RecipeTagsJson(cuisine="mexican", cost_level="cheap", prep_time_bucket="quick_meal"),
            "b": RecipeTagsJson(cuisine="italian", cost_level="cheap", prep_time_bucket="quick_meal"),
        },
        canonical_slugs_by_id={"a": {"high-protein"}, "b": set()},
        hard_eligible_slugs_by_id={"a": {"high-protein"}, "b": set()},
    )
    batch = MealPrepBatch(
        id="batch-b",
        recipe_id="b",
        total_servings=1,
        cook_date="2026-11-02",
        assignments=[BatchAssignment(day_index=0, slot_index=1)],
        status="active",
    )
    user_profile, _ = server._build_user_profile(PlanRequest(**{**PAYLOAD, "days": 1}))

    inputs = build_plan_inputs(
        user_profile=user_profile,
        days=1,
        recipes=recipes,
        tag_data=tag_data,
        tag_preferences=type("Prefs", (), {"cuisine": "mexican"})(),
        provider=_Provider(),
        pins=[ProfilePin(day_index=0, slot_index=0, recipe_id="a")],
        batches=[batch],
        keep_batch_recipes=True,
    )

    # The cuisine filter keeps "a"; "b" stays only because a batch uses it.
    assert [r.id for r in inputs.recipes] == ["a", "b"]
    assert inputs.recipe_by_id["a"].hard_eligible_tag_slugs == {"high-protein"}
    assert inputs.planning_profile.pinned_assignments == {(1, 0): "a"}
    assert [(lock.batch_id, lock.day_index, lock.slot_index) for lock in inputs.planning_profile.batch_locks] == [
        ("batch-b", 0, 1)
    ]
