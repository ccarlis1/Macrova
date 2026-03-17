"""Phase 0 unit tests: inputs, reference data, and state structures.

Spec: MEALPLAN_SPECIFICATION_v1.md Sections 2 and 3.
Roadmap: Phase 0 — Foundation.
"""

import pytest
import json
from pathlib import Path

from src.planning.phase0_models import (
    MealSlot,
    PlanningUserProfile,
    PlanningRecipe,
    DailyTracker,
    WeeklyTracker,
    validate_schedule_structure,
    validate_planning_horizon,
    total_decision_points,
    MAX_SLOTS_PER_DAY,
    MIN_SLOTS_PER_DAY,
    PLANNING_DAYS_MIN,
    PLANNING_DAYS_MAX,
    micronutrient_profile_to_dict,
)
from src.planning.slot_attributes import (
    activity_context,
    is_workout_slot,
    time_until_next_meal,
    satiety_requirement,
    cooking_time_max,
)
from src.data_layer.models import (
    NutritionProfile,
    MicronutrientProfile,
    Ingredient,
    UpperLimits,
)
from src.data_layer.upper_limits import (
    UpperLimitsLoader,
    resolve_upper_limits,
    DEFAULT_UL_REFERENCE_PATH,
)


# --- Schedule validation (Section 2.1.1) ---


class TestScheduleValidation:
    """1–8 slots per day valid; 0 slots rejected; ordering maintained."""

    def test_one_slot_per_day_valid(self):
        schedule = [[MealSlot("08:00", 2, "breakfast")]]
        validate_schedule_structure(schedule, 1)

    def test_eight_slots_per_day_valid(self):
        slots = [
            MealSlot(f"{h:02d}:00", 3, "meal")
            for h in range(8)
        ]
        schedule = [slots]
        validate_schedule_structure(schedule, 1)

    def test_zero_slots_rejected(self):
        schedule = [[]]
        with pytest.raises(ValueError, match="minimum is 1"):
            validate_schedule_structure(schedule, 1)

    def test_more_than_eight_slots_rejected(self):
        slots = [MealSlot("08:00", 3, "meal")] * 9
        schedule = [slots]
        with pytest.raises(ValueError, match="maximum is 8"):
            validate_schedule_structure(schedule, 1)

    def test_schedule_length_must_match_D(self):
        schedule = [
            [MealSlot("08:00", 2, "breakfast")],
            [MealSlot("12:00", 3, "lunch")],
        ]
        with pytest.raises(ValueError, match="exactly D=3"):
            validate_schedule_structure(schedule, 3)

    def test_correct_ordering_maintained(self):
        schedule = [
            [MealSlot("07:00", 1, "breakfast"), MealSlot("13:00", 3, "lunch"), MealSlot("19:00", 4, "dinner")],
        ]
        validate_schedule_structure(schedule, 1)
        assert len(schedule[0]) == 3
        assert schedule[0][0].time == "07:00"
        assert schedule[0][1].time == "13:00"
        assert schedule[0][2].time == "19:00"


# --- Derived slot attributes (Section 2.1.2) ---


class TestDerivedSlotAttributes:
    """Workout vs non-workout; overnight fast ahead; busyness levels."""

    def test_cooking_time_max_busyness_levels(self):
        assert cooking_time_max(1) == 5
        assert cooking_time_max(2) == 15
        assert cooking_time_max(3) == 30
        assert cooking_time_max(4) is None

    def test_satiety_high_when_more_than_four_hours_until_next(self):
        assert satiety_requirement(5.0, False) == "high"
        assert satiety_requirement(4.5, False) == "high"

    def test_satiety_moderate_when_under_four_hours(self):
        assert satiety_requirement(3.0, False) == "moderate"
        assert satiety_requirement(4.0, False) == "moderate"

    def test_satiety_high_when_last_slot_and_overnight_fast_12_plus(self):
        assert satiety_requirement(12.0, True) == "high"
        assert satiety_requirement(14.0, True) == "high"

    def test_satiety_moderate_when_last_slot_but_short_overnight(self):
        # Spec: high if time_until_next_meal > 4h OR (last slot and >= 12h). So moderate when <= 4h (e.g. 3h gap).
        assert satiety_requirement(3.0, True) == "moderate"

    def test_time_until_next_meal_same_day(self):
        day_slots = [
            MealSlot("08:00", 2, "breakfast"),
            MealSlot("13:00", 3, "lunch"),
            MealSlot("19:00", 4, "dinner"),
        ]
        # 08:00 -> 13:00 = 5h
        h = time_until_next_meal(day_slots[0], 0, day_slots, None)
        assert h == pytest.approx(5.0)
        # 13:00 -> 19:00 = 6h
        h = time_until_next_meal(day_slots[1], 1, day_slots, None)
        assert h == pytest.approx(6.0)

    def test_time_until_next_meal_to_next_day(self):
        day_slots = [MealSlot("22:00", 3, "dinner")]
        next_day_first = MealSlot("07:00", 2, "breakfast")
        h = time_until_next_meal(day_slots[0], 0, day_slots, next_day_first)
        assert h == pytest.approx(9.0)  # 22->24 = 2h, 0->7 = 7h

    def test_activity_context_sedentary_when_no_workout(self):
        slot = MealSlot("12:00", 3, "lunch")
        day_slots = [MealSlot("08:00", 2, "b"), slot, MealSlot("18:00", 4, "d")]
        ctx = activity_context(slot, 1, day_slots, None, {})
        assert "sedentary" in ctx
        assert "pre_workout" not in ctx
        assert "post_workout" not in ctx

    def test_activity_context_pre_workout(self):
        slot = MealSlot("16:00", 2, "snack")  # 2h before workout at 18:00
        day_slots = [slot]
        ctx = activity_context(slot, 0, day_slots, None, {"workout_start": "18:00", "workout_end": "19:00"})
        assert "pre_workout" in ctx

    def test_activity_context_post_workout(self):
        slot = MealSlot("20:00", 3, "dinner")  # 1h after workout end 19:00
        day_slots = [slot]
        ctx = activity_context(slot, 0, day_slots, None, {"workout_start": "18:00", "workout_end": "19:00"})
        assert "post_workout" in ctx

    def test_is_workout_slot_true_when_pre_or_post(self):
        assert is_workout_slot(frozenset({"pre_workout"})) is True
        assert is_workout_slot(frozenset({"post_workout"})) is True
        assert is_workout_slot(frozenset({"pre_workout", "overnight_fast_ahead"})) is True

    def test_is_workout_slot_false_when_sedentary_only(self):
        assert is_workout_slot(frozenset({"sedentary"})) is False
        assert is_workout_slot(frozenset({"sedentary", "overnight_fast_ahead"})) is False

    def test_overnight_fast_ahead_when_long_gap(self):
        slot = MealSlot("12:00", 3, "lunch")
        day_slots = [MealSlot("08:00", 2, "b"), slot, MealSlot("19:00", 4, "d")]  # 7h until next
        ctx = activity_context(slot, 1, day_slots, None, {})
        assert "overnight_fast_ahead" in ctx


# --- UL loading (Section 2.3) ---


class TestULLoading:
    """Demographic selection, override merging, null handling per spec."""

    def test_default_reference_path_defined(self):
        assert DEFAULT_UL_REFERENCE_PATH == "data/reference/ul_by_demographic.json"

    def test_reference_file_exists(self):
        assert Path(DEFAULT_UL_REFERENCE_PATH).exists()

    def test_load_for_demographic_adult_male(self):
        loader = UpperLimitsLoader(DEFAULT_UL_REFERENCE_PATH)
        ul = loader.load_for_demographic("adult_male")
        assert ul.vitamin_a_ug == 3000
        assert ul.iron_mg == 45
        assert ul.vitamin_k_ug is None

    def test_load_for_demographic_adult_female(self):
        loader = UpperLimitsLoader(DEFAULT_UL_REFERENCE_PATH)
        ul = loader.load_for_demographic("adult_female")
        assert ul.vitamin_a_ug == 3000

    def test_unknown_demographic_raises(self):
        loader = UpperLimitsLoader(DEFAULT_UL_REFERENCE_PATH)
        with pytest.raises(KeyError, match="not found"):
            loader.load_for_demographic("unknown_demographic")

    def test_resolve_override_replaces_reference(self):
        loader = UpperLimitsLoader(DEFAULT_UL_REFERENCE_PATH)
        ul = resolve_upper_limits(loader, "adult_male", {"vitamin_a_ug": 2500})
        assert ul.vitamin_a_ug == 2500
        assert ul.iron_mg == 45

    def test_resolve_null_override_ignored(self):
        loader = UpperLimitsLoader(DEFAULT_UL_REFERENCE_PATH)
        ref = loader.load_for_demographic("adult_male")
        ul = resolve_upper_limits(loader, "adult_male", {"vitamin_a_ug": None})
        assert ul.vitamin_a_ug == ref.vitamin_a_ug

    def test_resolve_no_overrides_returns_reference(self):
        loader = UpperLimitsLoader(DEFAULT_UL_REFERENCE_PATH)
        ul = resolve_upper_limits(loader, "adult_male", None)
        assert ul.vitamin_a_ug == 3000


# --- State structures (Section 3.1–3.3) ---


class TestStateStructures:
    """Daily tracker, weekly tracker, assignment sequence type."""

    def test_daily_tracker_creation(self):
        t = DailyTracker(
            calories_consumed=500.0,
            protein_consumed=30.0,
            fat_consumed=20.0,
            carbs_consumed=50.0,
            micronutrients_consumed={"iron_mg": 5.0},
            used_recipe_ids={"r1"},
            non_workout_recipe_ids={"r1"},
            slots_assigned=1,
            slots_total=3,
        )
        assert t.calories_consumed == 500.0
        assert t.slots_total == 3
        assert "r1" in t.used_recipe_ids
        assert t.micronutrients_consumed["iron_mg"] == 5.0

    def test_daily_tracker_defaults(self):
        t = DailyTracker()
        assert t.calories_consumed == 0.0
        assert t.used_recipe_ids == set()
        assert t.non_workout_recipe_ids == set()
        assert t.slots_assigned == 0
        assert t.micronutrients_consumed == {}

    def test_weekly_tracker_creation(self):
        np = NutritionProfile(100.0, 10.0, 5.0, 12.0)
        w = WeeklyTracker(weekly_totals=np, days_completed=1, days_remaining=6, carryover_needs={"iron_mg": 2.0})
        assert w.days_completed == 1
        assert w.days_remaining == 6
        assert w.weekly_totals.calories == 100.0
        assert w.carryover_needs["iron_mg"] == 2.0

    def test_weekly_tracker_defaults(self):
        w = WeeklyTracker()
        assert w.days_completed == 0
        assert w.carryover_needs == {}
        assert w.weekly_totals.calories == 0.0

    def test_assignment_sequence_type(self):
        from src.planning.phase0_models import Assignment
        a = Assignment(0, 0, "recipe_1")
        assert a.day_index == 0
        assert a.slot_index == 0
        assert a.recipe_id == "recipe_1"
        assert a.variant_index == 0
        a2 = Assignment(1, 1, "r2", 1)
        assert a2.variant_index == 1


# --- Planning horizon (Section 2.4) ---


class TestPlanningHorizon:
    """D in [1, 7]; N = total decision points."""

    def test_D_valid_range(self):
        for d in (1, 4, 7):
            validate_planning_horizon(d)

    def test_D_below_one_rejected(self):
        with pytest.raises(ValueError, match="1.*7"):
            validate_planning_horizon(0)
        with pytest.raises(ValueError, match="1.*7"):
            validate_planning_horizon(-1)

    def test_D_above_seven_rejected(self):
        with pytest.raises(ValueError, match="1.*7"):
            validate_planning_horizon(8)

    def test_total_decision_points(self):
        schedule = [
            [MealSlot("08:00", 2, "b"), MealSlot("13:00", 3, "l")],
            [MealSlot("08:00", 2, "b"), MealSlot("13:00", 3, "l"), MealSlot("19:00", 4, "d")],
        ]
        n = total_decision_points(schedule, 2)
        assert n == 5  # 2 slots + 3 slots


# --- PlanningUserProfile and PlanningRecipe ---


class TestPlanningUserProfileAndRecipe:
    """Spec Section 2.1 and 2.2 types construct and serialize."""

    def test_planning_user_profile_construction(self):
        schedule = [[MealSlot("08:00", 2, "breakfast")]]
        u = PlanningUserProfile(
            daily_calories=2400,
            daily_protein_g=150.0,
            daily_fat_g=(60.0, 80.0),
            daily_carbs_g=250.0,
            schedule=schedule,
            excluded_ingredients=["peanuts"],
            micronutrient_targets={"iron_mg": 18.0},
            pinned_assignments={(1, 0): "recipe_breakfast"},
            activity_schedule={"workout_start": "18:00"},
            enable_primary_carb_downscaling=False,
        )
        assert u.daily_calories == 2400
        assert u.excluded_ingredients == ["peanuts"]
        assert u.pinned_assignments[(1, 0)] == "recipe_breakfast"
        assert len(u.schedule[0]) == 1

    def test_planning_recipe_construction(self):
        nut = NutritionProfile(400.0, 25.0, 15.0, 40.0)
        r = PlanningRecipe(
            id="r1",
            name="Oatmeal",
            ingredients=[],
            cooking_time_minutes=10,
            nutrition=nut,
            primary_carb_contribution=None,
        )
        assert r.id == "r1"
        assert r.nutrition.calories == 400.0
        assert r.primary_carb_contribution is None

    def test_micronutrient_profile_to_dict(self):
        m = MicronutrientProfile(iron_mg=5.0, vitamin_c_mg=60.0)
        d = micronutrient_profile_to_dict(m)
        assert d["iron_mg"] == 5.0
        assert d["vitamin_c_mg"] == 60.0
        assert "vitamin_a_ug" in d
