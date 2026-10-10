from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass

from fastapi.testclient import TestClient

from src.api.server import app
from src.data_layer.meal_prep import BatchAssignment, MealPrepBatch
from src.data_layer.models import NutritionProfile, ProfilePin, UserProfile
from src.planning.converters import convert_profile
from src.planning.orchestrator import (
    apply_persisted_pins_to_profile,
    build_plan_request_from_profile,
    hydrate_parity_plan_context,
    parity_diagnostics_payload,
    planning_batch_locks_from_batches,
)
from src.planning.phase0_models import PlanningRecipe
from src.planning.planner import plan_meals
from src.planning.phase10_reporting import MealPlanResult


def _recipe_ids_sha256(payload: dict) -> str:
    ids = list(payload.get("recipe_ids", []))
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()


def _planned_meal_sequence(result: MealPlanResult) -> list[tuple[int, int, str]]:
    plan = list(result.plan or [])
    plan.sort(key=lambda a: (a.day_index, a.slot_index))
    return [(a.day_index, a.slot_index, a.recipe_id) for a in plan]


def _planning_recipes() -> list[PlanningRecipe]:
    return [
        PlanningRecipe(
            id="r_batch",
            name="r_batch",
            ingredients=[],
            cooking_time_minutes=10,
            nutrition=NutritionProfile(calories=500.0, protein_g=50.0, fat_g=20.0, carbs_g=40.0),
            canonical_tag_slugs=set(),
        ),
        PlanningRecipe(
            id="r_other",
            name="r_other",
            ingredients=[],
            cooking_time_minutes=10,
            nutrition=NutritionProfile(calories=500.0, protein_g=50.0, fat_g=20.0, carbs_g=40.0),
            canonical_tag_slugs=set(),
        ),
    ]


def _profile_with_pins(*, pins: list[ProfilePin]) -> UserProfile:
    return UserProfile(
        daily_calories=1000,
        daily_protein_g=100.0,
        daily_fat_g=(40.0, 60.0),
        daily_carbs_g=100.0,
        schedule={"12:00": 2, "18:00": 2},
        liked_foods=[],
        disliked_foods=[],
        allergies=[],
        pins=list(pins),
    )


def _active_batch_fixture() -> list[MealPrepBatch]:
    return [
        MealPrepBatch(
            id="batch-1",
            recipe_id="r_batch",
            total_servings=4,
            cook_date="2026-01-01",
            assignments=[BatchAssignment(day_index=0, slot_index=0, servings=1.0)],
            status="active",
        )
    ]


def _apply_api_style_setup(
    profile: UserProfile,
    *,
    active_batches: list[MealPrepBatch],
    persisted_pins: list[ProfilePin],
) -> tuple[object, list[PlanningRecipe]]:
    apply_persisted_pins_to_profile(profile, persisted_pins)
    planning_profile = convert_profile(profile, days=1)
    planning_profile.batch_locks = planning_batch_locks_from_batches(active_batches)
    return planning_profile, copy.deepcopy(_planning_recipes())


def _apply_cli_style_setup(
    profile: UserProfile,
    *,
    active_batches: list[MealPrepBatch],
    persisted_pins: list[ProfilePin],
) -> tuple[object, list[PlanningRecipe]]:
    apply_persisted_pins_to_profile(profile, persisted_pins)
    planning_profile = convert_profile(profile, days=1)
    planning_profile.batch_locks = planning_batch_locks_from_batches(active_batches)
    return planning_profile, copy.deepcopy(_planning_recipes())


def test_cli_and_http_request_builder_parity_for_batches_pins_and_seed():
    """E-blocker: same profile + batches + persisted pins + seed → identical meal sequence."""
    persisted_pins = [ProfilePin(day_index=0, slot_index=1, recipe_id="r_other")]
    profile = _profile_with_pins(pins=persisted_pins)
    recipes = _planning_recipes()
    active_batches = _active_batch_fixture()
    seed = 7
    expected_sequence = [(0, 0, "r_batch"), (0, 1, "r_other")]

    http_payload = build_plan_request_from_profile(profile, recipes, active_batches, seed)
    cli_payload = build_plan_request_from_profile(profile, recipes, active_batches, seed)

    assert http_payload["active_batches"] == cli_payload["active_batches"]
    assert http_payload["seed"] == cli_payload["seed"] == 7
    assert _recipe_ids_sha256(http_payload) == _recipe_ids_sha256(cli_payload)

    http_profile, http_recipes = _apply_api_style_setup(
        copy.deepcopy(profile),
        active_batches=active_batches,
        persisted_pins=persisted_pins,
    )
    cli_profile, cli_recipes = _apply_cli_style_setup(
        copy.deepcopy(profile),
        active_batches=active_batches,
        persisted_pins=persisted_pins,
    )

    http_result = plan_meals(http_profile, http_recipes, days=1)
    cli_result = plan_meals(cli_profile, cli_recipes, days=1)

    assert _planned_meal_sequence(http_result) == expected_sequence
    assert _planned_meal_sequence(cli_result) == expected_sequence
    assert _planned_meal_sequence(http_result) == _planned_meal_sequence(cli_result)


def test_persisted_pins_seed_and_meal_sequence_parity():
    persisted_pins = [ProfilePin(day_index=0, slot_index=1, recipe_id="r_other")]
    profile = _profile_with_pins(pins=persisted_pins)
    active_batches = _active_batch_fixture()
    seed = 7

    api_profile, api_recipes = _apply_api_style_setup(
        copy.deepcopy(profile),
        active_batches=active_batches,
        persisted_pins=persisted_pins,
    )
    cli_profile, cli_recipes = _apply_cli_style_setup(
        copy.deepcopy(profile),
        active_batches=active_batches,
        persisted_pins=persisted_pins,
    )

    api_payload = build_plan_request_from_profile(profile, _planning_recipes(), active_batches, seed)
    cli_payload = build_plan_request_from_profile(profile, _planning_recipes(), active_batches, seed)
    assert api_payload["seed"] == cli_payload["seed"] == 7

    first = plan_meals(api_profile, api_recipes, days=1)
    second = plan_meals(cli_profile, cli_recipes, days=1)
    third = plan_meals(api_profile, copy.deepcopy(_planning_recipes()), days=1)

    expected_sequence = [(0, 0, "r_batch"), (0, 1, "r_other")]
    assert _planned_meal_sequence(first) == expected_sequence
    assert _planned_meal_sequence(second) == expected_sequence
    assert _planned_meal_sequence(third) == expected_sequence


def test_parity_diagnostics_payload_includes_batches_pins_and_seed(monkeypatch):
    active_batches = _active_batch_fixture()
    persisted_pins = [ProfilePin(day_index=0, slot_index=1, recipe_id="r_other")]

    class _Repo:
        def list_active(self):
            return active_batches

    monkeypatch.setattr("src.planning.orchestrator.MealPrepBatchRepository", lambda: _Repo())
    monkeypatch.setattr(
        "src.planning.orchestrator.load_profile_pins",
        lambda **_kwargs: persisted_pins,
    )

    context = hydrate_parity_plan_context(seed=7)
    payload = parity_diagnostics_payload(context)

    assert payload["seed"] == 7
    assert payload["active_batches"][0]["id"] == "batch-1"
    assert payload["persisted_pins"] == [
        {"day_index": 0, "slot_index": 1, "recipe_id": "r_other"}
    ]
    assert len(context.batch_locks) == 1


def test_api_plan_ignores_client_active_batches(monkeypatch):
    @dataclass
    class _ObservedProfile:
        batch_locks_count: int

    observed = _ObservedProfile(batch_locks_count=-1)

    class _DummyRecipeDB:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_all_recipes(self):
            return []

    class _DummyProvider:
        def resolve_all(self, _names):
            return None

    def _fake_plan_meals(profile, recipe_pool, days):
        observed.batch_locks_count = len(profile.batch_locks)
        return MealPlanResult(
            success=True,
            termination_code="TC-1",
            plan=[],
            daily_trackers={},
            weekly_tracker=None,
            report={},
            stats={"attempts": 1, "backtracks": 0},
        )

    monkeypatch.setattr("src.api.server.RecipeDB", _DummyRecipeDB)
    monkeypatch.setattr("src.api.server.NutritionDB", lambda _p: object())
    monkeypatch.setattr("src.api.server.LocalIngredientProvider", lambda _db: _DummyProvider())
    monkeypatch.setattr("src.api.server.convert_recipes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("src.api.server.load_canonical_recipe_tag_slugs", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("src.api.server.plan_meals", _fake_plan_meals)
    monkeypatch.setattr(
        "src.api.server.format_result_json",
        lambda *_a, **_k: {
            "success": True,
            "termination_code": "TC-1",
            "days": 1,
            "daily_plans": [],
            "warnings": {},
            "report": {"failures": []},
            "goals": {},
            "weekly_totals": None,
            "plan_status": "success",
            "plan_status_message": None,
        },
    )
    monkeypatch.setattr(
        "src.api.server.hydrate_parity_plan_context",
        lambda **_kwargs: type(
            "Ctx",
            (),
            {
                "active_batches": [],
                "persisted_pins": [],
                "seed": None,
                "batch_locks": [],
            },
        )(),
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/plan",
        json={
            "daily_calories": 2400,
            "daily_protein_g": 150.0,
            "daily_fat_g_min": 50.0,
            "daily_fat_g_max": 100.0,
            "schedule": {"07:00": 2, "12:00": 3, "18:00": 3},
            "liked_foods": [],
            "disliked_foods": [],
            "allergies": [],
            "days": 1,
            "ingredient_source": "local",
            "active_batches": [{"id": "client-injected"}],
        },
    )

    assert response.status_code == 200
    assert observed.batch_locks_count == 0
