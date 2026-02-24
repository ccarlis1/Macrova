"""Phase 1 unit tests: initial state, pinned pre-validation, adjusted daily targets, per-meal targets.

Spec: MEALPLAN_SPECIFICATION_v1.md Section 3.4, 3.5, 3.6.
Roadmap: Phase 1 — State initialization and per-meal target computation.
"""

import pytest

from src.data_layer.models import NutritionProfile, MicronutrientProfile, Ingredient
from src.planning.phase0_models import (
    Assignment,
    MealSlot,
    PlanningUserProfile,
    PlanningRecipe,
    DailyTracker,
    validate_schedule_structure,
)
from src.planning.phase1_state import (
    PinnedValidationResult,
    validate_pinned_assignments,
    build_initial_state,
    InitialState,
    adjusted_daily_target,
    per_meal_target,
    PerMealTarget,
    PRE_WORKOUT_PROTEIN_FACTOR,
    POST_WORKOUT_PROTEIN_FACTOR,
    HIGH_SATIETY_CALORIES_FACTOR,
)


def _make_recipe(rid: str, calories: float = 500.0, protein: float = 30.0, fat: float = 20.0, carbs: float = 40.0, cooking_min: int = 10, ingredients: list = None):
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=ingredients or [],
        cooking_time_minutes=cooking_min,
        nutrition=NutritionProfile(calories, protein, fat, carbs),
        primary_carb_contribution=None,
    )


# --- Initial state ---


class TestInitialState:
    """No pins; pins on one day; pins across multiple days; assignment order."""

    @pytest.fixture
    def schedule_2d(self):
        return [
            [MealSlot("08:00", 2, "b"), MealSlot("13:00", 3, "l")],
            [MealSlot("08:00", 2, "b"), MealSlot("19:00", 4, "d")],
        ]

    @pytest.fixture
    def profile_no_pins(self, schedule_2d):
        return PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule_2d,
        )

    def test_no_pinned_assignments(self, profile_no_pins, schedule_2d):
        R = {"r1": _make_recipe("r1"), "r2": _make_recipe("r2")}
        val = validate_pinned_assignments(profile_no_pins, R, 2)
        assert val.success is True
        state = build_initial_state(profile_no_pins, R, 2)
        assert state.assignments == []
        assert state.daily_trackers == {}
        assert state.weekly_tracker.days_completed == 0
        assert state.weekly_tracker.days_remaining == 2
        assert state.weekly_tracker.weekly_totals.calories == 0.0

    def test_pins_on_single_day(self, schedule_2d):
        profile = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule_2d,
            pinned_assignments={(1, 0): "r1"},
        )
        R = {"r1": _make_recipe("r1", calories=600.0)}
        val = validate_pinned_assignments(profile, R, 2)
        assert val.success is True
        state = build_initial_state(profile, R, 2)
        assert len(state.assignments) == 1
        assert state.assignments[0] == Assignment(0, 0, "r1")
        assert 0 in state.daily_trackers
        t = state.daily_trackers[0]
        assert t.calories_consumed == 600.0
        assert t.slots_assigned == 1
        assert t.slots_total == 2
        assert "r1" in t.used_recipe_ids

    def test_pins_across_multiple_days(self, schedule_2d):
        profile = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule_2d,
            pinned_assignments={(1, 0): "r1", (2, 1): "r2"},
        )
        R = {"r1": _make_recipe("r1", calories=400.0), "r2": _make_recipe("r2", calories=500.0)}
        val = validate_pinned_assignments(profile, R, 2)
        assert val.success is True
        state = build_initial_state(profile, R, 2)
        assert len(state.assignments) == 2
        assert state.assignments[0] == Assignment(0, 0, "r1")
        assert state.assignments[1] == Assignment(1, 1, "r2")
        assert state.daily_trackers[0].calories_consumed == 400.0
        assert state.daily_trackers[1].calories_consumed == 500.0
        assert state.weekly_tracker.weekly_totals.calories == 900.0

    def test_assignment_order_matches_decision_order(self, schedule_2d):
        profile = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule_2d,
            pinned_assignments={(1, 1): "r2", (1, 0): "r1", (2, 0): "r3"},
        )
        R = {f"r{i}": _make_recipe(f"r{i}") for i in (1, 2, 3)}
        state = build_initial_state(profile, R, 2)
        # Decision order: (0,0), (0,1), (1,0), (1,1)
        assert state.assignments[0] == Assignment(0, 0, "r1")
        assert state.assignments[1] == Assignment(0, 1, "r2")
        assert state.assignments[2] == Assignment(1, 0, "r3")


# --- Pinned pre-validation ---


class TestPinnedPreValidation:
    """Reject HC-1, HC-2, HC-3, HC-5, HC-8; failure indicates which HC failed."""

    @pytest.fixture
    def schedule_1d(self):
        return [[MealSlot("08:00", 2, "b"), MealSlot("13:00", 3, "l")]]

    def test_reject_HC1_excluded_ingredient(self, schedule_1d):
        profile = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule_1d,
            excluded_ingredients=["peanuts"],
            pinned_assignments={(1, 0): "r1"},
        )
        R = {"r1": _make_recipe("r1", ingredients=[Ingredient("peanuts", 30.0, "g", False)])}
        val = validate_pinned_assignments(profile, R, 1)
        assert val.success is False
        assert val.failed_hc == "HC-1"

    def test_reject_HC2_same_recipe_twice_same_day(self, schedule_1d):
        profile = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule_1d,
            pinned_assignments={(1, 0): "r1", (1, 1): "r1"},
        )
        R = {"r1": _make_recipe("r1", cooking_min=5)}
        val = validate_pinned_assignments(profile, R, 1)
        assert val.success is False
        assert val.failed_hc == "HC-2"

    def test_reject_HC3_cooking_time(self, schedule_1d):
        profile = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule_1d,
            pinned_assignments={(1, 0): "r1"},
        )
        # Slot 0 has busyness 2 -> max 15 min
        R = {"r1": _make_recipe("r1", cooking_min=20)}
        val = validate_pinned_assignments(profile, R, 1)
        assert val.success is False
        assert val.failed_hc == "HC-3"

    def test_reject_HC5_calorie_ceiling(self, schedule_1d):
        profile = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule_1d,
            max_daily_calories=400,
            pinned_assignments={(1, 0): "r1"},
        )
        R = {"r1": _make_recipe("r1", calories=500.0, cooking_min=5)}
        val = validate_pinned_assignments(profile, R, 1)
        assert val.success is False
        assert val.failed_hc == "HC-5"

    def test_reject_HC8_consecutive_day_non_workout_repeat(self):
        schedule = [
            [MealSlot("08:00", 2, "b")],
            [MealSlot("08:00", 2, "b")],
        ]
        profile = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule,
            pinned_assignments={(1, 0): "r1", (2, 0): "r1"},
        )
        R = {"r1": _make_recipe("r1", cooking_min=5)}
        val = validate_pinned_assignments(profile, R, 2)
        assert val.success is False
        assert val.failed_hc == "HC-8"

    def test_pass_HC8_when_same_recipe_in_workout_slots(self):
        schedule = [
            [MealSlot("16:00", 2, "snack")],
            [MealSlot("16:00", 2, "snack")],
        ]
        profile = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule,
            activity_schedule={"workout_start": "18:00", "workout_end": "19:00"},
            pinned_assignments={(1, 0): "r1", (2, 0): "r1"},
        )
        R = {"r1": _make_recipe("r1", cooking_min=5)}
        val = validate_pinned_assignments(profile, R, 2)
        assert val.success is True


# --- Adjusted daily targets ---


class TestAdjustedDailyTargets:
    """No carryover; positive carryover; multiple days remaining."""

    def test_no_carryover(self):
        assert adjusted_daily_target(100.0, 0.0, 5) == 100.0

    def test_positive_carryover(self):
        # base 100, carryover 30, days_remaining 3 -> 100 + 30/3 = 110
        assert adjusted_daily_target(100.0, 30.0, 3) == pytest.approx(110.0)

    def test_multiple_days_remaining(self):
        assert adjusted_daily_target(50.0, 100.0, 4) == pytest.approx(75.0)


# --- Per-meal targets ---


class TestPerMealTargets:
    """Various slots_left; activity context; multiplicative factors."""

    @pytest.fixture
    def profile(self):
        return PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=[[MealSlot("08:00", 2, "b"), MealSlot("13:00", 3, "l"), MealSlot("19:00", 4, "d")]],
        )

    def test_even_distribution_three_slots(self, profile):
        t = DailyTracker(calories_consumed=0, protein_consumed=0, fat_consumed=0, carbs_consumed=0, slots_assigned=0, slots_total=3)
        target = per_meal_target(0, 0, t, profile, frozenset({"sedentary"}), "moderate")
        assert target.calories == pytest.approx(2400 / 3)
        assert target.protein_g == pytest.approx(150.0 / 3)
        assert target.carbs_g == pytest.approx(250.0 / 3)

    def test_remaining_after_partial_consumption(self, profile):
        t = DailyTracker(calories_consumed=800, protein_consumed=50, fat_consumed=25, carbs_consumed=80, slots_assigned=1, slots_total=3)
        target = per_meal_target(0, 1, t, profile, frozenset({"sedentary"}), "moderate")
        assert target.calories == pytest.approx((2400 - 800) / 2)
        assert target.protein_g == pytest.approx((150 - 50) / 2)

    def test_pre_workout_reduces_protein_increases_carbs(self, profile):
        t = DailyTracker(slots_assigned=0, slots_total=2)
        base = per_meal_target(0, 0, t, profile, frozenset({"sedentary"}), "moderate")
        pre = per_meal_target(0, 0, t, profile, frozenset({"pre_workout"}), "moderate")
        assert pre.protein_g == pytest.approx(base.protein_g * PRE_WORKOUT_PROTEIN_FACTOR)
        assert pre.carbs_g == pytest.approx(base.carbs_g * 1.1)

    def test_post_workout_increases_protein(self, profile):
        t = DailyTracker(slots_assigned=0, slots_total=2)
        base = per_meal_target(0, 0, t, profile, frozenset({"sedentary"}), "moderate")
        post = per_meal_target(0, 0, t, profile, frozenset({"post_workout"}), "moderate")
        assert post.protein_g == pytest.approx(base.protein_g * POST_WORKOUT_PROTEIN_FACTOR)

    def test_high_satiety_increases_calories(self, profile):
        t = DailyTracker(slots_assigned=0, slots_total=2)
        mod = per_meal_target(0, 0, t, profile, frozenset({"sedentary"}), "moderate")
        high = per_meal_target(0, 0, t, profile, frozenset({"sedentary"}), "high")
        assert high.calories == pytest.approx(mod.calories * HIGH_SATIETY_CALORIES_FACTOR)
