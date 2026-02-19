"""Phase 7 tests: Backtracking and search orchestration. Spec Sections 6.1–6.6, 9, 10, 11."""

from __future__ import annotations

import pytest

from src.data_layer.models import Ingredient, MicronutrientProfile, NutritionProfile
from src.planning.phase0_models import MealSlot, PlanningRecipe, PlanningUserProfile
from src.planning.phase0_models import Assignment
from src.planning.phase7_search import (
    DEFAULT_ATTEMPT_LIMIT,
    PlanFailure,
    PlanSuccess,
    SearchStats,
    run_meal_plan_search,
)


def _make_slot(busyness: int = 2) -> MealSlot:
    return MealSlot("12:00", busyness, "lunch")


def _make_schedule(ndays: int = 1, slots_per_day: int = 2) -> list:
    return [[_make_slot() for _ in range(slots_per_day)] for _ in range(ndays)]


def _make_recipe(
    rid: str,
    calories: float = 1000.0,
    protein: float = 50.0,
    fat: float = 32.0,
    carbs: float = 125.0,
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


def _make_profile(
    schedule: list,
    daily_calories: int = 2000,
    daily_protein_g: float = 100.0,
    daily_fat_g: tuple[float, float] = (50.0, 80.0),
    daily_carbs_g: float = 250.0,
    pinned_assignments: dict | None = None,
    excluded_ingredients: list | None = None,
    micronutrient_targets: dict | None = None,
) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=daily_calories,
        daily_protein_g=daily_protein_g,
        daily_fat_g=daily_fat_g,
        daily_carbs_g=daily_carbs_g,
        schedule=schedule,
        pinned_assignments=pinned_assignments or {},
        excluded_ingredients=excluded_ingredients or [],
        micronutrient_targets=micronutrient_targets or {},
    )


# --- Integration: success D=1, D=2, D=7 no pins ---


class TestSearchSuccessNoPins:
    """D=1, D=2, D=7 no pins; produces valid plan when feasible."""

    def test_d1_two_slots_success(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
        ]
        ok, result = run_meal_plan_search(profile, pool, 1, None)
        assert ok is True
        assert isinstance(result, PlanSuccess)
        assert len(result.assignments) == 2
        assert result.daily_trackers and 0 in result.daily_trackers
        assert result.daily_trackers[0].slots_assigned == 2
        assert result.daily_trackers[0].calories_consumed == 2000.0

    def test_d2_four_slots_success(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        ok, result = run_meal_plan_search(profile, pool, 2, None)
        assert ok is True
        assert isinstance(result, PlanSuccess)
        assert len(result.assignments) == 4
        assert result.weekly_tracker.days_completed == 2

    def test_d7_success(self):
        schedule = _make_schedule(ndays=7, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [_make_recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(14)]
        ok, result = run_meal_plan_search(profile, pool, 7, None)
        assert ok is True
        assert isinstance(result, PlanSuccess)
        assert len(result.assignments) == 14
        assert result.weekly_tracker.days_completed == 7


# --- Integration: with pinned slots ---


class TestSearchWithPinnedSlots:
    def test_d2_with_one_pinned_success(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(
            schedule,
            pinned_assignments={(1, 0): "r1"},
        )
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        ok, result = run_meal_plan_search(profile, pool, 2, None)
        assert ok is True, getattr(result, "constraint_detail", result)
        assert isinstance(result, PlanSuccess)
        assert Assignment(0, 0, "r1") in result.assignments
        assert len(result.assignments) == 4


# --- Failure modes ---


class TestFailureModes:
    """FM-1 through FM-5 and report structure."""

    def test_fm3_pinned_conflict_schedule_length(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [_make_recipe("r1"), _make_recipe("r2")]
        ok, result = run_meal_plan_search(profile, pool, 3, None)
        assert ok is False
        assert isinstance(result, PlanFailure)
        assert result.failure_mode == "FM-3"
        assert result.constraint_detail is not None

    def test_fm3_pinned_invalid_hc1(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(
            schedule,
            pinned_assignments={(1, 0): "r_bad"},
            excluded_ingredients=["peanut"],
        )
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe(
                "r_bad",
                1000.0,
                50.0,
                32.0,
                125.0,
                ingredients=[Ingredient("peanut", 10.0, "g", False, "g", 10.0)],
            ),
        ]
        ok, result = run_meal_plan_search(profile, pool, 1, None)
        assert ok is False
        assert isinstance(result, PlanFailure)
        assert result.failure_mode == "FM-3"
        assert result.constraint_detail is not None

    def test_fm1_insufficient_pool_empty_candidates(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [_make_recipe("r1", 1000.0, 50.0, 32.0, 125.0)]
        ok, result = run_meal_plan_search(profile, pool, 1, None)
        assert ok is False
        assert isinstance(result, PlanFailure)
        assert result.failure_mode == "FM-1"
        assert result.day_index is not None
        assert result.slot_index is not None
        assert result.attempt_count >= 0
        assert hasattr(result, "best_partial_assignments")
        assert hasattr(result, "best_partial_daily_trackers")

    def test_fm2_daily_infeasible_exhaustion(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(
            schedule,
            daily_protein_g=100.0,
        )
        pool = [
            _make_recipe("r1", 1000.0, 30.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 30.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 30.0, 32.0, 125.0),
        ]
        ok, result = run_meal_plan_search(profile, pool, 1, None)
        assert ok is False
        assert isinstance(result, PlanFailure)
        assert result.failure_mode in ("FM-1", "FM-2")
        assert hasattr(result, "best_partial_assignments")
        assert hasattr(result, "attempt_count")

    def test_fm5_attempt_limit(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
        ]
        ok, result = run_meal_plan_search(profile, pool, 1, None, attempt_limit=1)
        assert ok is False
        assert isinstance(result, PlanFailure)
        assert result.failure_mode == "FM-5"
        assert result.attempt_count == 1
        assert hasattr(result, "best_partial_assignments")
        assert hasattr(result, "best_partial_daily_trackers")

    def test_fm4_weekly_validation_failure(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(
            schedule,
            micronutrient_targets={"iron_mg": 1.0},
        )
        zero_iron = MicronutrientProfile(iron_mg=0.0)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0, micronutrients=zero_iron),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0, micronutrients=zero_iron),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0, micronutrients=zero_iron),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0, micronutrients=zero_iron),
        ]
        ok, result = run_meal_plan_search(profile, pool, 2, None)
        assert ok is False
        assert isinstance(result, PlanFailure)
        assert result.failure_mode in ("FM-1", "FM-2", "FM-4")
        assert hasattr(result, "attempt_count")


# --- Determinism ---


class TestDeterminism:
    def test_same_inputs_same_plan(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        ok1, result1 = run_meal_plan_search(profile, pool, 2, None)
        profile2 = _make_profile(schedule)
        ok2, result2 = run_meal_plan_search(profile2, pool, 2, None)
        assert ok1 is ok2
        assert ok1 is True
        assert [a for a in result1.assignments] == [a for a in result2.assignments]

    def test_stats_enabled_vs_disabled_identical_plan(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        ok_no_stats, result_no = run_meal_plan_search(profile, pool, 2, None)
        profile2 = _make_profile(schedule)
        stats = SearchStats(enabled=True)
        ok_with_stats, result_with = run_meal_plan_search(profile2, pool, 2, None, stats=stats)
        assert ok_no_stats is ok_with_stats
        assert ok_no_stats is True
        assert [a for a in result_no.assignments] == [a for a in result_with.assignments]
        assert stats.total_attempts == 4
        assert stats.total_runtime() >= 0
        assert len(stats.branching_factors) <= 4


# --- Report structure ---


class TestFailureReportStructure:
    def test_fm2_has_required_fields(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(schedule, daily_protein_g=100.0)
        pool = [
            _make_recipe("r1", 1000.0, 30.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 30.0, 32.0, 125.0),
        ]
        ok, result = run_meal_plan_search(profile, pool, 1, None)
        assert ok is False
        assert result.failure_mode in ("FM-1", "FM-2")
        assert isinstance(result.failure_mode, str)
        assert isinstance(result.best_partial_assignments, list)
        assert isinstance(result.best_partial_daily_trackers, dict)
        assert isinstance(result.attempt_count, int)
        assert result.attempt_count >= 0

    def test_attempt_limit_configurable_default(self):
        assert DEFAULT_ATTEMPT_LIMIT > 0
        assert isinstance(DEFAULT_ATTEMPT_LIMIT, int)


# --- Optional SearchStats instrumentation ---


class TestSearchStatsInstrumentation:
    def test_stats_disabled_by_default(self):
        stats = SearchStats()
        assert stats.enabled is False

    def test_stats_populated_when_enabled(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        stats = SearchStats(enabled=True)
        ok, result = run_meal_plan_search(profile, pool, 2, None, stats=stats)
        assert ok is True
        assert stats.total_attempts == 4
        assert stats.total_runtime() >= 0
        assert isinstance(stats.branching_factors, dict)
        assert stats.time_per_attempt() >= 0

    def test_d7_timing_measurable(self):
        schedule = _make_schedule(ndays=7, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [_make_recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(14)]
        stats = SearchStats(enabled=True)
        ok, result = run_meal_plan_search(profile, pool, 7, None, stats=stats)
        assert ok is True
        assert stats.total_attempts == 14
        assert stats.total_runtime() >= 0
        assert stats.time_per_attempt() >= 0

    def test_single_day_mode_stats(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
        ]
        stats = SearchStats(enabled=True)
        ok, result = run_meal_plan_search(profile, pool, 1, None, stats=stats)
        assert ok is True
        assert stats.total_attempts == 2
        assert stats.total_runtime() >= 0
