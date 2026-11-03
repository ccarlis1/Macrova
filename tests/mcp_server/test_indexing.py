"""MCP day/meal numbering: 1-based at the boundary, 0-based inside.

Round trips go through the real pipeline (``build_plan_inputs`` -> ``plan_meals`` ->
``format_plan_response``), so a pin, batch or FM-3 failure comes back at the same
day and meal the caller sent.
"""

from __future__ import annotations

import pytest

from src.api import server
from src.api.server import PlanRequest, PlanTagData, build_plan_inputs, format_plan_response
from src.data_layer.meal_prep import BatchAssignment
from src.data_layer.models import Ingredient, ProfilePin, Recipe
from src.mcp_server.indexing import (
    SlotNumberError,
    batches_from_mcp,
    batches_to_mcp,
    failure_where,
    fm3_pinned_slots,
    from_slot,
    meal_number,
    pins_from_mcp,
    pins_to_mcp,
    recipe_gap_slots,
    to_slot,
)
from src.planning.planner import plan_meals

DAYS = 2
MEAL_COUNTS = [3, 3]
RECIPE_IDS = ("a", "b", "c", "d", "e")


class _Provider:
    def resolve_all(self, _names):
        return None

    def get_ingredient_info(self, name):
        return {"name": name, "per_100g": {"calories": 200.0, "protein_g": 20.0, "fat_g": 8.0, "carbs_g": 12.0}}


def _plan(mcp_pins, mcp_meal_prep):
    """Plan 2 days x 3 meals of identical 300 kcal recipes from MCP-numbered pins and batches."""
    request = PlanRequest(
        daily_calories=2200,
        daily_protein_g=140.0,
        daily_fat_g_min=60.0,
        daily_fat_g_max=90.0,
        days=DAYS,
        schedule_days=[
            {"day_index": d, "meals": [{"index": m, "busyness_level": 3} for m in (1, 2, 3)]}
            for d in range(1, DAYS + 1)
        ],
    )
    user_profile, _ = server._build_user_profile(request)
    pins = pins_from_mcp(mcp_pins, MEAL_COUNTS)
    batches = batches_from_mcp(mcp_meal_prep, MEAL_COUNTS)
    recipes = [
        Recipe(
            id=rid,
            name=rid,
            ingredients=[Ingredient("chicken breast", 150.0, "g", is_to_taste=False)],
            cooking_time_minutes=10,
            instructions=["cook"],
        )
        for rid in RECIPE_IDS
    ]
    inputs = build_plan_inputs(
        user_profile=user_profile,
        days=DAYS,
        recipes=recipes,
        tag_data=PlanTagData(
            tags_by_id={},
            canonical_slugs_by_id={rid: set() for rid in RECIPE_IDS},
            hard_eligible_slugs_by_id={rid: set() for rid in RECIPE_IDS},
        ),
        tag_preferences=request,
        provider=_Provider(),
        pins=pins,
        batches=batches,
        keep_batch_recipes=True,
    )
    result = plan_meals(inputs.planning_profile, inputs.recipe_pool, DAYS)
    out = format_plan_response(result, inputs, user_profile=user_profile, days=DAYS, pins=pins, batches=batches)
    return inputs, out


def test_to_slot_and_from_slot_are_inverse():
    for day in (1, 2, 7):
        for meal in (1, 3, 8):
            assert from_slot(*to_slot(day, meal)) == {"day": day, "meal": meal}
    assert to_slot(1, 1) == (0, 0)
    assert from_slot(None, None) == {"day": None, "meal": None}
    assert from_slot(2, None) == {"day": 3, "meal": None}


@pytest.mark.parametrize(
    ("day", "meal", "message"),
    [
        (0, 1, "day must be a whole number from 1"),
        (1, 0, "meal must be a whole number from 1"),
        (-1, 1, "day must be"),
        (1.0, 1, "day must be"),
        (True, 1, "day must be"),
        (3, 1, "day 3 is outside the 2-day plan"),
        (2, 4, "day 2 has 3 meals; there is no meal 4"),
    ],
)
def test_to_slot_rejects_numbers_outside_the_plan(day, meal, message):
    with pytest.raises(SlotNumberError, match=message):
        to_slot(day, meal, MEAL_COUNTS)


def test_pins_round_trip():
    mcp_pins = [{"day": 1, "meal": 1, "recipe_id": "a"}, {"day": 2, "meal": 3, "recipe_id": "b"}]
    pins = pins_from_mcp(mcp_pins, MEAL_COUNTS)
    assert pins == [ProfilePin(0, 0, "a"), ProfilePin(1, 2, "b")]
    assert pins_to_mcp(pins) == mcp_pins


def test_batches_round_trip():
    mcp_meal_prep = [
        {
            "recipe_id": "chili",
            "total_servings": 4,
            "assignments": [{"day": d, "meal": 2, "servings": 1.0} for d in (1, 2, 3, 4)],
        }
    ]
    batches = batches_from_mcp(mcp_meal_prep)
    assert batches[0].id == "meal-prep-1"
    assert batches[0].status == "active"
    assert batches[0].assignments == [BatchAssignment(d, 1, 1.0) for d in (0, 1, 2, 3)]
    assert batches_to_mcp(batches) == mcp_meal_prep


def test_batch_servings_default_to_one():
    batches = batches_from_mcp([{"recipe_id": "c", "total_servings": 1, "assignments": [{"day": 1, "meal": 1}]}])
    assert batches[0].assignments == [BatchAssignment(0, 0, 1.0)]


def test_pins_and_batches_reach_the_planner_and_come_back_at_the_same_meal():
    inputs, out = _plan(
        [{"day": 2, "meal": 3, "recipe_id": "a"}],
        [{"recipe_id": "c", "total_servings": 1, "assignments": [{"day": 1, "meal": 2}]}],
    )
    # The planner keys pins as (1-based day, 0-based slot).
    assert inputs.planning_profile.pinned_assignments[(2, 2)] == "a"
    assert [(lock.day_index, lock.slot_index) for lock in inputs.planning_profile.batch_locks] == [(0, 1)]

    meals = {
        (day["day"], meal_number(m)): m for day in out["daily_plans"] for m in day["meals"]
    }
    assert meals[(2, 3)]["recipe_id"] == "a"
    assert meals[(2, 3)]["source"] == "pinned_assignment"
    assert meals[(1, 2)]["recipe_id"] == "c"
    assert meals[(1, 2)]["source"] == "meal_prep_batch"


def test_slot_level_fm3_reports_the_pinned_meal():
    # HC-8: a non-workout recipe pinned on consecutive days.
    _, out = _plan(
        [{"day": 1, "meal": 2, "recipe_id": "a"}, {"day": 2, "meal": 3, "recipe_id": "a"}],
        [],
    )
    [failure] = out["report"]["failures"]
    assert failure["code"] == "FM-3"
    assert failure_where(failure) == {"day": 2, "meal": 3}


def test_day_level_fm3_reports_the_day_and_each_pinned_meal():
    # Day 2 is fully pinned at 900 kcal, far under the 2200 kcal target.
    _, out = _plan(
        [{"day": 2, "meal": 1, "recipe_id": "a"}, {"day": 2, "meal": 2, "recipe_id": "b"}],
        [{"recipe_id": "c", "total_servings": 1, "assignments": [{"day": 2, "meal": 3}]}],
    )
    [failure] = out["report"]["failures"]
    assert failure["code"] == "FM-3"
    assert failure_where(failure) == {"day": 2, "meal": None}
    assert [(row["day"], row["meal"], row["recipe_id"], row["source"]) for row in fm3_pinned_slots(failure)] == [
        (2, 1, "a", "pin"),
        (2, 2, "b", "pin"),
        (2, 3, "c", "batch"),
    ]


def test_failure_where_falls_back_to_the_day_date():
    # FM-MACRO-INFEASIBLE sets only the "day-N" date.
    assert failure_where({"code": "FM-MACRO-INFEASIBLE", "date": "day-4"}) == {"day": 4, "meal": None}
    assert failure_where({"code": "FM-4"}) == {"day": None, "meal": None}


def test_recipe_gap_slots_are_one_based():
    assert recipe_gap_slots([[0, 0], [2, 1]]) == [{"day": 1, "meal": 1}, {"day": 3, "meal": 2}]
