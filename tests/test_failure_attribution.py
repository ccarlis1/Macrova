"""Post-search failure attribution (C2a). Spec §11 steps 2–3."""

from __future__ import annotations

from src.data_layer.models import MicronutrientProfile, NutritionProfile
from src.planning.failure_attribution import (
    diagnose_exhausted_search,
)
from src.planning.phase0_models import MealSlot, PlanningRecipe, PlanningUserProfile
from src.planning.phase6_candidates import check_slot_statically
from src.planning.phase7_search import run_meal_plan_search
from src.planning.failure_attribution import weekly_tracker_from_best_micro
from src.planning.phase10_reporting import (
    HC8_SEQUENCE_FIX_HINT,
    PIN_VIOLATION_DOWNSTREAM,
    build_report_fm4,
    fix_hint_for_code,
)


def _slot(busyness: int = 3) -> MealSlot:
    return MealSlot("12:00", busyness, "lunch")


def _recipe(
    rid: str,
    calories: float = 1000.0,
    protein: float = 50.0,
    fat: float = 32.0,
    carbs: float = 125.0,
    *,
    cooking_min: int = 10,
    fiber_g: float = 0.0,
    tags: set[str] | None = None,
) -> PlanningRecipe:
    micro = MicronutrientProfile(fiber_g=fiber_g) if fiber_g else MicronutrientProfile()
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=[],
        cooking_time_minutes=cooking_min,
        nutrition=NutritionProfile(calories, protein, fat, carbs, micronutrients=micro),
        primary_carb_contribution=None,
        canonical_tag_slugs=set(tags or set()),
    )


def _profile(
    schedule: list,
    *,
    daily_calories: int = 2000,
    daily_protein_g: float = 100.0,
    daily_fat_g: tuple[float, float] = (50.0, 80.0),
    daily_carbs_g: float = 250.0,
    pins: dict | None = None,
    micronutrient_targets: dict | None = None,
    enable_carb_scaling: bool = False,
) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=daily_calories,
        daily_protein_g=daily_protein_g,
        daily_fat_g=daily_fat_g,
        daily_carbs_g=daily_carbs_g,
        schedule=schedule,
        # Pins are (day_1based, slot_index) per convert_profile / phase1.
        pinned_assignments=pins or {},
        micronutrient_targets=micronutrient_targets or {},
        enable_primary_carb_downscaling=enable_carb_scaling,
    )


class TestStaticEligibleIds:
    def test_eligible_recipe_ids_match_count_and_tags(self):
        pool = [
            _recipe("a", tags={"breakfast"}),
            _recipe("b", tags={"lunch"}),
            _recipe("c", cooking_min=60),  # fails HC-3 at busyness 2
        ]
        slot = MealSlot("08:00", 2, "breakfast", required_tag_slugs=["breakfast"])
        profile = _profile([[slot]])
        check = check_slot_statically(pool, 0, slot, profile, None)
        assert check.code is None
        assert check.eligible_count == 2  # a,b pass HC-1/HC-3
        assert check.eligible_recipe_ids == ("a",)  # only tagged


class TestDayCheckFm2:
    def test_intrinsic_macro_conflict(self):
        """1-day 2-slot pool cannot hit protein → FM-2 with closest_plan."""
        schedule = [[_slot(), _slot()]]
        profile = _profile(
            schedule,
            daily_calories=2000,
            daily_protein_g=200.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
        )
        pool = [
            _recipe("r1", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r2", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r3", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r4", 1000.0, 30.0, 32.0, 125.0),
        ]
        attr = diagnose_exhausted_search(profile, pool, schedule, 1, None)
        assert attr.status == "attributed"
        assert attr.code == "FM-2"
        assert attr.day_index == 0
        assert attr.step == "day_check"

        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.failure_mode == "FM-2"
        assert result.termination_code == "TC-2"
        assert result.report.get("failed_days")
        assert result.report["failed_days"][0]["day"] == 0
        assert result.report["failed_days"][0]["constraint_detail"] == "no_valid_combination"
        assert "closest_plan" in result.report
        failures = result.report["failures"]
        assert failures[0]["code"] == "FM-MACRO-INFEASIBLE"
        assert failures[0]["date"] == "day-1"
        assert failures[0]["fix_hint"] == fix_hint_for_code("FM-MACRO-INFEASIBLE")
        assert result.report["diagnosis"]["status"] == "attributed"
        assert result.report["diagnosis"]["code"] == "FM-2"


class TestDayCheckFm3:
    def test_mb147_style_pinned_breakfast(self):
        """Pin on breakfast makes day infeasible; unpinned day is feasible → FM-3."""
        schedule = [[_slot(), _slot(), _slot()]]
        # High-fat pin blows the fat range; other recipes can form a valid day.
        pin = _recipe("pin", 800.0, 40.0, 70.0, 20.0)
        pool = [
            pin,
            _recipe("a", 700.0, 40.0, 20.0, 90.0),
            _recipe("b", 700.0, 40.0, 20.0, 90.0),
            _recipe("c", 600.0, 20.0, 20.0, 70.0),
            _recipe("d", 600.0, 20.0, 20.0, 70.0),
            _recipe("e", 600.0, 20.0, 20.0, 70.0),
        ]
        profile = _profile(
            schedule,
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 70.0),
            daily_carbs_g=250.0,
            pins={(1, 0): "pin"},
        )
        attr = diagnose_exhausted_search(profile, pool, schedule, 1, None)
        assert attr.status == "attributed"
        assert attr.code == "FM-3"
        assert attr.day_index == 0

        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.failure_mode == "FM-3"
        assert result.termination_code == "TC-2"
        conflicts = result.report["pinned_conflicts"]
        assert conflicts[0]["violation_type"] == PIN_VIOLATION_DOWNSTREAM
        assert conflicts[0]["slot_index"] is None
        assert conflicts[0]["recipe_id"] is None
        assert any(p["recipe_id"] == "pin" for p in conflicts[0]["pinned_slots"])
        assert "remaining_budget" in result.report

    def test_mb148_style_pinned_lunch(self):
        schedule = [[_slot(), _slot(), _slot()]]
        pin = _recipe("pin", 800.0, 40.0, 70.0, 20.0)
        pool = [
            pin,
            _recipe("a", 700.0, 40.0, 20.0, 90.0),
            _recipe("b", 700.0, 40.0, 20.0, 90.0),
            _recipe("c", 600.0, 20.0, 20.0, 70.0),
            _recipe("d", 600.0, 20.0, 20.0, 70.0),
            _recipe("e", 600.0, 20.0, 20.0, 70.0),
        ]
        profile = _profile(
            schedule,
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 70.0),
            daily_carbs_g=250.0,
            pins={(1, 1): "pin"},
        )
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.failure_mode == "FM-3"
        assert result.termination_code == "TC-2"
        assert result.report["pinned_conflicts"][0]["violation_type"] == PIN_VIOLATION_DOWNSTREAM

    def test_pin_still_infeasible_without_pin_is_fm2(self):
        """Day infeasible with and without pin → FM-2, not FM-3."""
        schedule = [[_slot(), _slot()]]
        pin = _recipe("pin", 1000.0, 30.0, 32.0, 125.0)
        pool = [
            pin,
            _recipe("r2", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r3", 1000.0, 30.0, 32.0, 125.0),
        ]
        profile = _profile(
            schedule,
            daily_calories=2000,
            daily_protein_g=200.0,  # unreachable either way
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
            pins={(1, 0): "pin"},
        )
        attr = diagnose_exhausted_search(profile, pool, schedule, 1, None)
        assert attr.code == "FM-2"
        result = run_meal_plan_search(profile, pool, 1, None)
        assert result.failure_mode == "FM-2"


class TestMultiDayFm2:
    def test_mb138_style_second_day_infeasible(self):
        """Day 0 feasible, day 1 not → FM-2 on day 1."""
        day0 = [_slot(), _slot()]
        # Day 1: one slot with tiny cook-time and absurd targets via high protein need
        # Simpler: day 1 has 1 slot that can only hold ~600 kcal recipes vs 2000 target.
        day1 = [MealSlot("12:00", 1, "lunch")]  # cook cap 5 min
        schedule = [day0, day1]
        pool = [
            _recipe("a", 1000.0, 50.0, 32.0, 125.0, cooking_min=10),
            _recipe("b", 1000.0, 50.0, 32.0, 125.0, cooking_min=10),
            _recipe("c", 1000.0, 50.0, 32.0, 125.0, cooking_min=10),
            _recipe("snack", 600.0, 20.0, 20.0, 70.0, cooking_min=5),
            _recipe("snack2", 600.0, 20.0, 20.0, 70.0, cooking_min=5),
        ]
        profile = _profile(
            schedule,
            daily_calories=2000,
            daily_protein_g=100.0,
            daily_fat_g=(50.0, 80.0),
            daily_carbs_g=250.0,
        )
        # Day 1 only has snack recipes under cook cap; 600 kcal can't hit 2000.
        attr = diagnose_exhausted_search(profile, pool, schedule, 2, None)
        assert attr.status == "attributed"
        assert attr.code == "FM-2"
        assert attr.day_index == 1

        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.failure_mode == "FM-2"
        assert result.report["failed_days"][0]["day"] == 1


class TestAcrossDaysFm1:
    def test_hc8_blocks_all_sequences(self):
        """One valid combo per day; HC-8 blocks D=3 → FM-1."""
        # Each day has exactly 2 slots; only two recipes exist, so the only
        # valid day assignment is (a, b) or (b, a). Non-workout reuse across
        # consecutive days then blocks every sequence.
        schedule = [[_slot(), _slot()] for _ in range(3)]
        pool = [
            _recipe("a", 1000.0, 50.0, 32.0, 125.0),
            _recipe("b", 1000.0, 50.0, 32.0, 125.0),
        ]
        profile = _profile(schedule)
        attr = diagnose_exhausted_search(profile, pool, schedule, 3, None)
        assert attr.status == "attributed"
        assert attr.code == "FM-1"
        assert attr.step == "across_days"
        assert any("HC-8" in c for c in attr.details.get("blocking_constraints", []))

        result = run_meal_plan_search(profile, pool, 3, None)
        assert result.failure_mode == "FM-1"
        assert result.report.get("unfillable_slots")
        assert "HC-8" in result.report["unfillable_slots"][0]["blocking_constraints"][0]
        # Day-level: no slot is singled out and no zero candidate count is claimed.
        entry = result.report["unfillable_slots"][0]
        assert entry["slot_index"] is None
        assert "eligible_recipe_count" not in entry
        failure = result.report["failures"][0]
        assert failure["code"] == "FM-1"
        assert "slot_index" not in failure
        assert failure["slot_id"] == ""
        assert "consecutive days" in failure["message"]
        assert failure["fix_hint"] == HC8_SEQUENCE_FIX_HINT


class TestAcrossDaysFm4:
    def test_mb065_style_fiber_floor(self):
        """Both days feasible macros; fiber floor unreachable → FM-4."""
        schedule = [[_slot(), _slot()] for _ in range(2)]
        # Macros OK; fiber max ~5g/day → 10 over 2 days vs floor 70.
        pool = [
            _recipe("a", 1000.0, 50.0, 32.0, 125.0, fiber_g=5.0),
            _recipe("b", 1000.0, 50.0, 32.0, 125.0, fiber_g=5.0),
            _recipe("c", 1000.0, 50.0, 32.0, 125.0, fiber_g=4.0),
            _recipe("d", 1000.0, 50.0, 32.0, 125.0, fiber_g=4.0),
        ]
        profile = _profile(
            schedule,
            micronutrient_targets={"fiber_g": 35.0},
        )
        attr = diagnose_exhausted_search(profile, pool, schedule, 2, None)
        assert attr.status == "attributed"
        assert attr.code == "FM-4"
        assert "micronutrient_shortfall" in attr.details

        result = run_meal_plan_search(profile, pool, 2, None)
        assert result.failure_mode == "FM-4"
        assert result.report.get("deficient_nutrients")
        nutrients = {d["nutrient"] for d in result.report["deficient_nutrients"]}
        assert "fiber_g" in nutrients


    def test_floor_blocked_only_jointly_under_hc8_lists_deficit(self):
        """Per-day maxima pass the floor; HC-8 makes it unreachable → FM-4 with a deficit.

        Best day (a, b) gives 40 g fiber, so per-day maxima sum to 80 >= 60, but
        HC-8 forbids (a, b) twice. Best real sequence is 42 g.
        """
        schedule = [[_slot(), _slot()] for _ in range(2)]
        pool = [
            _recipe("a", 1000.0, 50.0, 32.0, 125.0, fiber_g=20.0),
            _recipe("b", 1000.0, 50.0, 32.0, 125.0, fiber_g=20.0),
            _recipe("c", 1000.0, 50.0, 32.0, 125.0, fiber_g=1.0),
            _recipe("d", 1000.0, 50.0, 32.0, 125.0, fiber_g=1.0),
        ]
        profile = _profile(schedule, micronutrient_targets={"fiber_g": 30.0})
        attr = diagnose_exhausted_search(profile, pool, schedule, 2, None)
        assert attr.status == "attributed"
        assert attr.code == "FM-4"
        assert attr.details["micronutrient_shortfall"]["fiber_g"]["best_achievable"] == 42.0

        weekly = weekly_tracker_from_best_micro(
            profile, 2, attr.details["best_micro"], ["fiber_g"]
        )
        deficient = build_report_fm4(weekly, profile, 2)["deficient_nutrients"]
        assert [d["nutrient"] for d in deficient] == ["fiber_g"]
        assert deficient[0]["achieved"] == 42.0


class TestInconclusive:
    def test_node_budget_keeps_last_event(self):
        schedule = [[_slot(), _slot()]]
        profile = _profile(
            schedule,
            daily_protein_g=200.0,
        )
        pool = [
            _recipe("r1", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r2", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r3", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r4", 1000.0, 30.0, 32.0, 125.0),
        ]
        attr = diagnose_exhausted_search(
            profile, pool, schedule, 1, None, node_limit=1,
        )
        assert attr.status == "inconclusive"
        assert attr.code is None
        assert attr.details.get("reason") == "node_budget"

    def test_carb_downscaling_inconclusive_on_infeasible_day(self):
        schedule = [[_slot(), _slot()]]
        profile = _profile(
            schedule,
            daily_protein_g=200.0,
            enable_carb_scaling=True,
        )
        pool = [
            _recipe("r1", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r2", 1000.0, 30.0, 32.0, 125.0),
        ]
        attr = diagnose_exhausted_search(profile, pool, schedule, 1, None)
        assert attr.status == "inconclusive"
        assert attr.details.get("reason") == "carb_downscaling"

    def test_plan_exists_keeps_last_event_via_search(self):
        """When diagnosis finds a plan the search missed, keep last-event code."""
        # Force attribution to report plan_exists by using a feasible 1-day case
        # diagnosed directly (search wouldn't exhaust on a feasible instance).
        schedule = [[_slot(), _slot()]]
        profile = _profile(schedule)
        pool = [
            _recipe("a", 1000.0, 50.0, 32.0, 125.0),
            _recipe("b", 1000.0, 50.0, 32.0, 125.0),
        ]
        attr = diagnose_exhausted_search(profile, pool, schedule, 1, None)
        assert attr.status == "inconclusive"
        assert attr.details.get("reason") == "plan_exists"


class TestDeterminism:
    def test_diagnose_twice_equal(self):
        schedule = [[_slot(), _slot()]]
        profile = _profile(schedule, daily_protein_g=200.0)
        pool = [
            _recipe("r1", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r2", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r3", 1000.0, 30.0, 32.0, 125.0),
            _recipe("r4", 1000.0, 30.0, 32.0, 125.0),
        ]
        a = diagnose_exhausted_search(profile, pool, schedule, 1, None)
        b = diagnose_exhausted_search(profile, pool, schedule, 1, None)
        assert a == b

        r1 = run_meal_plan_search(profile, pool, 1, None)
        r2 = run_meal_plan_search(profile, pool, 1, None)
        assert r1.failure_mode == r2.failure_mode == "FM-2"
        assert r1.report.get("diagnosis") == r2.report.get("diagnosis")
        assert r1.report.get("failed_days") == r2.report.get("failed_days")
