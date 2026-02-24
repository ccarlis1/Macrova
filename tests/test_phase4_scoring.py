"""Phase 4 unit tests: cost function (scoring module). Spec Section 8.

No constraint or feasibility logic; fixed state and recipe only.
"""

from __future__ import annotations

import pytest

from src.data_layer.models import (
    MicronutrientProfile,
    NutritionProfile,
)
from src.planning.phase0_models import (
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    WeeklyTracker,
)
from src.planning.phase4_scoring import (
    W_NUTRITION,
    W_MICRONUTRIENT,
    W_SATIETY,
    W_BALANCE,
    W_SCHEDULE,
    ScoringStateView,
    nutrition_match,
    micronutrient_match,
    satiety_match,
    balance,
    schedule_match,
    composite_score,
)


def _make_recipe(
    rid: str = "r1",
    calories: float = 500.0,
    protein: float = 30.0,
    fat: float = 20.0,
    carbs: float = 40.0,
    cooking_min: int = 15,
    micronutrients: MicronutrientProfile | None = None,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=[],
        cooking_time_minutes=cooking_min,
        nutrition=NutritionProfile(calories, protein, fat, carbs, micronutrients=micronutrients),
        primary_carb_contribution=None,
    )


def _make_slot(busyness: int = 2) -> MealSlot:
    return MealSlot("12:00", busyness, "lunch")


def _make_profile() -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        schedule=[[_make_slot(2), _make_slot(2)]],
    )


def _make_state(
    daily_trackers: dict | None = None,
    weekly_tracker: WeeklyTracker | None = None,
    schedule: list | None = None,
) -> ScoringStateView:
    sched = schedule or [[_make_slot(2), _make_slot(2)]]
    return ScoringStateView(
        daily_trackers=daily_trackers or {},
        weekly_tracker=weekly_tracker or WeeklyTracker(),
        schedule=sched,
    )


# --- Per-meal target and activity for nutrition_match ---


def _get_per_meal_and_activity(state: ScoringStateView, profile: PlanningUserProfile, day_index: int, slot_index: int):
    from src.planning.phase1_state import per_meal_target
    from src.planning.slot_attributes import activity_context, time_until_next_meal, satiety_requirement
    day_slots = state.schedule[day_index]
    slot = day_slots[slot_index]
    next_first = state.schedule[day_index + 1][0] if day_index + 1 < len(state.schedule) else None
    activity_context_set = activity_context(slot, slot_index, day_slots, next_first, profile.activity_schedule or {})
    hours_until = time_until_next_meal(slot, slot_index, day_slots, next_first)
    is_last = slot_index + 1 >= len(day_slots)
    satiety = satiety_requirement(hours_until, is_last)
    tracker = state.daily_trackers.get(day_index) or DailyTracker(slots_total=len(day_slots))
    per_meal = per_meal_target(day_index, slot_index, tracker, profile, activity_context_set, satiety)
    return per_meal, activity_context_set, satiety


# --- Component tests ---


class TestNutritionMatch:
    """8.3 Nutrition Match in [0, 100]."""

    def test_perfect_match_near_100(self):
        profile = _make_profile()
        state = _make_state(
            daily_trackers={0: DailyTracker(slots_assigned=0, slots_total=2)},
            schedule=[[_make_slot(), _make_slot()]],
        )
        per_meal, act, _ = _get_per_meal_and_activity(state, profile, 0, 0)
        target_cal = per_meal.calories
        recipe = _make_recipe(rid="r1", calories=target_cal, protein=per_meal.protein_g, fat=(per_meal.fat_min + per_meal.fat_max) / 2, carbs=per_meal.carbs_g)
        score = nutrition_match(recipe, 0, 0, state, profile, per_meal, act)
        assert 95 <= score <= 100

    def test_extreme_deviation_near_zero(self):
        profile = _make_profile()
        state = _make_state(daily_trackers={0: DailyTracker(slots_total=2)})
        per_meal, act, _ = _get_per_meal_and_activity(state, profile, 0, 0)
        recipe = _make_recipe(calories=5000.0, protein=200.0, fat=200.0, carbs=500.0)
        score = nutrition_match(recipe, 0, 0, state, profile, per_meal, act)
        assert 0 <= score <= 30


class TestMicronutrientMatch:
    """8.4 Micronutrient Match in [0, 100]."""

    def test_in_range(self):
        profile = _make_profile()
        profile.micronutrient_targets = {"iron_mg": 10.0, "vitamin_c_mg": 90.0}
        state = _make_state(
            daily_trackers={0: DailyTracker(micronutrients_consumed={"iron_mg": 2.0, "vitamin_c_mg": 20.0})},
            schedule=[[_make_slot()]],
            weekly_tracker=WeeklyTracker(days_remaining=1),
        )
        recipe = _make_recipe(micronutrients=MicronutrientProfile(iron_mg=5.0, vitamin_c_mg=50.0))
        score = micronutrient_match(recipe, 0, state, profile)
        assert 0 <= score <= 100

    def test_no_tracked_returns_mid(self):
        profile = _make_profile()
        profile.micronutrient_targets = {}
        state = _make_state()
        recipe = _make_recipe()
        score = micronutrient_match(recipe, 0, state, profile)
        assert score == 50.0


class TestSatietyMatch:
    """8.5 Satiety Match in [0, 100]."""

    def test_high_satiety_fiber_protein_calories(self):
        recipe = _make_recipe(
            calories=600.0,
            protein=35.0,
            micronutrients=MicronutrientProfile(fiber_g=12.0),
        )
        score = satiety_match(recipe, "high")
        assert 0 <= score <= 100

    def test_moderate_in_range(self):
        recipe = _make_recipe(protein=25.0)
        score = satiety_match(recipe, "moderate")
        assert 0 <= score <= 100


class TestBalance:
    """8.6 Balance in [0, 100]."""

    def test_in_range(self):
        profile = _make_profile()
        state = _make_state(daily_trackers={0: DailyTracker(slots_assigned=0, slots_total=2)})
        recipe = _make_recipe()
        score = balance(recipe, 0, state, profile)
        assert 0 <= score <= 100


class TestScheduleMatch:
    """8.7 Schedule Match in [0, 100]."""

    def test_cooking_at_max(self):
        slot = _make_slot(busyness=2)
        recipe = _make_recipe(cooking_min=15)
        score = schedule_match(recipe, slot)
        assert 0 <= score <= 100
        assert score == 0.0

    def test_cooking_well_below_max(self):
        slot = _make_slot(busyness=2)
        recipe = _make_recipe(cooking_min=5)
        score = schedule_match(recipe, slot)
        assert 0 <= score <= 100
        assert score >= 50

    def test_busyness_4_proximity_to_30(self):
        slot = _make_slot(busyness=4)
        recipe = _make_recipe(cooking_min=30)
        score = schedule_match(recipe, slot)
        assert score == 100.0


# --- Composite ---


class TestCompositeScore:
    """Composite in [0, 100], weights sum 1.0."""

    def test_weights_sum_one(self):
        assert abs((W_NUTRITION + W_MICRONUTRIENT + W_SATIETY + W_BALANCE + W_SCHEDULE) - 1.0) < 1e-9

    def test_composite_in_range(self):
        profile = _make_profile()
        state = _make_state(schedule=[[_make_slot(2), _make_slot(2)]])
        recipe = _make_recipe()
        score = composite_score(recipe, 0, 0, state, profile)
        assert 0 <= score <= 100

    def test_determinism(self):
        profile = _make_profile()
        state = _make_state(schedule=[[_make_slot(2), _make_slot(2)]])
        recipe = _make_recipe()
        a = composite_score(recipe, 0, 0, state, profile)
        b = composite_score(recipe, 0, 0, state, profile)
        assert a == b


# --- Boundary ---

class TestBoundaries:
    """Boundary and edge cases."""

    def test_invalid_day_index_returns_mid(self):
        profile = _make_profile()
        state = _make_state()
        recipe = _make_recipe()
        score = composite_score(recipe, 5, 0, state, profile)
        assert score == 50.0

    def test_invalid_slot_index_returns_mid(self):
        profile = _make_profile()
        state = _make_state(schedule=[[_make_slot()]])
        recipe = _make_recipe()
        score = composite_score(recipe, 0, 5, state, profile)
        assert score == 50.0
