"""Phase 2 unit tests: hard constraints as pure predicates. Spec Section 4.

No search, no scoring, no feasibility logic — only logical constraint enforcement.
"""

from __future__ import annotations

import pytest

from src.data_layer.models import (
    Ingredient,
    MicronutrientProfile,
    NutritionProfile,
    UpperLimits,
)
from src.planning.phase0_models import (
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
)
from src.planning.phase2_constraints import (
    ConstraintStateView,
    check_hc1_excluded_ingredients,
    check_hc2_no_same_day_reuse,
    check_hc3_cooking_time_bound,
    check_hc4_daily_ul,
    check_hc5_max_daily_calories,
    check_hc6_pinned_assignment,
    check_hc8_cross_day_non_workout_reuse,
    check_all,
)


def _make_recipe(
    rid: str,
    calories: float = 500.0,
    protein: float = 30.0,
    fat: float = 20.0,
    carbs: float = 40.0,
    cooking_min: int = 10,
    ingredients: list | None = None,
    micronutrients: MicronutrientProfile | None = None,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=ingredients or [],
        cooking_time_minutes=cooking_min,
        nutrition=NutritionProfile(calories, protein, fat, carbs, micronutrients=micronutrients),
        primary_carb_contribution=None,
    )


def _make_slot(busyness: int = 2) -> MealSlot:
    return MealSlot("12:00", busyness, "lunch")


def _make_profile(
    excluded: list[str] | None = None,
    max_calories: int | None = None,
    pinned: dict | None = None,
) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=2400,
        daily_protein_g=150.0,
        daily_fat_g=(60.0, 80.0),
        daily_carbs_g=250.0,
        excluded_ingredients=excluded or [],
        max_daily_calories=max_calories,
        pinned_assignments=pinned or {},
    )


def _make_state(daily_trackers: dict[int, DailyTracker] | None = None) -> ConstraintStateView:
    return ConstraintStateView(daily_trackers=daily_trackers or {})


# --- HC-1: Excluded ingredients ---


class TestHC1ExcludedIngredients:
    """HC-1: No recipe ingredient matching user_profile.excluded_ingredients (normalized)."""

    def test_matching_excluded_ingredient_rejected(self):
        recipe = _make_recipe(
            "r1",
            ingredients=[Ingredient("peanuts", 30.0, "g", False)],
        )
        profile = _make_profile(excluded=["peanuts"])
        state = _make_state({})
        slot = _make_slot()
        assert check_hc1_excluded_ingredients(
            recipe, slot, 0, state, profile, None
        ) is False

    def test_case_variation_normalized(self):
        recipe = _make_recipe(
            "r1",
            ingredients=[Ingredient("Peanuts", 30.0, "g", False)],
        )
        profile = _make_profile(excluded=["PEANUTS"])
        state = _make_state({})
        slot = _make_slot()
        assert check_hc1_excluded_ingredients(
            recipe, slot, 0, state, profile, None
        ) is False

    def test_whitespace_normalized(self):
        recipe = _make_recipe(
            "r1",
            ingredients=[Ingredient("  peanuts  ", 30.0, "g", False)],
        )
        profile = _make_profile(excluded=["peanuts"])
        state = _make_state({})
        slot = _make_slot()
        assert check_hc1_excluded_ingredients(
            recipe, slot, 0, state, profile, None
        ) is False

    def test_no_excluded_ingredient_allowed(self):
        recipe = _make_recipe(
            "r1",
            ingredients=[Ingredient("chicken", 100.0, "g", False)],
        )
        profile = _make_profile(excluded=["peanuts"])
        state = _make_state({})
        slot = _make_slot()
        assert check_hc1_excluded_ingredients(
            recipe, slot, 0, state, profile, None
        ) is True

    def test_empty_excluded_list_allowed(self):
        recipe = _make_recipe("r1", ingredients=[Ingredient("peanuts", 30.0, "g", False)])
        profile = _make_profile(excluded=[])
        state = _make_state({})
        slot = _make_slot()
        assert check_hc1_excluded_ingredients(
            recipe, slot, 0, state, profile, None
        ) is True


# --- HC-2: No same-day recipe reuse ---


class TestHC2NoSameDayReuse:
    """HC-2: Recipe ID at most once per day (daily_tracker.used_recipe_ids)."""

    def test_same_day_reuse_rejected(self):
        recipe = _make_recipe("r1")
        tracker = DailyTracker(used_recipe_ids={"r1"})
        state = _make_state({0: tracker})
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc2_no_same_day_reuse(
            recipe, slot, 0, state, profile, None
        ) is False

    def test_different_day_allowed(self):
        recipe = _make_recipe("r1")
        tracker_day0 = DailyTracker(used_recipe_ids={"r1"})
        state = _make_state({0: tracker_day0})
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc2_no_same_day_reuse(
            recipe, slot, 1, state, profile, None
        ) is True

    def test_first_use_today_allowed(self):
        recipe = _make_recipe("r1")
        tracker = DailyTracker(used_recipe_ids=set())
        state = _make_state({0: tracker})
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc2_no_same_day_reuse(
            recipe, slot, 0, state, profile, None
        ) is True

    def test_no_tracker_for_day_allowed(self):
        recipe = _make_recipe("r1")
        state = _make_state({})
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc2_no_same_day_reuse(
            recipe, slot, 0, state, profile, None
        ) is True


# --- HC-3: Cooking time bound ---


class TestHC3CookingTimeBound:
    """HC-3: recipe.cooking_time_minutes <= slot.cooking_time_max; busyness 4 no bound."""

    def test_within_bound_allowed(self):
        recipe = _make_recipe("r1", cooking_min=10)
        slot = _make_slot(busyness=2)  # max 15
        state = _make_state({})
        profile = _make_profile()
        assert check_hc3_cooking_time_bound(
            recipe, slot, 0, state, profile, None
        ) is True

    def test_at_bound_allowed(self):
        recipe = _make_recipe("r1", cooking_min=15)
        slot = _make_slot(busyness=2)  # max 15
        state = _make_state({})
        profile = _make_profile()
        assert check_hc3_cooking_time_bound(
            recipe, slot, 0, state, profile, None
        ) is True

    def test_over_bound_rejected(self):
        recipe = _make_recipe("r1", cooking_min=20)
        slot = _make_slot(busyness=2)  # max 15
        state = _make_state({})
        profile = _make_profile()
        assert check_hc3_cooking_time_bound(
            recipe, slot, 0, state, profile, None
        ) is False

    def test_busyness_4_exemption(self):
        recipe = _make_recipe("r1", cooking_min=120)
        slot = _make_slot(busyness=4)  # no upper bound
        state = _make_state({})
        profile = _make_profile()
        assert check_hc3_cooking_time_bound(
            recipe, slot, 0, state, profile, None
        ) is True


# --- HC-4: Daily UL enforcement ---


class TestHC4DailyUL:
    """HC-4: T_d.micronutrients_consumed[n] <= resolved_UL[n]; strict excess only."""

    def test_at_ul_allowed(self):
        ul = UpperLimits(vitamin_c_mg=100.0)
        tracker = DailyTracker(micronutrients_consumed={"vitamin_c_mg": 60.0})
        recipe = _make_recipe(
            "r1",
            micronutrients=MicronutrientProfile(vitamin_c_mg=40.0),
        )
        state = _make_state({0: tracker})
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc4_daily_ul(
            recipe, slot, 0, state, profile, ul
        ) is True

    def test_over_ul_rejected(self):
        ul = UpperLimits(vitamin_c_mg=100.0)
        tracker = DailyTracker(micronutrients_consumed={"vitamin_c_mg": 60.0})
        recipe = _make_recipe(
            "r1",
            micronutrients=MicronutrientProfile(vitamin_c_mg=50.0),
        )
        state = _make_state({0: tracker})
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc4_daily_ul(
            recipe, slot, 0, state, profile, ul
        ) is False

    def test_null_ul_ignored(self):
        ul = UpperLimits(vitamin_c_mg=None)
        tracker = DailyTracker(micronutrients_consumed={"vitamin_c_mg": 500.0})
        recipe = _make_recipe(
            "r1",
            micronutrients=MicronutrientProfile(vitamin_c_mg=500.0),
        )
        state = _make_state({0: tracker})
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc4_daily_ul(
            recipe, slot, 0, state, profile, ul
        ) is True

    def test_none_resolved_ul_allowed(self):
        tracker = DailyTracker(micronutrients_consumed={"vitamin_c_mg": 1000.0})
        recipe = _make_recipe("r1", micronutrients=MicronutrientProfile(vitamin_c_mg=500.0))
        state = _make_state({0: tracker})
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc4_daily_ul(
            recipe, slot, 0, state, profile, None
        ) is True

    def test_no_tracker_recipe_alone_over_ul_rejected(self):
        """When no tracker exists for the day, recipe alone is checked against UL."""
        ul = UpperLimits(vitamin_c_mg=50.0)
        recipe = _make_recipe(
            "r1",
            micronutrients=MicronutrientProfile(vitamin_c_mg=60.0),
        )
        state = _make_state({})
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc4_daily_ul(recipe, slot, 0, state, profile, ul) is False


# --- HC-5: Max daily calories ---


class TestHC5MaxDailyCalories:
    """HC-5: If max_daily_calories set, T_d.calories_consumed <= max_daily_calories; equality allowed."""

    def test_at_cap_allowed(self):
        profile = _make_profile(max_calories=2000)
        tracker = DailyTracker(calories_consumed=1500.0)
        recipe = _make_recipe("r1", calories=500.0)
        state = _make_state({0: tracker})
        slot = _make_slot()
        assert check_hc5_max_daily_calories(
            recipe, slot, 0, state, profile, None
        ) is True

    def test_over_cap_rejected(self):
        profile = _make_profile(max_calories=2000)
        tracker = DailyTracker(calories_consumed=1500.0)
        recipe = _make_recipe("r1", calories=600.0)
        state = _make_state({0: tracker})
        slot = _make_slot()
        assert check_hc5_max_daily_calories(
            recipe, slot, 0, state, profile, None
        ) is False

    def test_max_calories_none_no_check(self):
        profile = _make_profile(max_calories=None)
        tracker = DailyTracker(calories_consumed=5000.0)
        recipe = _make_recipe("r1", calories=1000.0)
        state = _make_state({0: tracker})
        slot = _make_slot()
        assert check_hc5_max_daily_calories(
            recipe, slot, 0, state, profile, None
        ) is True

    def test_no_tracker_recipe_alone_over_cap_rejected(self):
        """When no tracker exists for the day, recipe alone is checked against cap."""
        profile = _make_profile(max_calories=2000)
        recipe = _make_recipe("r1", calories=2500.0)
        state = _make_state({})
        slot = _make_slot()
        assert check_hc5_max_daily_calories(
            recipe, slot, 0, state, profile, None
        ) is False


# --- HC-6: Pinned assignment ---


class TestHC6PinnedAssignment:
    """HC-6: If slot is pinned, recipe_id must match pinned recipe."""

    def test_pinned_slot_wrong_recipe_rejected(self):
        profile = _make_profile(pinned={(1, 0): "pinned_recipe"})
        recipe = _make_recipe("other_recipe")
        state = _make_state({})
        slot = _make_slot()
        assert check_hc6_pinned_assignment(
            recipe, slot, 0, state, profile, None, slot_index=0
        ) is False

    def test_pinned_slot_matching_recipe_allowed(self):
        profile = _make_profile(pinned={(1, 0): "pinned_recipe"})
        recipe = _make_recipe("pinned_recipe")
        state = _make_state({})
        slot = _make_slot()
        assert check_hc6_pinned_assignment(
            recipe, slot, 0, state, profile, None, slot_index=0
        ) is True

    def test_unpinned_slot_any_recipe_allowed(self):
        profile = _make_profile(pinned={})
        recipe = _make_recipe("r1")
        state = _make_state({})
        slot = _make_slot()
        assert check_hc6_pinned_assignment(
            recipe, slot, 0, state, profile, None, slot_index=0
        ) is True


# --- HC-8: Cross-day non-workout reuse ---


class TestHC8CrossDayNonWorkoutReuse:
    """HC-8: Non-workout slot on day d>1: recipe_id not in T_{d-1}.non_workout_recipe_ids."""

    def test_non_workout_reuse_rejected(self):
        prev_tracker = DailyTracker(non_workout_recipe_ids={"r1"})
        state = _make_state({0: prev_tracker})
        recipe = _make_recipe("r1")
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc8_cross_day_non_workout_reuse(
            recipe, slot, 1, state, profile, None, is_workout_slot=False
        ) is False

    def test_workout_reuse_allowed(self):
        prev_tracker = DailyTracker(non_workout_recipe_ids={"r1"})
        state = _make_state({0: prev_tracker})
        recipe = _make_recipe("r1")
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc8_cross_day_non_workout_reuse(
            recipe, slot, 1, state, profile, None, is_workout_slot=True
        ) is True

    def test_day_1_exemption(self):
        prev_tracker = DailyTracker(non_workout_recipe_ids={"r1"})
        state = _make_state({0: prev_tracker})
        recipe = _make_recipe("r1")
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc8_cross_day_non_workout_reuse(
            recipe, slot, 0, state, profile, None, is_workout_slot=False
        ) is True

    def test_different_recipe_allowed(self):
        prev_tracker = DailyTracker(non_workout_recipe_ids={"r1"})
        state = _make_state({0: prev_tracker})
        recipe = _make_recipe("r2")
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc8_cross_day_non_workout_reuse(
            recipe, slot, 1, state, profile, None, is_workout_slot=False
        ) is True


# --- Integration-style: multiple HCs ---


class TestIntegrationMultipleHCs:
    """Combine multiple HCs; no scoring, no search."""

    def test_excluded_ingredient_and_cooking_time(self):
        recipe = _make_recipe(
            "r1",
            ingredients=[Ingredient("peanuts", 10.0, "g", False)],
            cooking_min=20,
        )
        profile = _make_profile(excluded=["peanuts"])
        state = _make_state({})
        slot = _make_slot(busyness=2)
        assert check_hc1_excluded_ingredients(
            recipe, slot, 0, state, profile, None
        ) is False
        assert check_hc3_cooking_time_bound(
            recipe, slot, 0, state, profile, None
        ) is False

    def test_ul_and_calorie_cap(self):
        ul = UpperLimits(vitamin_c_mg=100.0)
        tracker = DailyTracker(
            calories_consumed=1800.0,
            micronutrients_consumed={"vitamin_c_mg": 80.0},
        )
        recipe = _make_recipe(
            "r1",
            calories=200.0,
            micronutrients=MicronutrientProfile(vitamin_c_mg=20.0),
        )
        profile = _make_profile(max_calories=2000)
        state = _make_state({0: tracker})
        slot = _make_slot()
        assert check_hc4_daily_ul(recipe, slot, 0, state, profile, ul) is True
        assert check_hc5_max_daily_calories(recipe, slot, 0, state, profile, None) is True
        # Over UL
        recipe_bad = _make_recipe(
            "r2",
            calories=100.0,
            micronutrients=MicronutrientProfile(vitamin_c_mg=30.0),
        )
        assert check_hc4_daily_ul(recipe_bad, slot, 0, state, profile, ul) is False

    def test_same_day_reuse_and_cross_day_rule(self):
        # Day 0 had r1 in a non-workout slot; day 1 already used r1
        tracker0 = DailyTracker(used_recipe_ids=set(), non_workout_recipe_ids={"r1"})
        tracker1 = DailyTracker(used_recipe_ids={"r1"}, non_workout_recipe_ids=set())
        state = _make_state({0: tracker0, 1: tracker1})
        recipe_r1 = _make_recipe("r1")
        profile = _make_profile()
        slot = _make_slot()
        assert check_hc2_no_same_day_reuse(
            recipe_r1, slot, 1, state, profile, None
        ) is False
        assert check_hc8_cross_day_non_workout_reuse(
            recipe_r1, slot, 1, state, profile, None, is_workout_slot=False
        ) is False


# --- check_all ---


class TestCheckAll:
    """Combined evaluation returns True or list of violated HC identifiers."""

    def test_all_pass_returns_true(self):
        recipe = _make_recipe("r1", ingredients=[])
        slot = _make_slot()
        state = _make_state({0: DailyTracker()})
        profile = _make_profile()
        result = check_all(
            recipe, slot, 0, 0, state, profile, None, is_workout_slot=False
        )
        assert result is True

    def test_multiple_violations_return_list(self):
        recipe = _make_recipe(
            "r1",
            ingredients=[Ingredient("peanuts", 10.0, "g", False)],
            cooking_min=60,
        )
        slot = _make_slot(busyness=2)
        state = _make_state({0: DailyTracker(used_recipe_ids={"r1"})})
        profile = _make_profile(excluded=["peanuts"])
        result = check_all(
            recipe, slot, 0, 0, state, profile, None, is_workout_slot=False
        )
        assert isinstance(result, list)
        assert "HC-1" in result
        assert "HC-2" in result
        assert "HC-3" in result
