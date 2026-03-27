import pytest

from src.llm.planner_assistant import build_feedback_context, suggest_targeted_recipe_drafts
from src.llm.schemas import RecipeDraft, RecipeIngredientDraft
from src.llm.client import LLMClient
from src.planning.phase0_models import MealSlot, PlanningUserProfile
from src.planning.phase10_reporting import MealPlanResult


def _make_schedule(*, days: int, slots_per_day: int) -> list[list[MealSlot]]:
    schedule: list[list[MealSlot]] = []
    for d in range(days):
        day_slots: list[MealSlot] = []
        for s in range(slots_per_day):
            day_slots.append(MealSlot(time="12:00", busyness_level=2, meal_type="lunch"))
        schedule.append(day_slots)
    return schedule


def test_build_feedback_context_fm4_extracts_deficient_nutrients():
    profile = PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        schedule=_make_schedule(days=2, slots_per_day=2),
        pinned_assignments={},
        excluded_ingredients=[],
        liked_foods=[],
        micronutrient_targets={},
    )

    result = MealPlanResult(
        success=False,
        termination_code="TC-2",
        failure_mode="FM-4",
        report={
            "deficient_nutrients": [
                {
                    "nutrient": "iron_mg",
                    "achieved": 0.0,
                    "required": 2.0,
                    "deficit": 2.0,
                    "classification": "structural",
                }
            ]
        },
        stats={"attempts": 0, "backtracks": 0},
    )

    ctx = build_feedback_context(result, profile)
    assert ctx["failure_type"] == "FM-4"
    assert ctx["days"] == 2
    assert ctx["meals_per_day"] == 2
    assert ctx["busyness_by_day"] == [[2, 2], [2, 2]]
    assert ctx["workout_gaps_by_day"] is None
    assert ctx["nutrient_deficits"] == [
        {
            "nutrient": "iron_mg",
            "achieved": 0.0,
            "required": 2.0,
            "deficit": 2.0,
            "classification": "structural",
        }
    ]
    assert ctx["macro_violations"] == []


def test_build_feedback_context_includes_workout_gaps_when_present():
    profile = PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        schedule=_make_schedule(days=1, slots_per_day=3),
        workout_after_meal_indices_by_day=[[1]],
        pinned_assignments={},
        excluded_ingredients=[],
        liked_foods=[],
        micronutrient_targets={},
    )
    result = MealPlanResult(
        success=False,
        termination_code="TC-2",
        failure_mode="FM-1",
        report={},
        stats={"attempts": 0, "backtracks": 0},
    )
    ctx = build_feedback_context(result, profile)
    assert ctx["workout_gaps_by_day"] == [[1]]


def test_build_feedback_context_fm2_computes_macro_deficit_and_excess():
    profile = PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        schedule=_make_schedule(days=2, slots_per_day=2),
        pinned_assignments={},
        excluded_ingredients=[],
        liked_foods=[],
        micronutrient_targets={},
    )

    result = MealPlanResult(
        success=False,
        termination_code="TC-2",
        failure_mode="FM-2",
        report={
            "failed_days": [
                {
                    "day": 0,
                    "constraint_detail": "calories",
                    "macro_violations": {
                        "constraint_detail": "calories",
                        "calories_consumed": 2500.0,  # excess by 500
                        "protein_consumed": 90.0,  # deficit by 10
                        "fat_consumed": 40.0,  # deficit below fat_min by 10
                        "carbs_consumed": 200.0,  # deficit by 50
                    },
                    "ul_violations": {},
                }
            ]
        },
        stats={"attempts": 0, "backtracks": 0},
    )

    ctx = build_feedback_context(result, profile)
    assert ctx["failure_type"] == "FM-2"
    assert ctx["busyness_by_day"] == [[2, 2], [2, 2]]
    assert len(ctx["macro_violations"]) == 1
    day_ctx = ctx["macro_violations"][0]
    assert day_ctx["day"] == 0

    violations = {v["macro"]: v for v in day_ctx["violations"]}
    assert violations["calories"]["direction"] == "excess"
    assert violations["calories"]["amount"] == pytest.approx(500.0)
    assert violations["protein"]["direction"] == "deficit"
    assert violations["protein"]["amount"] == pytest.approx(10.0)
    assert violations["fat"]["direction"] == "deficit"
    assert violations["fat"]["amount"] == pytest.approx(10.0)
    assert violations["carbs"]["direction"] == "deficit"
    assert violations["carbs"]["amount"] == pytest.approx(50.0)


def test_suggest_targeted_recipe_drafts_uses_recipe_generator(monkeypatch):
    draft = RecipeDraft(
        name="LLM Recipe",
        ingredients=[RecipeIngredientDraft(name="chicken breast", quantity=200.0, unit="g")],
        instructions=["Cook it."],
    )

    captured = {}

    def _fake_generate_recipe_drafts(*, client, context, count):
        captured["client"] = client
        captured["context"] = context
        captured["count"] = count
        return [draft]

    monkeypatch.setattr(
        "src.llm.planner_assistant.generate_recipe_drafts",
        _fake_generate_recipe_drafts,
    )

    dummy_client = object()  # only forwarded, not used in the fake
    ctx = {"failure_type": "FM-4"}
    out = suggest_targeted_recipe_drafts(
        client=dummy_client,  # type: ignore[arg-type]
        context=ctx,
        count=1,
    )
    assert out == [draft]
    assert captured["context"] == ctx
    assert captured["count"] == 1

