"""Phase 7 tests: Backtracking and search orchestration. Spec Sections 6.1–6.6, 9, 10, 11."""

from __future__ import annotations

import pytest

from src.data_layer.models import Ingredient, MicronutrientProfile, NutritionProfile, UpperLimits
from src.planning.phase0_models import Assignment, DailyTracker, MealSlot, PlanningRecipe, PlanningUserProfile, WeeklyTracker
from src.planning.phase10_reporting import MealPlanResult, PIN_VIOLATION_DOWNSTREAM, fix_hint_for_code
from src.planning.phase7_search import (
    DEFAULT_ATTEMPT_LIMIT,
    PlannerStateError,
    SearchStats,
    _CandidateCacheEntry,
    _decision_order,
    _unwind_to,
    _update_weekly_after_day,
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

    def test_fm3_direct_pin_conflict_reports_zero_based_day(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(
            schedule,
            pinned_assignments={(0, 0): "r_bad"},
            excluded_ingredients=["peanut"],
        )
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe(
                "r_bad",
                1000.0,
                50.0,
                32.0,
                125.0,
                ingredients=[Ingredient("peanut", 10.0, "g", False, "g", 10.0)],
            ),
        ]
        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.failure_mode == "FM-3"
        conflicts = result.report["pinned_conflicts"]
        assert conflicts[0]["day"] == 0 and conflicts[0]["slot_index"] == 0
        failure = result.report["failures"][0]
        assert failure["day_index"] == 0
        assert failure["date"] == "day-1"
        assert failure["slot_id"] == "day-1-slot-0"

    def test_fm1_insufficient_pool_empty_candidates(self):
        """One recipe for two slots: day check finds no valid combo → FM-2 (C2a).

        Slot-level HC-1/HC-3 still pass (step 1), so this is not static FM-1.
        """
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(schedule)
        pool = [_make_recipe("r1", 1000.0, 50.0, 32.0, 125.0)]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert isinstance(result, MealPlanResult)
        assert result.failure_mode == "FM-2"
        assert result.report.get("failed_days")
        assert result.report["failed_days"][0]["day"] == 0
        failures = result.report.get("failures", [])
        assert failures and failures[0]["code"] == "FM-MACRO-INFEASIBLE"
        assert result.stats is not None and result.stats.get("attempts", 0) >= 0

    def test_fm1_static_hc3_empty_slot(self):
        """True FM-1: no recipe passes HC-3 for a slot (attribution step 1)."""
        schedule = [[_make_slot(busyness=1), _make_slot(busyness=2)]]
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0, cooking_min=30),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0, cooking_min=30),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert result.failure_mode == "FM-1"
        unfillable = result.report.get("unfillable_slots", [])
        assert len(unfillable) >= 1
        assert unfillable[0]["day"] == 0
        assert unfillable[0]["slot_index"] == 0
        failures = result.report.get("failures", [])
        assert failures[0]["code"] == "FM-1"
        assert "closest_plan" in result.report or "best_plan" in result.report or result.report.get("unfillable_slots")

    def test_fm_tag_empty_emits_stable_failure_shape(self):
        schedule = [[_make_slot(required_tag_slugs=["high-protein"]), _make_slot()]]
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0, canonical_tag_slugs={"quick"}),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0, canonical_tag_slugs={"comfort"}),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert result.failure_mode == "FM-TAG-EMPTY"
        failures = result.report.get("failures", [])
        assert len(failures) == 1
        assert failures[0] == {
            "code": "FM-TAG-EMPTY",
            "message": "No recipes satisfy required tag `high-protein` for this slot.",
            "day_index": 0,
            "slot_index": 0,
            "slot_id": "day-1-slot-0",
            "date": "",
            "details": {"missing_tag": "high-protein", "recipe_count": 0},
            "fix_hint": "No recipes match tag `high-protein`. Add one or relax constraints.",
        }

    def test_fm_tag_empty_later_slot_before_fc5(self):
        """C2b: tagged slot 2 diagnosed statically before FC-5 at earlier slots."""
        schedule = [
            [
                _make_slot(),
                _make_slot(),
                _make_slot(required_tag_slugs=["dairy-free"]),
            ]
        ]
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 700.0, 35.0, 22.0, 85.0, canonical_tag_slugs={"quick"}),
            _make_recipe("r2", 700.0, 35.0, 22.0, 85.0, canonical_tag_slugs={"comfort"}),
            _make_recipe("r3", 700.0, 35.0, 22.0, 85.0, canonical_tag_slugs={"high-protein"}),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert result.failure_mode == "FM-TAG-EMPTY"
        assert result.stats is not None and result.stats.get("attempts") == 0
        slot_report = result.report["tag_empty_slots"][0]
        assert slot_report["day_index"] == 0
        assert slot_report["slot_index"] == 2
        assert slot_report["required_tag_slugs"] == ["dairy-free"]
        assert slot_report["candidate_count_before"] == 3
        assert slot_report["candidate_count_after"] == 0
        assert "dairy-free" in result.report["failures"][0]["fix_hint"]

    def test_fm_tag_empty_day1_slot1(self):
        """C2b: tagged slot on day 1 (second day) is reported at (1, 1)."""
        schedule = [
            [_make_slot(), _make_slot()],
            [_make_slot(), _make_slot(required_tag_slugs=["portable"])],
        ]
        profile = _make_profile(schedule)
        pool = [
            _make_recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0, canonical_tag_slugs={"quick"})
            for i in range(4)
        ]
        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.success is False
        assert result.failure_mode == "FM-TAG-EMPTY"
        slot_report = result.report["tag_empty_slots"][0]
        assert slot_report["day_index"] == 1
        assert slot_report["slot_index"] == 1
        assert result.report["failures"][0]["details"]["missing_tag"] == "portable"
        assert result.stats is not None and result.stats.get("attempts") == 0

    def test_static_fm1_hc3_on_non_first_slot(self):
        """Static FM-1 when every recipe fails HC-3 on a later busy slot."""
        schedule = [
            [
                _make_slot(busyness=4),
                _make_slot(busyness=1),  # 5 min cap
            ]
        ]
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0, cooking_min=20),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0, cooking_min=30),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert result.failure_mode == "FM-1"
        assert result.stats is not None and result.stats.get("attempts") == 0
        unfillable = result.report["unfillable_slots"][0]
        assert unfillable["day"] == 0
        assert unfillable["slot_index"] == 1
        assert unfillable["eligible_recipe_count"] == 0
        assert any("HC-3" in c for c in unfillable["blocking_constraints"])

    def test_static_fm1_before_tag_empty(self):
        """Decision-order: an earlier FM-1 slot wins over a later tag-empty slot."""
        schedule = [
            [
                _make_slot(busyness=1),  # all recipes too slow → FM-1
                _make_slot(required_tag_slugs=["portable"]),
            ]
        ]
        profile = _make_profile(schedule)
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0, cooking_min=20, canonical_tag_slugs={"quick"}),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0, cooking_min=30, canonical_tag_slugs={"comfort"}),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert result.failure_mode == "FM-1"
        unfillable = result.report["unfillable_slots"][0]
        assert unfillable["slot_index"] == 0

    def test_pinned_tagged_slot_skipped_by_static_precheck(self):
        """Pinned slots are skipped; an empty free tagged slot still fires."""
        schedule = [
            [
                _make_slot(required_tag_slugs=["portable"]),
                _make_slot(required_tag_slugs=["dairy-free"]),
            ]
        ]
        profile = _make_profile(
            schedule,
            pinned_assignments={(1, 0): "r-pin"},
        )
        pool = [
            _make_recipe("r-pin", 1000.0, 50.0, 32.0, 125.0, canonical_tag_slugs={"quick"}),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0, canonical_tag_slugs={"quick"}),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert result.failure_mode == "FM-TAG-EMPTY"
        slot_report = result.report["tag_empty_slots"][0]
        assert slot_report["slot_index"] == 1
        assert slot_report["required_tag_slugs"] == ["dairy-free"]

    def test_static_slot_check_before_fully_pinned_fm3(self):
        """Slot check precedes fully-pinned-day FM-3 when both conditions hold."""
        schedule = [
            [
                _make_slot(required_tag_slugs=["portable"]),
                _make_slot(),
            ],
            [
                _make_slot(),
                _make_slot(),
            ],
        ]
        # Day 1 fully pinned with macros that miss protein → would be FM-3;
        # day 0 slot 0 is tag-empty → static check must win.
        profile = _make_profile(
            schedule,
            daily_calories=2000,
            daily_protein_g=200.0,
            pinned_assignments={(2, 0): "r1", (2, 1): "r2"},
        )
        pool = [
            _make_recipe("r1", 1000.0, 30.0, 32.0, 125.0, canonical_tag_slugs={"quick"}),
            _make_recipe("r2", 1000.0, 30.0, 32.0, 125.0, canonical_tag_slugs={"comfort"}),
            _make_recipe("r3", 1000.0, 30.0, 32.0, 125.0, canonical_tag_slugs={"comfort"}),
            _make_recipe("r4", 1000.0, 30.0, 32.0, 125.0, canonical_tag_slugs={"comfort"}),
        ]
        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.success is False
        assert result.failure_mode == "FM-TAG-EMPTY"
        assert result.report["tag_empty_slots"][0]["slot_index"] == 0
        assert result.stats is not None and result.stats.get("attempts") == 0

    def test_fm3_fully_pinned_day_misses_macros(self):
        """Fully pinned day that breaks daily macros fails pre-search with FM-3 (C3)."""
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(
            schedule,
            daily_calories=2000,
            daily_protein_g=100.0,
            pinned_assignments={(1, 0): "r1", (1, 1): "r2"},
        )
        pool = [
            _make_recipe("r1", 1000.0, 30.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 30.0, 32.0, 125.0),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert isinstance(result, MealPlanResult)
        assert result.failure_mode == "FM-3"
        assert result.termination_code == "TC-3"
        assert result.stats is not None and result.stats.get("attempts") == 0
        conflicts = result.report.get("pinned_conflicts", [])
        assert len(conflicts) == 1
        assert conflicts[0]["violation_type"] == PIN_VIOLATION_DOWNSTREAM
        assert conflicts[0]["constraint"] == "protein"
        assert len(conflicts[0]["pinned_slots"]) == 2
        failures = result.report.get("failures", [])
        assert len(failures) == 1
        assert all(f["code"] == "FM-3" for f in failures)
        assert all(f["details"].get("constraint") == "protein" for f in failures)

    def test_fm2_daily_infeasible_exhaustion(self):
        """Free-slot macro infeasibility is attributed as FM-2 (C2a day check)."""
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(
            schedule,
            daily_calories=2000,
            daily_protein_g=200.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
        )
        pool = [
            _make_recipe("r1", 1000.0, 30.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 30.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 30.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 30.0, 32.0, 125.0),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is False
        assert isinstance(result, MealPlanResult)
        assert result.failure_mode == "FM-2"
        assert result.report
        assert result.stats is not None and "attempts" in result.stats
        failures = result.report.get("failures", [])
        assert len(failures) >= 1
        assert failures[0]["code"] == "FM-MACRO-INFEASIBLE"
        assert failures[0]["fix_hint"] == fix_hint_for_code("FM-MACRO-INFEASIBLE")
        assert result.report.get("diagnosis", {}).get("code") == "FM-2"

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
        fm5 = result.report["failures"][0]
        assert fm5["code"] == "FM-5"
        assert fm5["message"] == "Planner stopped after reaching attempt limits."
        assert fm5["details"]["attempts"] == 1
        assert fm5["fix_hint"] == fix_hint_for_code("FM-5")
        assert "day_index" not in fm5 and "slot_index" not in fm5

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
        assert result.failure_mode == "FM-4"
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
        assert result.failure_mode == "FM-2"
        assert isinstance(result.failure_mode, str)
        assert "failed_days" in result.report
        assert "closest_plan" in result.report
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


# --- C3: fully pinned day validation ---


class TestFullyPinnedDayValidation:
    """Cluster C3: days with no free slots must complete / fail like free-slot days."""

    def test_mb099_fully_pinned_day_that_fits_succeeds(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(
            schedule,
            pinned_assignments={(1, 0): "r1", (1, 1): "r2"},
        )
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is True, getattr(result, "report", result)
        assert result.termination_code == "TC-4"
        assert result.plan is not None
        assert {a.recipe_id for a in result.plan} == {"r1", "r2"}
        assert result.weekly_tracker is not None
        assert result.weekly_tracker.days_completed == 1
        _assert_weekly_equals_sum_daily(result)

    def test_p2_fully_pinned_day0_misses_macros_returns_fm3(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(
            schedule,
            daily_calories=2000,
            daily_protein_g=100.0,
            pinned_assignments={(1, 0): "r_pin1", (1, 1): "r_pin2"},
        )
        pool = [
            _make_recipe("r_pin1", 700.0, 50.0, 32.0, 125.0),
            _make_recipe("r_pin2", 700.0, 50.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.success is False
        assert result.failure_mode == "FM-3"
        assert result.termination_code == "TC-3"
        assert result.stats is not None and result.stats.get("attempts") == 0
        # The failure reason lives in the report, not in a sodium advisory.
        assert result.warning is None
        conflicts = result.report.get("pinned_conflicts", [])
        assert len(conflicts) == 1
        assert conflicts[0]["violation_type"] == PIN_VIOLATION_DOWNSTREAM
        assert conflicts[0]["constraint"] == "calories"
        assert conflicts[0]["day"] == 0  # pin keys are 1-based; the report is 0-based
        assert {p["slot_index"] for p in conflicts[0]["pinned_slots"]} == {0, 1}
        failures = result.report.get("failures", [])
        assert len(failures) == 1
        assert all(f["code"] == "FM-3" for f in failures)

    def test_p3_weekly_fiber_includes_fully_pinned_day0_success(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        fiber_a = MicronutrientProfile(fiber_g=8.0)
        fiber_b = MicronutrientProfile(fiber_g=7.5)
        fiber_c = MicronutrientProfile(fiber_g=8.0)
        fiber_d = MicronutrientProfile(fiber_g=7.5)
        profile = _make_profile(
            schedule,
            pinned_assignments={(1, 0): "r_pin1", (1, 1): "r_pin2"},
            micronutrient_targets={"fiber_g": 10.0},
        )
        pool = [
            _make_recipe("r_pin1", 1000.0, 50.0, 32.0, 125.0, micronutrients=fiber_a),
            _make_recipe("r_pin2", 1000.0, 50.0, 32.0, 125.0, micronutrients=fiber_b),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0, micronutrients=fiber_c),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0, micronutrients=fiber_d),
        ]
        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.success is True, getattr(result, "report", result)
        assert result.weekly_tracker is not None
        assert result.weekly_tracker.days_completed == 2
        micro = result.weekly_tracker.weekly_totals.micronutrients
        assert micro is not None
        assert abs(micro.fiber_g - 31.0) < 1e-6
        _assert_weekly_equals_sum_daily(result)

    def test_p3_weekly_fiber_includes_fully_pinned_day0_on_fm4(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        fiber_pin = MicronutrientProfile(fiber_g=5.0)
        fiber_free = MicronutrientProfile(fiber_g=5.0)
        # Macro-infeasible high-fiber recipe: loose top-M used to let structural pass;
        # tight enumeration excludes it, so FM-4 fires pre-search (C4).
        fiber_rich = MicronutrientProfile(fiber_g=50.0)
        profile = _make_profile(
            schedule,
            pinned_assignments={(1, 0): "r_pin1", (1, 1): "r_pin2"},
            micronutrient_targets={"fiber_g": 15.0},
        )
        pool = [
            _make_recipe("r_pin1", 1000.0, 50.0, 32.0, 125.0, micronutrients=fiber_pin),
            _make_recipe("r_pin2", 1000.0, 50.0, 32.0, 125.0, micronutrients=fiber_pin),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0, micronutrients=fiber_free),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0, micronutrients=fiber_free),
            _make_recipe("r_rich", 3000.0, 50.0, 32.0, 125.0, micronutrients=fiber_rich),
        ]
        stats = SearchStats(enabled=True)
        result = run_meal_plan_search(profile, pool, 2, None, stats=stats)
        assert result.success is False
        assert result.failure_mode == "FM-4"
        assert stats.total_attempts == 0
        deficient = result.report.get("deficient_nutrients", [])
        fiber_entry = next(e for e in deficient if e["nutrient"] == "fiber_g")
        # Pre-search: nothing assigned yet; classification is structural vs tight day max.
        assert fiber_entry["achieved"] == 0.0
        assert fiber_entry["required"] == pytest.approx(30.0)
        assert fiber_entry["classification"] == "structural"
    def test_last_day_fully_pinned_succeeds(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(
            schedule,
            pinned_assignments={(2, 0): "r_pin1", (2, 1): "r_pin2"},
        )
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r_pin1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r_pin2", 1000.0, 50.0, 32.0, 125.0),
        ]
        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.success is True, getattr(result, "report", result)
        assert result.termination_code == "TC-1"
        assert result.weekly_tracker is not None
        assert result.weekly_tracker.days_completed == 2
        _assert_weekly_equals_sum_daily(result)

    def test_middle_day_fully_pinned_with_backtrack_keeps_weekly(self):
        """Day 1 fully pinned; search may backtrack past it. Weekly totals stay consistent.

        Direct `_unwind_to` coverage for uncompleting a later fully pinned day lives in
        `test_unwind_uncompletes_later_fully_pinned_day`. Scoring prefers high-iron
        recipes when iron is tracked, so this instance may succeed without backtracks.
        """
        schedule = _make_schedule(ndays=3, slots_per_day=2)
        high = MicronutrientProfile(iron_mg=12.0)
        mid = MicronutrientProfile(iron_mg=5.0)
        low = MicronutrientProfile(iron_mg=0.0)
        profile = _make_profile(
            schedule,
            pinned_assignments={(2, 0): "r_pin1", (2, 1): "r_pin2"},
            micronutrient_targets={"iron_mg": 10.0},
        )
        pool = [
            _make_recipe("r_low_a", 1000.0, 50.0, 32.0, 125.0, micronutrients=low),
            _make_recipe("r_low_b", 1000.0, 50.0, 32.0, 125.0, micronutrients=low),
            _make_recipe("r_high_a", 1000.0, 50.0, 32.0, 125.0, micronutrients=high),
            _make_recipe("r_high_b", 1000.0, 50.0, 32.0, 125.0, micronutrients=high),
            _make_recipe("r_pin1", 1000.0, 50.0, 32.0, 125.0, micronutrients=mid),
            _make_recipe("r_pin2", 1000.0, 50.0, 32.0, 125.0, micronutrients=mid),
            _make_recipe("r_day2_a", 1000.0, 50.0, 32.0, 125.0, micronutrients=low),
            _make_recipe("r_day2_b", 1000.0, 50.0, 32.0, 125.0, micronutrients=low),
        ]
        stats = SearchStats(enabled=True)
        result = run_meal_plan_search(profile, pool, 3, None, stats=stats)
        assert result.success is True, getattr(result, "report", result)
        assert result.weekly_tracker is not None
        assert result.weekly_tracker.days_completed == 3
        micro = result.weekly_tracker.weekly_totals.micronutrients
        assert micro is not None and micro.iron_mg >= 30.0 - 1e-6
        _assert_weekly_equals_sum_daily(result)
        # Pins remain on day 1 regardless of how many free-slot attempts occurred.
        assert result.plan is not None
        by_slot = {(a.day_index, a.slot_index): a.recipe_id for a in result.plan}
        assert by_slot[(1, 0)] == "r_pin1"
        assert by_slot[(1, 1)] == "r_pin2"

    def test_backtrack_across_fully_pinned_day_end_to_end(self, monkeypatch):
        """Weekly iron forces the search to unwind through a completed, fully pinned day 1.

        The pinned day is uncompleted on the way back and re-completed on the way forward, so
        weekly totals must still equal the sum of daily totals and the pins must survive.

        Tight per-slot floor pruning and day-indexed FC-4 (C4) would reject a low-iron
        day 0 before the pinned day is ever completed. This test forces the loose top-M
        bound, disables per-slot filtering, and prefers low-iron candidates first so
        search still exercises `_uncomplete_day` across a pin day end-to-end.
        """
        from src.planning import phase7_search as p7

        uncompleted_days: list[int] = []
        real_uncomplete = p7._uncomplete_day

        def spy(daily_trackers, weekly_tracker, day_index, *args, **kwargs):
            uncompleted_days.append(day_index)
            return real_uncomplete(daily_trackers, weekly_tracker, day_index, *args, **kwargs)

        monkeypatch.setattr(p7, "_uncomplete_day", spy)
        monkeypatch.setattr(p7, "candidate_passes_micro_floor", lambda *a, **k: True)

        def force_loose_bounds(profile, recipe_pool, schedule, D, resolved_ul, **kwargs):
            from src.planning.phase3_feasibility import (
                micro_floor_bounds_from_slot_mda,
                precompute_max_daily_achievable,
            )

            names = list(profile.micronutrient_targets.keys())
            slot_counts = {len(schedule[d]) for d in range(D)}
            mda = precompute_max_daily_achievable(recipe_pool, names, slot_counts)
            return micro_floor_bounds_from_slot_mda(mda, schedule, D, names)

        monkeypatch.setattr(p7, "precompute_micro_floor_bounds", force_loose_bounds)

        real_ordering = p7.ordering_key

        def low_iron_first(candidate, state, profile, day_index, **kwargs):
            recipe_view, _score = candidate
            iron = 0.0
            micro = getattr(recipe_view.nutrition, "micronutrients", None)
            if micro is not None:
                iron = float(getattr(micro, "iron_mg", 0.0) or 0.0)
            base = real_ordering(candidate, state, profile, day_index, **kwargs)
            return (iron, base)

        monkeypatch.setattr(p7, "ordering_key", low_iron_first)

        def iron(mg: float) -> MicronutrientProfile:
            return MicronutrientProfile(iron_mg=mg)

        schedule = _make_schedule(ndays=3, slots_per_day=2)
        profile = _make_profile(
            schedule,
            pinned_assignments={(2, 0): "r_pin1", (2, 1): "r_pin2"},
            micronutrient_targets={"iron_mg": 14.0},
        )
        pool = [
            _make_recipe("r_pin1", 1000.0, 50.0, 32.0, 125.0, micronutrients=iron(4.0)),
            _make_recipe("r_pin2", 1000.0, 50.0, 32.0, 125.0, micronutrients=iron(4.0)),
            _make_recipe("f0", 1000.0, 50.0, 32.0, 125.0, micronutrients=iron(0.0)),
            _make_recipe("f1", 800.0, 50.0, 32.0, 125.0, micronutrients=iron(12.0)),
            _make_recipe("f2", 1200.0, 50.0, 32.0, 125.0, micronutrients=iron(3.0)),
            _make_recipe("f3", 1200.0, 50.0, 32.0, 125.0, micronutrients=iron(6.0)),
            _make_recipe("f4", 1000.0, 50.0, 32.0, 125.0, micronutrients=iron(6.0)),
        ]
        result = run_meal_plan_search(profile, pool, 3, None)
        assert result.success is True, getattr(result, "report", result)
        assert 1 in uncompleted_days, "search never unwound the fully pinned day"
        assert result.weekly_tracker is not None
        assert result.weekly_tracker.days_completed == 3
        micro = result.weekly_tracker.weekly_totals.micronutrients
        assert micro is not None and micro.iron_mg >= 42.0 - 1e-6
        _assert_weekly_equals_sum_daily(result)
        assert result.plan is not None
        by_slot = {(a.day_index, a.slot_index): a.recipe_id for a in result.plan}
        assert by_slot[(1, 0)] == "r_pin1"
        assert by_slot[(1, 1)] == "r_pin2"

    def test_unwind_uncompletes_later_fully_pinned_day(self):
        schedule = _make_schedule(ndays=2, slots_per_day=2)
        profile = _make_profile(
            schedule,
            pinned_assignments={(2, 0): "r_pin1", (2, 1): "r_pin2"},
        )
        recipe_by_id = {
            "r1": _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            "r2": _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            "r_pin1": _make_recipe("r_pin1", 1000.0, 50.0, 32.0, 125.0),
            "r_pin2": _make_recipe("r_pin2", 1000.0, 50.0, 32.0, 125.0),
        }
        order = _decision_order(schedule, 2)
        daily_trackers = {
            0: DailyTracker(
                calories_consumed=2000.0,
                protein_consumed=100.0,
                fat_consumed=64.0,
                carbs_consumed=250.0,
                micronutrients_consumed={},
                used_recipe_ids={"r1", "r2"},
                non_workout_recipe_ids={"r1", "r2"},
                slots_assigned=2,
                slots_total=2,
            ),
            1: DailyTracker(
                calories_consumed=2000.0,
                protein_consumed=100.0,
                fat_consumed=64.0,
                carbs_consumed=250.0,
                micronutrients_consumed={},
                used_recipe_ids={"r_pin1", "r_pin2"},
                non_workout_recipe_ids={"r_pin1", "r_pin2"},
                slots_assigned=2,
                slots_total=2,
            ),
        }
        weekly_tracker = WeeklyTracker(
            weekly_totals=NutritionProfile(0.0, 0.0, 0.0, 0.0),
            days_completed=0,
            days_remaining=2,
            carryover_needs={},
        )
        completed_days: set[int] = set()
        _update_weekly_after_day(daily_trackers, weekly_tracker, 0, schedule, profile, 2)
        completed_days.add(0)
        _update_weekly_after_day(daily_trackers, weekly_tracker, 1, schedule, profile, 2)
        completed_days.add(1)
        assert weekly_tracker.days_completed == 2
        assert abs(weekly_tracker.weekly_totals.calories - 4000.0) < 1e-6

        assignments = [
            Assignment(0, 0, "r1", 0),
            Assignment(0, 1, "r2", 0),
            Assignment(1, 0, "r_pin1", 0),
            Assignment(1, 1, "r_pin2", 0),
        ]
        cache = {
            (0, 0): _CandidateCacheEntry(
                ordered=[("r1", 0), ("r_alt", 0)],
                variant_nutritions={},
                pointer=1,
            ),
        }
        # Backtrack to day 0 slot 0; day 1 is fully pinned so removals leave it completed
        # unless _unwind_to uncompletes it.
        _i, daily_trackers, weekly_tracker, assignments, _cache = _unwind_to(
            origin_i=3,
            target_i=0,
            order=order,
            daily_trackers=daily_trackers,
            weekly_tracker=weekly_tracker,
            assignments=assignments,
            cache=cache,
            completed_days=completed_days,
            recipe_by_id=recipe_by_id,
            schedule=schedule,
            profile=profile,
        )
        assert 1 not in completed_days
        assert weekly_tracker.days_completed == 0
        assert abs(weekly_tracker.weekly_totals.calories) < 1e-6

    def test_partly_pinned_day_completes_once(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        profile = _make_profile(
            schedule,
            pinned_assignments={(1, 1): "r_pin"},
        )
        pool = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r_pin", 1000.0, 50.0, 32.0, 125.0),
        ]
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.success is True, getattr(result, "report", result)
        assert result.weekly_tracker is not None
        assert result.weekly_tracker.days_completed == 1
        assert abs(result.weekly_tracker.weekly_totals.calories - 2000.0) < 1e-6
        _assert_weekly_equals_sum_daily(result)

    def test_fully_pinned_day_ul_violation_returns_fm3(self):
        schedule = _make_schedule(ndays=1, slots_per_day=2)
        ul = UpperLimits(vitamin_c_mg=100.0)
        profile = _make_profile(
            schedule,
            pinned_assignments={(1, 0): "r1", (1, 1): "r2"},
        )
        pool = [
            _make_recipe(
                "r1",
                1000.0,
                50.0,
                32.0,
                125.0,
                micronutrients=MicronutrientProfile(vitamin_c_mg=60.0),
            ),
            _make_recipe(
                "r2",
                1000.0,
                50.0,
                32.0,
                125.0,
                micronutrients=MicronutrientProfile(vitamin_c_mg=60.0),
            ),
        ]
        result = run_meal_plan_search(profile, pool, 1, ul)
        assert result.success is False
        assert result.failure_mode == "FM-3"
        conflicts = result.report.get("pinned_conflicts", [])
        assert conflicts
        assert all(str(c.get("constraint", "")).startswith("UL:") for c in conflicts)

    def test_fully_pinned_paths_are_deterministic(self):
        schedule_ok = _make_schedule(ndays=1, slots_per_day=2)
        profile_ok = _make_profile(
            schedule_ok,
            pinned_assignments={(1, 0): "r1", (1, 1): "r2"},
        )
        pool_ok = [
            _make_recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r2", 1000.0, 50.0, 32.0, 125.0),
        ]
        r1 = run_meal_plan_search(profile_ok, pool_ok, 1, None)
        r2 = run_meal_plan_search(profile_ok, pool_ok, 1, None)
        assert r1.success is True and r2.success is True
        assert r1.termination_code == r2.termination_code
        assert [(a.day_index, a.slot_index, a.recipe_id) for a in r1.plan] == [
            (a.day_index, a.slot_index, a.recipe_id) for a in r2.plan
        ]

        schedule_bad = _make_schedule(ndays=2, slots_per_day=2)
        profile_bad = _make_profile(
            schedule_bad,
            daily_calories=2000,
            pinned_assignments={(1, 0): "r_pin1", (1, 1): "r_pin2"},
        )
        pool_bad = [
            _make_recipe("r_pin1", 700.0, 50.0, 32.0, 125.0),
            _make_recipe("r_pin2", 700.0, 50.0, 32.0, 125.0),
            _make_recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _make_recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        f1 = run_meal_plan_search(profile_bad, pool_bad, 2, None)
        f2 = run_meal_plan_search(profile_bad, pool_bad, 2, None)
        assert f1.failure_mode == f2.failure_mode == "FM-3"
        assert f1.report.get("pinned_conflicts") == f2.report.get("pinned_conflicts")
