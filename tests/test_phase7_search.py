"""Phase 7 tests: Backtracking and search orchestration. Spec Sections 6.1–6.6, 9, 10, 11."""

from __future__ import annotations

import pytest

from src.data_layer.models import Ingredient, MicronutrientProfile, NutritionProfile, UpperLimits
from src.planning.phase0_models import MealSlot, PlanningRecipe, PlanningUserProfile
from src.planning.phase0_models import Assignment
from src.planning.phase10_reporting import MealPlanResult
from src.planning.phase7_search import (
    DEFAULT_ATTEMPT_LIMIT,
    PlannerStateError,
    SearchStats,
    run_meal_plan_search,
    _validate_planner_state,
)


def _make_slot(
    busyness: int = 2,
    *,
    required_tag_slugs: list[str] | None = None,
    preferred_tag_slugs: list[str] | None = None,
) -> MealSlot:
    return MealSlot(
        "12:00",
        busyness,
        "lunch",
        required_tag_slugs=required_tag_slugs,
        preferred_tag_slugs=preferred_tag_slugs,
    )


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
    canonical_tag_slugs: set[str] | None = None,
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
        canonical_tag_slugs=set(canonical_tag_slugs or set()),
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
    max_daily_calories: int | None = None,
    micronutrient_weekly_min_fraction: float = 1.0,
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
        max_daily_calories=max_daily_calories,
        micronutrient_weekly_min_fraction=micronutrient_weekly_min_fraction,
    )


def _assert_weekly_equals_sum_daily(result: MealPlanResult, tol: float = 1e-6) -> None:
    """Invariant: weekly_totals must equal sum of daily_trackers (macros)."""
    if not result.success or not result.daily_trackers or not result.weekly_tracker:
        return
    wt = result.weekly_tracker.weekly_totals
    sum_cal = sum(result.daily_trackers[d].calories_consumed for d in sorted(result.daily_trackers))
    sum_p = sum(result.daily_trackers[d].protein_consumed for d in sorted(result.daily_trackers))
    sum_f = sum(result.daily_trackers[d].fat_consumed for d in sorted(result.daily_trackers))
    sum_c = sum(result.daily_trackers[d].carbs_consumed for d in sorted(result.daily_trackers))
    assert abs(wt.calories - sum_cal) <= tol, f"weekly calories {wt.calories} != sum(daily) {sum_cal}"
    assert abs(wt.protein_g - sum_p) <= tol, f"weekly protein {wt.protein_g} != sum(daily) {sum_p}"
    assert abs(wt.fat_g - sum_f) <= tol, f"weekly fat {wt.fat_g} != sum(daily) {sum_f}"
    assert abs(wt.carbs_g - sum_c) <= tol, f"weekly carbs {wt.carbs_g} != sum(daily) {sum_c}"


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
        result = run_meal_plan_search(profile, pool, 1, None)
        assert isinstance(result, MealPlanResult)
        assert result.success is True
        assert result.plan is not None and len(result.plan) == 2
        assert result.daily_trackers and 0 in result.daily_trackers
        assert result.daily_trackers[0].slots_assigned == 2
        assert result.daily_trackers[0].calories_consumed == 2000.0
        _assert_weekly_equals_sum_daily(result)

    def test_d2_four_slots_success(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        result = run_meal_plan_search(profile, pool, 2, None)
        assert isinstance(result, MealPlanResult)
        assert result.success is True
        assert result.plan is not None and len(result.plan) == 4
        assert result.weekly_tracker.days_completed == 2
        _assert_weekly_equals_sum_daily(result)

    def test_d7_success(self):
        schedule = _make_schedule(ndays=7, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [_make_recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(14)]
        result = run_meal_plan_search(profile, pool, 7, None)
        assert isinstance(result, MealPlanResult)
        assert result.success is True
        assert result.plan is not None and len(result.plan) == 14
        assert result.weekly_tracker.days_completed == 7
        _assert_weekly_equals_sum_daily(result)

    def test_success_days_completed_invariant(self):
        """On success: days_completed <= D and len(daily_trackers) == days_completed."""
        for D in (1, 2, 3):
            schedule = _make_schedule(ndays=D, slots_per_day=2)
            profile = _make_profile(schedule)
            pool = [_make_recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(D * 2)]
            result = run_meal_plan_search(profile, pool, D, None)
            assert result.success is True, f"D={D}"
            wt = result.weekly_tracker
            assert wt is not None
            assert wt.days_completed <= D
            assert result.daily_trackers is not None
            assert len(result.daily_trackers) == wt.days_completed
            _assert_weekly_equals_sum_daily(result)

    def test_weekly_totals_equal_sum_daily_with_max_daily_calories(self):
        """With max_daily_calories (backtracking), weekly must still equal sum(daily)."""
        schedule = _make_schedule(ndays=3, slots_per_day=2)
        profile = _make_profile(schedule, max_daily_calories=2200, daily_calories=2000)
        pool = [
            _make_recipe("r1", 500.0, 25.0, 16.0, 62.0),
            _make_recipe("r2", 500.0, 25.0, 16.0, 62.0),
            _make_recipe("r3", 500.0, 25.0, 16.0, 62.0),
            _make_recipe("r4", 500.0, 25.0, 16.0, 62.0),
            _make_recipe("r5", 500.0, 25.0, 16.0, 62.0),
            _make_recipe("r6", 500.0, 25.0, 16.0, 62.0),
        ]
        result = run_meal_plan_search(profile, pool, 3, None)
        if result.success:
            _assert_weekly_equals_sum_daily(result)

    def test_weekly_equals_sum_completed_days_after_backtracking(self):
        """Regression: after repeated backtracking, weekly totals remain equal to sum of completed day totals."""
        schedule = _make_schedule(ndays=3, slots_per_day=2)
        profile = _make_profile(schedule, max_daily_calories=2100, daily_calories=2000)
        pool = [
            _make_recipe(f"r{i}", 500.0, 25.0, 16.0, 62.0) for i in range(8)
        ]
        result = run_meal_plan_search(profile, pool, 3, None)
        if result.success and result.weekly_tracker and result.daily_trackers:
            _assert_weekly_equals_sum_daily(result)

    def test_no_candidate_skipping_on_rewind(self):
        """Regression: backtrack does not skip next candidate (pointer advanced only at selection time)."""
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.success is True
        assert result.plan is not None and len(result.plan) == 4
        _assert_weekly_equals_sum_daily(result)


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
        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.success is True, getattr(result, "report", result)
        assert isinstance(result, MealPlanResult)
        assert result.plan is not None
        assert Assignment(0, 0, "r1") in result.plan
        assert len(result.plan) == 4
        _assert_weekly_equals_sum_daily(result)

    def test_pinned_recipe_precedence_over_required_tags_on_same_slot(self):
        schedule = [[
            _make_slot(required_tag_slugs=["high-protein"]),
            _make_slot(required_tag_slugs=["high-protein"]),
        ]]
        profile = _make_profile(
            schedule,
            pinned_assignments={(1, 0): "r_pinned"},
        )
        pool = [
            _make_recipe(
                "r_pinned",
                1000.0,
                50.0,
                32.0,
                125.0,
                canonical_tag_slugs={"comfort-food"},
            ),
            _make_recipe(
                "r_match",
                1000.0,
                50.0,
                32.0,
                125.0,
                canonical_tag_slugs={"high-protein"},
            ),
        ]

        result = run_meal_plan_search(profile, pool, 1, None)

        assert result.success is True, getattr(result, "report", result)
        assert result.plan is not None
        assert Assignment(0, 0, "r_pinned") in result.plan
        assert Assignment(0, 1, "r_match") in result.plan


# --- Failure modes ---


class TestFailureModes:
    """FM-1 through FM-5 and report structure."""

    def test_fm3_pinned_conflict_schedule_length(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [_make_recipe("r1"), _make_recipe("r2")]
        result = run_meal_plan_search(profile, pool, 3, None)
        assert result.success is False
        assert isinstance(result, MealPlanResult)
        assert result.failure_mode == "FM-3"
        assert result.report.get("pinned_conflicts")

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
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert isinstance(result, MealPlanResult)
        assert result.failure_mode == "FM-3"
        assert result.report.get("pinned_conflicts")

    def test_fm1_insufficient_pool_empty_candidates(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [_make_recipe("r1", 1000.0, 50.0, 32.0, 125.0)]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert isinstance(result, MealPlanResult)
        assert result.failure_mode == "FM-1"
        unfillable = result.report.get("unfillable_slots", [])
        assert len(unfillable) >= 1
        assert result.stats is not None and result.stats.get("attempts", 0) >= 0
        assert "closest_plan" in result.report or "best_plan" in result.report or result.report.get("unfillable_slots")

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
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert isinstance(result, MealPlanResult)
        assert result.failure_mode in ("FM-1", "FM-2")
        assert result.report
        assert result.stats is not None and "attempts" in result.stats

    def test_fm5_attempt_limit(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
        ]
        result = run_meal_plan_search(profile, pool, 1, None, attempt_limit=1)
        assert result.success is False
        assert isinstance(result, MealPlanResult)
        assert result.failure_mode == "FM-5"
        assert result.stats is not None and result.stats.get("attempts") == 1
        assert result.report.get("search_exhaustive") is False
        assert "attempts" in result.report and result.report["attempts"] == 1

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
        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.success is False
        assert isinstance(result, MealPlanResult)
        assert result.failure_mode in ("FM-1", "FM-2", "FM-4")
        assert result.stats is not None and "attempts" in result.stats


class TestWeeklyMicronutrientTau:
    """τ scales weekly floor; UL and structural checks stay independent of 'relaxing' RDI floor."""

    def test_tau_one_explicit_matches_default(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        micro = MicronutrientProfile(iron_mg=4.5)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0, micronutrients=micro),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0, micronutrients=micro),
        ]
        p_default = _make_profile(schedule, micronutrient_targets={"iron_mg": 10.0})
        p_explicit = _make_profile(
            schedule,
            micronutrient_targets={"iron_mg": 10.0},
            micronutrient_weekly_min_fraction=1.0,
        )
        r_a = run_meal_plan_search(p_default, pool, 1, None)
        r_b = run_meal_plan_search(p_explicit, pool, 1, None)
        assert r_a.success is False and r_b.success is False
        assert r_a.failure_mode == r_b.failure_mode == "FM-4"
        assert r_a.termination_code == r_b.termination_code == "TC-2"

    def test_relaxed_tau_allows_plan_strict_fm4_fails(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        micro = MicronutrientProfile(iron_mg=4.5)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0, micronutrients=micro),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0, micronutrients=micro),
        ]
        profile_lo = _make_profile(
            schedule,
            micronutrient_targets={"iron_mg": 10.0},
            micronutrient_weekly_min_fraction=0.9,
        )
        profile_hi = _make_profile(
            schedule,
            micronutrient_targets={"iron_mg": 10.0},
            micronutrient_weekly_min_fraction=1.0,
        )
        r_lo = run_meal_plan_search(profile_lo, pool, 1, None)
        r_hi = run_meal_plan_search(profile_hi, pool, 1, None)
        assert r_lo.success is True
        assert r_hi.success is False
        assert r_hi.failure_mode == "FM-4"
        assert r_lo.warning is not None
        assert "micronutrient_soft_deficit" in r_lo.warning
        soft = r_lo.warning["micronutrient_soft_deficit"]
        assert any(e["nutrient"] == "iron_mg" for e in soft)

    def test_ul_still_blocks_when_tau_relaxed(self):
        schedule = _make_schedule(ndays=1, slots_per_day=1)
        ul = UpperLimits(vitamin_c_mg=100.0)
        pool = [
            _make_recipe(
                "r1",
                2000.0,
                100.0,
                65.0,
                253.75,
                micronutrients=MicronutrientProfile(vitamin_c_mg=150.0),
            ),
        ]
        profile = _make_profile(
            schedule,
            micronutrient_targets={"vitamin_c_mg": 1.0},
            micronutrient_weekly_min_fraction=0.9,
        )
        result = run_meal_plan_search(profile, pool, 1, ul)
        assert result.success is False


class TestTauStrictGoldenSnapshot:
    """Frozen expected outputs for τ=1.0 (default vs explicit); catches ordering/termination regressions."""

    def test_golden_d1_two_slots_default_vs_explicit_tau_one(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
        ]
        expected_assignments = [
            Assignment(0, 0, "r1", 0),
            Assignment(0, 1, "r2", 0),
        ]
        p_default = _make_profile(schedule)
        p_explicit = _make_profile(schedule, micronutrient_weekly_min_fraction=1.0)
        r_def = run_meal_plan_search(p_default, pool, 1, None)
        r_exp = run_meal_plan_search(p_explicit, pool, 1, None)
        for label, r in ("default", r_def), ("explicit_tau_1", r_exp):
            assert r.success is True, label
            assert r.termination_code == "TC-4", label
            assert r.plan == expected_assignments, label
            assert r.warning is None, label


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
        result1 = run_meal_plan_search(profile, pool, 2, None)
        profile2 = _make_profile(schedule)
        result2 = run_meal_plan_search(profile2, pool, 2, None)
        assert result1.success is result2.success
        assert result1.success is True
        assert result1.plan is not None and result2.plan is not None
        assert [a for a in result1.plan] == [a for a in result2.plan]

    def test_stats_enabled_vs_disabled_identical_plan(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        result_no = run_meal_plan_search(profile, pool, 2, None)
        profile2 = _make_profile(schedule)
        stats = SearchStats(enabled=True)
        result_with = run_meal_plan_search(profile2, pool, 2, None, stats=stats)
        assert result_no.success is result_with.success
        assert result_no.success is True
        assert result_no.plan is not None and result_with.plan is not None
        assert [a for a in result_no.plan] == [a for a in result_with.plan]
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
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert result.failure_mode in ("FM-1", "FM-2")
        assert isinstance(result.failure_mode, str)
        assert "failed_days" in result.report or "unfillable_slots" in result.report
        assert "closest_plan" in result.report or "unfillable_slots" in result.report
        assert result.stats is not None and isinstance(result.stats.get("attempts", 0), int)
        assert result.stats.get("attempts", 0) >= 0

    def test_attempt_limit_configurable_default(self):
        assert DEFAULT_ATTEMPT_LIMIT > 0
        assert isinstance(DEFAULT_ATTEMPT_LIMIT, int)


# --- Micronutrient accumulation ---


class TestDailyTrackerMicronutrients:
    """Verify daily tracker accumulates micronutrients when recipes have them."""

    def test_daily_tracker_accumulates_micronutrients(self):
        """Assigning a recipe with micronutrients updates daily_tracker.micronutrients_consumed."""
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(schedule)
        # Use 1000 cal each so daily total 2000 meets profile.daily_calories (FC-2)
        recipe_with_iron = _make_recipe(
            "r1",
            1000.0,
            50.0,
            32.0,
            125.0,
            micronutrients=MicronutrientProfile(iron_mg=3.0, vitamin_c_mg=10.0),
        )
        pool = [
            recipe_with_iron,
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is True
        assert result.daily_trackers is not None and 0 in result.daily_trackers
        tracker = result.daily_trackers[0]
        # At least one recipe has micronutrients; daily total should reflect it
        assert tracker.micronutrients_consumed.get("iron_mg", 0) > 0
        assert tracker.micronutrients_consumed.get("vitamin_c_mg", 0) > 0


# --- Invariant validation ---


class TestPlannerStateInvariants:
    """_validate_planner_state and PlannerStateError."""

    def test_validate_planner_state_raises_when_days_completed_mismatch(self):
        from src.planning.phase0_models import DailyTracker, WeeklyTracker
        from src.data_layer.models import NutritionProfile

        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(schedule)
        wt = WeeklyTracker(
            weekly_totals=NutritionProfile(0.0, 0.0, 0.0, 0.0),
            days_completed=1,
            days_remaining=1,
            carryover_needs={},
        )
        daily_trackers = {0: _make_full_tracker(2)}
        completed_days = set()
        with pytest.raises(PlannerStateError, match="len\\(completed_days\\)"):
            _validate_planner_state(daily_trackers, wt, completed_days, 2, schedule)

    def test_validate_planner_state_raises_when_weekly_macro_large_negative(self):
        """Large negative weekly macro (e.g. -50) must still raise; only tiny drift is tolerated."""
        from src.planning.phase0_models import WeeklyTracker
        from src.data_layer.models import NutritionProfile

        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(schedule)
        wt = WeeklyTracker(
            weekly_totals=NutritionProfile(2000.0, 100.0, 65.0, -50.0),  # real negative
            days_completed=1,
            days_remaining=0,
            carryover_needs={},
        )
        daily_trackers = {0: _make_full_tracker(2)}
        completed_days = {0}
        with pytest.raises(PlannerStateError, match="negative weekly macro"):
            _validate_planner_state(daily_trackers, wt, completed_days, 1, schedule)


def _make_full_tracker(slots_total: int):
    from src.planning.phase0_models import DailyTracker
    return DailyTracker(
        calories_consumed=2000.0,
        protein_consumed=100.0,
        fat_consumed=65.0,
        carbs_consumed=250.0,
        slots_assigned=slots_total,
        slots_total=slots_total,
    )


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
        result = run_meal_plan_search(profile, pool, 2, None, stats=stats)
        assert result.success is True
        assert stats.total_attempts == 4
        assert stats.total_runtime() >= 0
        assert isinstance(stats.branching_factors, dict)
        assert stats.time_per_attempt() >= 0

    def test_d7_timing_measurable(self):
        schedule = _make_schedule(ndays=7, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [_make_recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(14)]
        stats = SearchStats(enabled=True)
        result = run_meal_plan_search(profile, pool, 7, None, stats=stats)
        assert result.success is True
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
        result = run_meal_plan_search(profile, pool, 1, None, stats=stats)
        assert result.success is True
        assert stats.total_attempts == 2
        assert stats.total_runtime() >= 0
