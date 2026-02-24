"""Theoretical Perfect Week suite: clean-room correctness under ideal feasibility.

Validates the planner when inputs are built so that:
- Search ambiguity is eliminated or stressed in controlled ways
- Accounting (daily/weekly, carryover) can be asserted exactly
- Determinism and tie-breaking are exercised

Variants:
  A — Identical meals everywhere (baseline sanity)
  B — Multiple perfect daily combinations (determinism stress)
  C — Cross-day micronutrient assembly (weekly coupling, carryover)
  D — Large pool, sparse perfect cover (search profile metrics)

Reference: MEALPLAN_SPECIFICATION_v1.md; MEAL_PLANNER_TESTING_GUIDE.md.
"""

from __future__ import annotations

import pytest

from src.data_layer.models import MicronutrientProfile, NutritionProfile
from src.planning.phase0_models import (
    Assignment,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    micronutrient_profile_to_dict,
)
from src.planning.phase10_reporting import MealPlanResult
from src.planning.phase7_search import SearchStats, run_meal_plan_search


# --- Helpers ---


def _slot(busyness: int = 2) -> MealSlot:
    return MealSlot("12:00", busyness, "lunch")


def _schedule(ndays: int, slots_per_day: int = 2) -> list:
    return [[_slot() for _ in range(slots_per_day)] for _ in range(ndays)]


def _recipe(
    rid: str,
    calories: float = 1000.0,
    protein: float = 50.0,
    fat: float = 32.0,
    carbs: float = 125.0,
    micronutrients: MicronutrientProfile | None = None,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=[],
        cooking_time_minutes=10,
        nutrition=NutritionProfile(
            calories, protein, fat, carbs,
            micronutrients=micronutrients or MicronutrientProfile(),
        ),
        primary_carb_contribution=None,
    )


def _profile(
    schedule: list,
    daily_calories: int = 2000,
    daily_protein_g: float = 100.0,
    daily_fat_g: tuple[float, float] = (50.0, 80.0),
    daily_carbs_g: float = 250.0,
    micronutrient_targets: dict | None = None,
) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=daily_calories,
        daily_protein_g=daily_protein_g,
        daily_fat_g=daily_fat_g,
        daily_carbs_g=daily_carbs_g,
        schedule=schedule,
        pinned_assignments={},
        excluded_ingredients=[],
        micronutrient_targets=micronutrient_targets or {},
    )


def _weekly_micro_dict(result: MealPlanResult) -> dict[str, float]:
    """Extract weekly micronutrient totals from a successful result."""
    if not result.weekly_tracker or not result.weekly_tracker.weekly_totals:
        return {}
    return micronutrient_profile_to_dict(
        getattr(result.weekly_tracker.weekly_totals, "micronutrients", None)
    )


# --- Variant A: Identical meals everywhere ---


class TestVariantAIdenticalMeals:
    """
    Every recipe has identical nutrition; each meal perfectly fits slot constraints;
    weekly totals exactly meet requirements.

    Catches: state drift, double counting, nondeterminism from sets,
    unstable tie-breaking, weekly folding bugs.
    """

    def test_succeeds_tc1(self):
        D = 7
        slots_per_day = 2
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule)
        n_slots = D * slots_per_day
        pool = [
            _recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0)
            for i in range(n_slots)
        ]
        result = run_meal_plan_search(profile, pool, D, None)
        assert isinstance(result, MealPlanResult)
        assert result.success is True
        assert result.termination_code == "TC-1"
        assert result.plan is not None
        assert len(result.plan) == n_slots
        assert result.weekly_tracker is not None
        assert result.weekly_tracker.days_completed == D

    def test_low_attempts_no_unnecessary_backtracking(self):
        D = 3
        slots_per_day = 2
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule)
        n_slots = D * slots_per_day
        pool = [_recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(n_slots)]
        stats = SearchStats(enabled=True)
        result = run_meal_plan_search(profile, pool, D, None, stats=stats)
        assert result.success is True
        # With identical recipes, search should assign without backtracking
        assert stats.total_attempts <= n_slots + 2
        assert result.stats is None or result.stats.get("backtracks", 0) <= 2

    def test_same_plan_across_repeated_runs(self):
        D = 2
        slots_per_day = 2
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule)
        pool = [
            _recipe("r1", 1000.0, 50.0, 32.0, 125.0),
            _recipe("r2", 1000.0, 50.0, 32.0, 125.0),
            _recipe("r3", 1000.0, 50.0, 32.0, 125.0),
            _recipe("r4", 1000.0, 50.0, 32.0, 125.0),
        ]
        result1 = run_meal_plan_search(profile, pool, D, None)
        result2 = run_meal_plan_search(profile, pool, D, None)
        assert result1.success and result2.success
        assert result1.plan is not None and result2.plan is not None
        plans = [tuple((a.day_index, a.slot_index, a.recipe_id) for a in result1.plan),
                 tuple((a.day_index, a.slot_index, a.recipe_id) for a in result2.plan)]
        assert plans[0] == plans[1], "Deterministic: same plan across runs"

    def test_weekly_micronutrients_equal_target_when_tracked(self):
        D = 2
        slots_per_day = 2
        daily_iron_rdi = 10.0
        # Per-slot iron so that 2 slots/day = daily RDI
        iron_per_slot = daily_iron_rdi / 2  # 5.0
        micro = MicronutrientProfile(iron_mg=iron_per_slot)
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule, micronutrient_targets={"iron_mg": daily_iron_rdi})
        n_slots = D * slots_per_day
        pool = [
            _recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0, micronutrients=micro)
            for i in range(n_slots)
        ]
        result = run_meal_plan_search(profile, pool, D, None)
        assert result.success is True
        weekly = _weekly_micro_dict(result)
        required = daily_iron_rdi * D
        assert weekly.get("iron_mg", 0.0) >= required - 0.01

    def test_no_sodium_advisory_unless_triggered(self):
        D = 2
        schedule = _schedule(D, 2)
        # Low sodium so we do NOT trigger 200% advisory
        low_sodium = MicronutrientProfile(sodium_mg=200.0)
        profile = _profile(schedule, micronutrient_targets={"sodium_mg": 500.0})
        pool = [
            _recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0, micronutrients=low_sodium)
            for i in range(4)
        ]
        result = run_meal_plan_search(profile, pool, D, None)
        assert result.success is True
        # 4 slots * 200 = 800 mg; 2 * 500 * 2 = 2000 recommended max; 800 < 2000 → no advisory
        assert result.warning is None or result.warning.get("type") != "sodium_advisory"


# --- Variant B: Multiple perfect daily combinations ---


class TestVariantBMultiplePerfectCombinations:
    """
    Several recipes per slot, multiple valid combinations per day,
    all nutritionally perfect. Stress determinism and Phase 5 tie-break.

    Catches: unstable sorting, set iteration leaks, tie-break mistakes, hidden randomness.
    """

    def test_succeeds_tc1(self):
        D = 2
        slots_per_day = 2
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule)
        # 2 options per "role": A/B for slot0, C/D for slot1, etc. All same nutrition.
        base = (1000.0, 50.0, 32.0, 125.0)
        pool = [
            _recipe("rA", *base),
            _recipe("rB", *base),
            _recipe("rC", *base),
            _recipe("rD", *base),
        ]
        result = run_meal_plan_search(profile, pool, D, None)
        assert result.success is True
        assert result.termination_code == "TC-1"
        assert result.plan is not None
        assert len(result.plan) == D * slots_per_day

    def test_identical_output_and_attempts_across_n_runs(self):
        D = 2
        slots_per_day = 2
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule)
        base = (1000.0, 50.0, 32.0, 125.0)
        pool = [
            _recipe("rA", *base),
            _recipe("rB", *base),
            _recipe("rC", *base),
            _recipe("rD", *base),
        ]
        plans = []
        attempt_counts = []
        for _ in range(20):
            stats = SearchStats(enabled=True)
            result = run_meal_plan_search(profile, pool, D, None, stats=stats)
            assert result.success is True
            assert result.plan is not None
            plans.append(tuple((a.day_index, a.slot_index, a.recipe_id) for a in result.plan))
            attempt_counts.append(stats.total_attempts)
        assert len(set(plans)) == 1, "Identical output each run"
        assert len(set(attempt_counts)) == 1, "Identical attempt count each run"


# --- Variant C: Cross-day micronutrient assembly ---


class TestVariantCCrossDayMicronutrientAssembly:
    """
    Recipes supply ~10% of required micronutrients; no single day can reach
    full weekly RDI; only multi-day accumulation satisfies weekly validation.

    Catches: carryover math bugs, partial-day subtraction errors,
    premature deficiency detection, weekly tracker corruption, backtrack restoration.
    """

    def _iron_pool(self, D: int, slots_per_day: int, daily_rdi: float) -> list[PlanningRecipe]:
        """Each recipe contributes 1/slots_per_day of daily RDI so one day = daily_rdi."""
        iron_per_slot = daily_rdi / slots_per_day
        micro = MicronutrientProfile(iron_mg=iron_per_slot)
        n_slots = D * slots_per_day
        return [
            _recipe(f"r{i}", 1000.0, 50.0, 32.0, 125.0, micronutrients=micro)
            for i in range(n_slots)
        ]

    def test_d3_weekly_totals_meet_prorated_rdi(self):
        D = 3
        slots_per_day = 2
        daily_iron = 10.0
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule, micronutrient_targets={"iron_mg": daily_iron})
        pool = self._iron_pool(D, slots_per_day, daily_iron)
        result = run_meal_plan_search(profile, pool, D, None)
        assert result.success is True
        weekly = _weekly_micro_dict(result)
        assert weekly.get("iron_mg", 0.0) >= daily_iron * D - 0.01
        assert result.weekly_tracker is not None
        assert result.weekly_tracker.days_completed == D

    def test_d5_success_no_false_fm4(self):
        D = 5
        slots_per_day = 2
        daily_iron = 10.0
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule, micronutrient_targets={"iron_mg": daily_iron})
        pool = self._iron_pool(D, slots_per_day, daily_iron)
        result = run_meal_plan_search(profile, pool, D, None)
        assert result.success is True
        assert result.termination_code == "TC-1"
        assert result.weekly_tracker is not None
        assert result.weekly_tracker.days_completed == D

    def test_d7_completed_days_correct_no_negative_weekly(self):
        D = 7
        slots_per_day = 2
        daily_iron = 10.0
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule, micronutrient_targets={"iron_mg": daily_iron})
        pool = self._iron_pool(D, slots_per_day, daily_iron)
        result = run_meal_plan_search(profile, pool, D, None)
        assert result.success is True
        wt = result.weekly_tracker
        assert wt is not None
        assert wt.days_completed == D
        weekly = _weekly_micro_dict(result)
        assert weekly.get("iron_mg", 0.0) >= 0.0
        assert weekly.get("iron_mg", 0.0) >= daily_iron * D - 0.01

    def test_backtracking_bounded(self):
        D = 7
        slots_per_day = 2
        daily_iron = 10.0
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule, micronutrient_targets={"iron_mg": daily_iron})
        pool = self._iron_pool(D, slots_per_day, daily_iron)
        stats = SearchStats(enabled=True)
        result = run_meal_plan_search(profile, pool, D, None, stats=stats)
        assert result.success is True
        # Should not explode in backtracks for this feasible case
        assert stats.total_attempts < 50
        assert stats.max_depth < 20


# --- Variant D: Large pool, sparse perfect cover ---


class TestVariantDLargePoolSparsePerfectCover:
    """
    Large recipe pool; only specific combinations yield a perfect week;
    many distractor recipes. Combinatorial correctness and search profile.
    """

    def test_still_finds_valid_plan_d7(self):
        D = 7
        slots_per_day = 2
        n_slots = D * slots_per_day
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule)
        # 14 "perfect" recipes (exactly enough) + many distractors (same nutrition so still valid)
        perfect = [_recipe(f"p{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(n_slots)]
        distractors = [_recipe(f"d{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(30)]
        pool = perfect + distractors
        result = run_meal_plan_search(profile, pool, D, None)
        assert result.success is True
        assert result.plan is not None
        assert len(result.plan) == n_slots

    def test_deterministic_with_large_pool(self):
        D = 3
        slots_per_day = 2
        n_slots = D * slots_per_day
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule)
        perfect = [_recipe(f"p{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(n_slots)]
        distractors = [_recipe(f"d{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(20)]
        pool = perfect + distractors
        result1 = run_meal_plan_search(profile, pool, D, None)
        result2 = run_meal_plan_search(profile, pool, D, None)
        assert result1.success and result2.success
        assert result1.plan is not None and result2.plan is not None
        t1 = tuple((a.day_index, a.slot_index, a.recipe_id) for a in result1.plan)
        t2 = tuple((a.day_index, a.slot_index, a.recipe_id) for a in result2.plan)
        assert t1 == t2

    def test_metrics_recorded_attempts_backtracks_runtime(self):
        D = 7
        slots_per_day = 2
        n_slots = D * slots_per_day
        schedule = _schedule(D, slots_per_day)
        profile = _profile(schedule)
        perfect = [_recipe(f"p{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(n_slots)]
        distractors = [_recipe(f"d{i}", 1000.0, 50.0, 32.0, 125.0) for i in range(30)]
        pool = perfect + distractors
        stats = SearchStats(enabled=True)
        result = run_meal_plan_search(profile, pool, D, None, stats=stats)
        assert result.success is True
        assert stats.total_attempts >= n_slots
        assert stats.total_runtime() >= 0.0
        assert isinstance(stats.branching_factors, dict)
        # Optional: assert reasonable attempt growth (no explosion)
        assert stats.total_attempts < 500
