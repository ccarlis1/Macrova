"""Phase 3 unit tests: feasibility constraints FC-1 through FC-5. Spec Section 5.

No search, no scoring — hand-built state and candidate lists only.
"""

from __future__ import annotations

import pytest

from src.data_layer.models import (
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
from src.planning.phase3_feasibility import (
    FeasibilityStateView,
    MacroBoundsPrecomputation,
    check_fc1_daily_calories,
    check_fc2_daily_macros,
    check_fc3_incremental_ul,
    check_fc4_cross_day_rdi,
    check_fc5_candidate_set,
    check_fc1_fc2_fc3,
    precompute_macro_bounds,
    precompute_max_daily_achievable,
)


def _make_recipe(
    rid: str,
    calories: float = 500.0,
    protein: float = 30.0,
    fat: float = 20.0,
    carbs: float = 40.0,
    micronutrients: MicronutrientProfile | None = None,
) -> PlanningRecipe:
    return PlanningRecipe(
        id=rid,
        name=rid,
        ingredients=[],
        cooking_time_minutes=10,
        nutrition=NutritionProfile(calories, protein, fat, carbs, micronutrients=micronutrients),
        primary_carb_contribution=None,
    )


def _make_slot() -> MealSlot:
    return MealSlot("12:00", 2, "lunch")


def _make_profile(
    daily_calories: int = 2000,
    daily_protein_g: float = 100.0,
    daily_fat_g: tuple[float, float] = (50.0, 80.0),
    daily_carbs_g: float = 200.0,
    max_daily_calories: int | None = 2500,
) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=daily_calories,
        daily_protein_g=daily_protein_g,
        daily_fat_g=daily_fat_g,
        daily_carbs_g=daily_carbs_g,
        max_daily_calories=max_daily_calories,
    )


def _make_state(
    daily_trackers: dict | None = None,
    weekly_tracker: WeeklyTracker | None = None,
    schedule: list | None = None,
) -> FeasibilityStateView:
    return FeasibilityStateView(
        daily_trackers=daily_trackers or {},
        weekly_tracker=weekly_tracker or WeeklyTracker(),
        schedule=schedule or [[_make_slot(), _make_slot()]],
    )


# --- FC-1: Daily calories ---


class TestFC1DailyCalories:
    """FC-1: Daily calorie feasibility; ±10% tolerance."""

    def test_at_lower_tolerance_bound(self):
        profile = _make_profile(daily_calories=2000)
        tracker = DailyTracker(calories_consumed=1700.0, slots_assigned=1, slots_total=2)
        state = _make_state(
            daily_trackers={0: tracker},
            schedule=[[_make_slot(), _make_slot()]],
        )
        recipe = _make_recipe("r1", calories=100.0)  # total 1800, within 2000±10%
        macro = precompute_macro_bounds([
            _make_recipe("r2", calories=200.0),
        ])
        assert check_fc1_daily_calories(
            recipe, _make_slot(), 0, 0, state, profile, None, macro
        ) is True

    def test_at_upper_tolerance_bound(self):
        profile = _make_profile(daily_calories=2000)
        tracker = DailyTracker(calories_consumed=1800.0, slots_assigned=1, slots_total=2)
        state = _make_state(daily_trackers={0: tracker}, schedule=[[_make_slot(), _make_slot()]])
        recipe = _make_recipe("r1", calories=400.0)  # total 2200 = 2000+10%
        macro = precompute_macro_bounds([_make_recipe("r2", calories=0.0)])
        assert check_fc1_daily_calories(
            recipe, _make_slot(), 0, 0, state, profile, None, macro
        ) is True

    def test_slightly_over_cap_rejected(self):
        profile = _make_profile(max_daily_calories=2000)
        tracker = DailyTracker(calories_consumed=1500.0, slots_assigned=1, slots_total=2)
        state = _make_state(daily_trackers={0: tracker})
        recipe = _make_recipe("r1", calories=600.0)  # 2100 > 2000
        macro = precompute_macro_bounds([_make_recipe("r2", calories=100.0)])
        assert check_fc1_daily_calories(
            recipe, _make_slot(), 0, 0, state, profile, None, macro
        ) is False

    def test_remaining_lower_bound_unreachable_rejected(self):
        profile = _make_profile(daily_calories=2000)
        tracker = DailyTracker(calories_consumed=0.0, slots_assigned=0, slots_total=2)
        state = _make_state(daily_trackers={0: tracker}, schedule=[[_make_slot(), _make_slot()]])
        recipe_low = _make_recipe("r1", calories=1000.0)  # used=1000, c_remaining=1000; need [800,1200] from 1 slot
        macro = precompute_macro_bounds([_make_recipe("r2", calories=500.0)])  # [500,500] no intersection
        assert check_fc1_daily_calories(
            recipe_low, _make_slot(), 0, 0, state, profile, None, macro
        ) is False


# --- FC-2: Macros ---


class TestFC2DailyMacros:
    """FC-2: Protein/carbs ±10%; fat within [min,max]."""

    def test_protein_at_tolerance(self):
        profile = _make_profile(daily_protein_g=100.0, daily_carbs_g=200.0)
        tracker = DailyTracker(
            protein_consumed=85.0, carbs_consumed=0.0, fat_consumed=0.0,
            slots_assigned=0, slots_total=2,
        )
        state = _make_state(daily_trackers={0: tracker}, schedule=[[_make_slot(), _make_slot()]])
        recipe = _make_recipe("r1", protein=10.0, carbs=40.0, fat=20.0)  # 1 slot left; need pro 5±10, carbs 160±20, fat [30,60]
        macro = precompute_macro_bounds([
            _make_recipe("r2", protein=10.0, carbs=160.0, fat=45.0),
        ])
        assert check_fc2_daily_macros(
            recipe, _make_slot(), 0, 0, state, profile, None, macro
        ) is True

    def test_protein_unreachable(self):
        profile = _make_profile(daily_protein_g=100.0)
        tracker = DailyTracker(protein_consumed=50.0, slots_assigned=0, slots_total=2)
        state = _make_state(daily_trackers={0: tracker}, schedule=[[_make_slot(), _make_slot()]])
        recipe = _make_recipe("r1", protein=60.0)  # 110 used, need 90-110 from 1 slot; max from 1 recipe say 30
        macro = precompute_macro_bounds([_make_recipe("r2", protein=30.0)])
        assert check_fc2_daily_macros(
            recipe, _make_slot(), 0, 0, state, profile, None, macro
        ) is False

    def test_fat_min_unmet(self):
        profile = _make_profile(daily_fat_g=(50.0, 80.0))
        tracker = DailyTracker(fat_consumed=30.0, slots_assigned=0, slots_total=2)
        state = _make_state(daily_trackers={0: tracker}, schedule=[[_make_slot(), _make_slot()]])
        recipe = _make_recipe("r1", fat=5.0)  # 35 used, need 50-80 so need 15-45 from 1 slot
        macro = precompute_macro_bounds([_make_recipe("r2", fat=10.0)])  # max 10 from 1 slot, can't reach 15
        assert check_fc2_daily_macros(
            recipe, _make_slot(), 0, 0, state, profile, None, macro
        ) is False

    def test_fat_max_exceeded(self):
        profile = _make_profile(daily_fat_g=(50.0, 80.0))
        tracker = DailyTracker(fat_consumed=70.0, slots_assigned=0, slots_total=2)
        state = _make_state(daily_trackers={0: tracker}, schedule=[[_make_slot(), _make_slot()]])
        recipe = _make_recipe("r1", fat=20.0)  # 90 used, need 50-80 so we're over; remaining need -10 to -20 from 1 slot
        macro = precompute_macro_bounds([_make_recipe("r2", fat=15.0)])  # min 15 from 1 slot, can't get -10
        assert check_fc2_daily_macros(
            recipe, _make_slot(), 0, 0, state, profile, None, macro
        ) is False


# --- FC-3: Incremental UL ---


class TestFC3IncrementalUL:
    """FC-3: T_d + recipe <= resolved_UL; equality allowed."""

    def test_ul_equality_allowed(self):
        ul = UpperLimits(vitamin_c_mg=100.0)
        tracker = DailyTracker(micronutrients_consumed={"vitamin_c_mg": 50.0})
        state = _make_state(daily_trackers={0: tracker})
        recipe = _make_recipe("r1", micronutrients=MicronutrientProfile(vitamin_c_mg=50.0))
        assert check_fc3_incremental_ul(
            recipe, _make_slot(), 0, state, _make_profile(), ul
        ) is True

    def test_ul_excess_rejected(self):
        ul = UpperLimits(vitamin_c_mg=100.0)
        tracker = DailyTracker(micronutrients_consumed={"vitamin_c_mg": 60.0})
        state = _make_state(daily_trackers={0: tracker})
        recipe = _make_recipe("r1", micronutrients=MicronutrientProfile(vitamin_c_mg=50.0))
        assert check_fc3_incremental_ul(
            recipe, _make_slot(), 0, state, _make_profile(), ul
        ) is False


# --- FC-4: Precomputation and trigger ---


class TestFC4Precomputation:
    """FC-4: max_daily_achievable precomputation and irrecoverability check."""

    def test_precomputation_correct_for_small_pool(self):
        recipes = [
            _make_recipe("r1", micronutrients=MicronutrientProfile(vitamin_c_mg=10.0)),
            _make_recipe("r2", micronutrients=MicronutrientProfile(vitamin_c_mg=30.0)),
            _make_recipe("r3", micronutrients=MicronutrientProfile(vitamin_c_mg=20.0)),
        ]
        mda = precompute_max_daily_achievable(
            recipes,
            nutrient_names=["vitamin_c_mg"],
            slot_counts={1, 2, 3},
        )
        assert mda["vitamin_c_mg"][1] == 30.0
        assert mda["vitamin_c_mg"][2] == 30.0 + 20.0
        assert mda["vitamin_c_mg"][3] == 30.0 + 20.0 + 10.0

    def test_trigger_when_irrecoverable(self):
        profile = _make_profile()
        profile.micronutrient_targets = {"vitamin_c_mg": 100.0}
        wt = WeeklyTracker(
            weekly_totals=NutritionProfile(0.0, 0.0, 0.0, 0.0, micronutrients=MicronutrientProfile(vitamin_c_mg=0.0)),
            days_remaining=2,
        )
        state = _make_state(weekly_tracker=wt, schedule=[[_make_slot()], [_make_slot()]])
        mda = {"vitamin_c_mg": {1: 50.0}}
        D = 2
        # deficit = 100*2 - 0 = 200; days_left * max = 2 * 50 = 100; 200 > 100 -> irrecoverable
        assert check_fc4_cross_day_rdi(1, state, profile, D, mda) is False

    def test_no_trigger_when_recoverable(self):
        profile = _make_profile()
        profile.micronutrient_targets = {"vitamin_c_mg": 100.0}
        wt = WeeklyTracker(
            weekly_totals=NutritionProfile(0.0, 0.0, 0.0, 0.0, micronutrients=MicronutrientProfile(vitamin_c_mg=0.0)),
            days_remaining=2,
        )
        state = _make_state(weekly_tracker=wt, schedule=[[_make_slot()], [_make_slot()]])
        mda = {"vitamin_c_mg": {1: 150.0}}
        D = 2
        assert check_fc4_cross_day_rdi(1, state, profile, D, mda) is True


# --- FC-5: Candidate set and future slots ---


class TestFC5CandidateSet:
    """FC-5: Empty candidate set; future slot with zero/one eligible."""

    def test_empty_candidate_set_rejected(self):
        assert check_fc5_candidate_set(
            candidate_recipe_ids=set(),
            tentative_recipe_id="r1",
            used_recipe_ids_today=set(),
            future_slot_eligible_recipe_ids=[{"r2"}],
        ) is False

    def test_future_slot_zero_eligible_rejected(self):
        assert check_fc5_candidate_set(
            candidate_recipe_ids={"r1"},
            tentative_recipe_id="r1",
            used_recipe_ids_today=set(),
            future_slot_eligible_recipe_ids=[{"r1"}],  # only r1 eligible; after using r1, none
        ) is False

    def test_future_slot_one_eligible_accepted(self):
        assert check_fc5_candidate_set(
            candidate_recipe_ids={"r1", "r2"},
            tentative_recipe_id="r1",
            used_recipe_ids_today=set(),
            future_slot_eligible_recipe_ids=[{"r1", "r2"}],
        ) is True


# --- Combined FC-1/FC-2/FC-3 ---


class TestCheckFC1FC2FC3:
    """Combined per-candidate feasibility."""

    def test_all_pass(self):
        profile = _make_profile(daily_calories=2000, max_daily_calories=2500)
        tracker = DailyTracker(
            calories_consumed=500.0,
            protein_consumed=30.0,
            fat_consumed=20.0,
            carbs_consumed=50.0,
            slots_assigned=0,
            slots_total=2,
        )
        state = _make_state(daily_trackers={0: tracker}, schedule=[[_make_slot(), _make_slot()]])
        recipe = _make_recipe("r1", calories=400.0, protein=30.0, fat=20.0, carbs=60.0)
        # After r1: 900 cal, 60 pro, 40 fat, 110 carbs. Need from 1 slot: cal in [900,1300], pro [30,50], fat [10,40], carbs [80,100]
        macro = precompute_macro_bounds([
            _make_recipe("r2", calories=1000.0, protein=40.0, fat=25.0, carbs=90.0),
        ])
        assert check_fc1_fc2_fc3(
            recipe, _make_slot(), 0, 0, state, profile, None, macro
        ) is True
