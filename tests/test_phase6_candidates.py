"""Phase 6 unit tests: candidate generation. Spec Section 6.3 steps 1–7."""

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
    WeeklyTracker,
)
from src.planning.phase3_feasibility import MacroBoundsPrecomputation, precompute_macro_bounds
from src.planning.phase6_candidates import (
    CandidateGenerationResult,
    generate_candidates,
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
        nutrition=NutritionProfile(
            calories, protein, fat, carbs,
            micronutrients=micronutrients or MicronutrientProfile(),
        ),
        primary_carb_contribution=None,
    )


def _make_slot(busyness: int = 2) -> MealSlot:
    return MealSlot("12:00", busyness, "lunch")


def _feasible_recipe(rid: str, calories: float = 1000.0, **kwargs) -> PlanningRecipe:
    """Recipe that fits 2-slot 2000 cal day: 50 pro, 32 fat, 125 carbs per slot."""
    defaults = dict(protein=50.0, fat=32.0, carbs=125.0, calories=calories)
    defaults.update(kwargs)
    return _make_recipe(rid, **defaults)


def _make_schedule(ndays: int = 1, slots_per_day: int = 2) -> list:
    return [[_make_slot() for _ in range(slots_per_day)] for _ in range(ndays)]


def _make_profile(
    excluded: list | None = None,
    max_daily_calories: int | None = None,
    daily_calories: int = 2000,
    daily_protein_g: float = 100.0,
    daily_fat_g: tuple[float, float] = (50.0, 80.0),
    daily_carbs_g: float = 250.0,
) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=daily_calories,
        daily_protein_g=daily_protein_g,
        daily_fat_g=daily_fat_g,
        daily_carbs_g=daily_carbs_g,
        excluded_ingredients=excluded or [],
        max_daily_calories=max_daily_calories,
    )


def _macro_bounds(recipes: list) -> MacroBoundsPrecomputation:
    return precompute_macro_bounds(recipes, max_slots=8)


# --- HC-1: Excluded ingredients ---


class TestHC1Filtering:
    def test_recipe_excluded_by_hc1(self):
        profile = _make_profile(excluded=["peanut"])
        r_ok = _feasible_recipe("r1", ingredients=[Ingredient("egg", 1.0, "unit", False, "", 0.0)])
        r_bad = _feasible_recipe("r2", ingredients=[Ingredient("peanut", 10.0, "g", False, "g", 10.0)])
        pool = [r_ok, r_bad]
        schedule = _make_schedule(1, 2)
        state_0 = {0: DailyTracker(slots_assigned=0, slots_total=2)}
        res = generate_candidates(
            pool, 0, 0, state_0, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == {("r1", 0)}
        assert not res.trigger_backtrack


# --- HC-2: Same-day reuse ---


class TestHC2Filtering:
    def test_recipe_excluded_by_hc2(self):
        profile = _make_profile()
        r1 = _feasible_recipe("r1")
        r2 = _feasible_recipe("r2")
        pool = [r1, r2]
        tracker = DailyTracker(
            used_recipe_ids={"r1"},
            calories_consumed=1000.0, protein_consumed=50.0, fat_consumed=32.0, carbs_consumed=125.0,
            slots_assigned=1, slots_total=2,
        )
        schedule = _make_schedule(1, 2)
        res = generate_candidates(
            pool, 0, 1, {0: tracker}, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == {("r2", 0)}
        assert not res.trigger_backtrack


# --- HC-3: Cooking time ---


class TestHC3Filtering:
    def test_recipe_excluded_by_hc3(self):
        slot = MealSlot("12:00", 2, "lunch")
        schedule = [[slot, _make_slot()]]
        r_ok = _feasible_recipe("r1", cooking_min=10)
        r_bad = _feasible_recipe("r2", cooking_min=20)
        pool = [r_ok, r_bad]
        profile = _make_profile()
        state_0 = {0: DailyTracker(slots_assigned=0, slots_total=2)}
        res = generate_candidates(
            pool, 0, 0, state_0, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == {("r1", 0)}
        assert not res.trigger_backtrack


# --- HC-5: Max daily calories ---


class TestHC5Filtering:
    def test_recipe_excluded_by_hc5(self):
        profile = _make_profile(daily_calories=600, max_daily_calories=600, daily_protein_g=40.0, daily_fat_g=(30.0, 40.0), daily_carbs_g=60.0)
        tracker = DailyTracker(
            calories_consumed=200.0, protein_consumed=20.0, fat_consumed=15.0, carbs_consumed=30.0,
            slots_assigned=1, slots_total=2,
        )
        r_ok = _make_recipe("r1", calories=400.0, protein=20.0, fat=15.0, carbs=30.0)
        r_bad = _make_recipe("r2", calories=500.0, protein=20.0, fat=15.0, carbs=30.0)
        pool = [r_ok, r_bad]
        schedule = _make_schedule(1, 2)
        res = generate_candidates(
            pool, 0, 1, {0: tracker}, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == {("r1", 0)}
        assert "r2" in res.calorie_excess_rejections
        assert not res.trigger_backtrack


# --- HC-8: Consecutive-day non-workout ---


class TestHC8Filtering:
    def test_recipe_excluded_by_hc8_when_d1_and_non_workout(self):
        profile = _make_profile()
        r1 = _feasible_recipe("r1")
        r2 = _feasible_recipe("r2")
        pool = [r1, r2]
        prev_tracker = DailyTracker(
            used_recipe_ids={"r1"},
            non_workout_recipe_ids={"r1"},
            slots_assigned=2,
            slots_total=2,
        )
        schedule = _make_schedule(2, 2)
        state_1 = {0: prev_tracker, 1: DailyTracker(slots_assigned=0, slots_total=2)}
        res = generate_candidates(
            pool, 1, 0, state_1, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == {("r2", 0)}
        assert not res.trigger_backtrack

    def test_hc8_no_restriction_on_day_0(self):
        profile = _make_profile()
        r1 = _feasible_recipe("r1")
        pool = [r1]
        schedule = _make_schedule(1, 2)
        res = generate_candidates(
            pool, 0, 0, {}, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == {("r1", 0)}


# --- FC-1, FC-2, FC-3 ---


class TestFeasibilityFiltering:
    def test_recipe_fails_fc1_calorie_feasibility(self):
        profile = _make_profile(daily_calories=2000, max_daily_calories=2500)
        tracker = DailyTracker(
            calories_consumed=1900.0, protein_consumed=50.0, fat_consumed=32.0, carbs_consumed=125.0,
            slots_assigned=1, slots_total=2,
        )
        r_ok = _make_recipe("r1", calories=150.0, protein=50.0, fat=32.0, carbs=125.0)
        r_bad = _make_recipe("r2", calories=800.0, protein=50.0, fat=32.0, carbs=125.0)
        pool = [r_ok, r_bad]
        schedule = _make_schedule(1, 2)
        res = generate_candidates(
            pool, 0, 1, {0: tracker}, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == {("r1", 0)}

    def test_recipe_fails_fc1_calorie_overflow_recorded(self):
        profile = _make_profile(max_daily_calories=600)
        tracker = DailyTracker(calories_consumed=200.0, slots_assigned=1, slots_total=2)
        r_bad = _make_recipe("r2", calories=500.0)
        pool = [r_bad]
        schedule = _make_schedule(1, 2)
        res = generate_candidates(
            pool, 0, 1, {0: tracker}, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == set()
        assert "r2" in res.calorie_excess_rejections

    def test_recipe_fails_fc2_macro_feasibility(self):
        profile = _make_profile(daily_protein_g=100.0, daily_carbs_g=200.0)
        tracker = DailyTracker(
            protein_consumed=95.0, carbs_consumed=100.0, fat_consumed=60.0, calories_consumed=1200.0,
            slots_assigned=1, slots_total=2,
        )
        r_high_protein = _make_recipe("r1", protein=15.0, carbs=50.0, fat=10.0, calories=400.0)
        r_zero_protein = _make_recipe("r2", protein=0.0, carbs=100.0, fat=10.0, calories=500.0)
        pool = [r_high_protein, r_zero_protein]
        macro = _macro_bounds(pool)
        schedule = _make_schedule(1, 2)
        res = generate_candidates(
            pool, 0, 1, {0: tracker}, WeeklyTracker(), schedule,
            profile, None, macro,
        )
        assert res.candidates == {("r2", 0)}

    def test_recipe_fails_fc3_ul_feasibility(self):
        profile = _make_profile(daily_calories=2000, daily_protein_g=80.0, daily_fat_g=(52.0, 80.0), daily_carbs_g=205.0)
        ul = UpperLimits(vitamin_a_ug=900.0)
        tracker = DailyTracker(
            calories_consumed=1200.0, protein_consumed=30.0, fat_consumed=20.0, carbs_consumed=80.0,
            micronutrients_consumed={"vitamin_a_ug": 500.0},
            slots_assigned=1, slots_total=2,
        )
        r_ok = _make_recipe("r1", calories=800.0, protein=50.0, fat=32.0, carbs=125.0, micronutrients=MicronutrientProfile(vitamin_a_ug=300.0))
        r_bad = _make_recipe("r2", calories=800.0, protein=50.0, fat=32.0, carbs=125.0, micronutrients=MicronutrientProfile(vitamin_a_ug=500.0))
        pool = [r_ok, r_bad]
        schedule = _make_schedule(1, 2)
        res = generate_candidates(
            pool, 0, 1, {0: tracker}, WeeklyTracker(), schedule,
            profile, ul, _macro_bounds(pool),
        )
        assert res.candidates == {("r1", 0)}


# --- Backtrack signal ---


class TestBacktrackSignal:
    def test_empty_candidates_triggers_backtrack(self):
        profile = _make_profile(excluded=["x"])
        r = _make_recipe("r1", ingredients=[Ingredient("x", 1.0, "g", False, "g", 1.0)])
        pool = [r]
        schedule = _make_schedule(1, 2)
        res = generate_candidates(
            pool, 0, 0, {}, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == set()
        assert res.trigger_backtrack is True

    def test_valid_scenario_no_backtrack(self):
        profile = _make_profile()
        r1 = _feasible_recipe("r1")
        r2 = _feasible_recipe("r2")
        pool = [r1, r2]
        schedule = _make_schedule(1, 2)
        state_0 = {0: DailyTracker(slots_assigned=0, slots_total=2)}
        res = generate_candidates(
            pool, 0, 0, state_0, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == {("r1", 0), ("r2", 0)}
        assert res.trigger_backtrack is False

    def test_future_slot_zero_eligible_triggers_backtrack(self):
        # HC-8: day 1, both slots non-workout. Day 0 used r1 and r2 in non-workout.
        # Pool has only r1 and r2. At day 1 slot 0, HC-8 excludes both → empty C → backtrack.
        # But we want to test the *future-slot* path, so we need slot 0 to have candidates
        # while a future slot does not.
        # Setup: day 1, 2 slots. Pool = {r1, r2, r3}. Day 0 used r1, r2 in non-workout.
        # Slot 0 on day 1: HC-8 excludes r1, r2 → only r3 survives → candidates = {r3}.
        # Future slot 1: HC-2 uses current used_recipe_ids (empty, optimistic). HC-8 still
        # excludes r1, r2 → only r3. So future slot has {r3} → no trigger.
        # Instead: make all recipes excluded by HC-1 for the future slot's cooking time.
        # Simpler: slot 1 has busyness=1 (max 5 min). All recipes have cooking_time=10.
        # At slot 0 (busyness=2, max 15): all pass HC-3. At slot 1 (busyness=1, max 5): all fail HC-3.
        profile = _make_profile()
        r1 = _feasible_recipe("r1", cooking_min=10)
        r2 = _feasible_recipe("r2", cooking_min=10)
        pool = [r1, r2]
        slot_0 = MealSlot("12:00", 2, "lunch")   # max 15 min
        slot_1 = MealSlot("18:00", 1, "dinner")   # max 5 min
        schedule = [[slot_0, slot_1]]
        state_0 = {0: DailyTracker(slots_assigned=0, slots_total=2)}
        res = generate_candidates(
            pool, 0, 0, state_0, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert res.candidates == {("r1", 0), ("r2", 0)}
        assert res.trigger_backtrack is True


# --- Result shape ---


class TestResultShape:
    def test_result_has_required_fields(self):
        profile = _make_profile()
        pool = [_feasible_recipe("r1")]
        schedule = _make_schedule(1, 2)
        res = generate_candidates(
            pool, 0, 0, {}, WeeklyTracker(), schedule,
            profile, None, _macro_bounds(pool),
        )
        assert isinstance(res, CandidateGenerationResult)
        assert isinstance(res.candidates, set)
        assert all(isinstance(x, tuple) and len(x) == 2 for x in res.candidates)
        assert isinstance(res.trigger_backtrack, bool)
        assert isinstance(res.calorie_excess_rejections, set)
