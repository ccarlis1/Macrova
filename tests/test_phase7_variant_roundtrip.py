"""Phase 7: Round-trip invariant tests for variant assignments."""

from __future__ import annotations

from typing import Dict, List

from src.data_layer.models import NutritionProfile
from src.planning.phase0_models import (
    Assignment,
    DailyTracker,
    MealSlot,
    PlanningRecipe,
    PlanningUserProfile,
    WeeklyTracker,
)
from src.planning.phase7_search import (
    _apply_assignment,
    _remove_assignment,
    _update_weekly_after_day,
)


def _make_recipe_with_primary_carb() -> PlanningRecipe:
    """Helper: recipe with a valid primary_carb_contribution."""
    base = NutritionProfile(400.0, 30.0, 10.0, 50.0)
    contrib = NutritionProfile(100.0, 5.0, 1.0, 20.0)
    return PlanningRecipe(
        id="r_var",
        name="r_var",
        ingredients=[],
        cooking_time_minutes=10,
        nutrition=base,
        primary_carb_contribution=contrib,
        primary_carb_source="rice",
    )


def _make_profile_for_variants() -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=100.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=250.0,
        enable_primary_carb_downscaling=True,
        max_scaling_steps=4,
        scaling_step_fraction=0.10,
    )


def test_variant_apply_remove_round_trip_identity():
    """Applying then removing a variant assignment must be state-neutral."""
    recipe = _make_recipe_with_primary_carb()
    profile = _make_profile_for_variants()

    # Simple one-day, one-slot schedule
    schedule: List[List[MealSlot]] = [[MealSlot(time="12:00", busyness_level=2, meal_type="lunch")]]

    # Initial empty state
    daily_trackers: Dict[int, DailyTracker] = {}
    weekly_tracker = WeeklyTracker()
    assignments: List[Assignment] = []

    # Snapshot initial state
    daily_before = dict(daily_trackers)
    weekly_before = WeeklyTracker(
        weekly_totals=weekly_tracker.weekly_totals,
        days_completed=weekly_tracker.days_completed,
        days_remaining=weekly_tracker.days_remaining,
        carryover_needs=dict(weekly_tracker.carryover_needs),
    )
    assignments_before = list(assignments)

    # Apply variant with index 1
    from src.planning.phase9_carb_scaling import compute_variant_nutrition

    variant_index = 1
    variant_nutrition = compute_variant_nutrition(recipe, variant_index, profile)
    _apply_assignment(
        daily_trackers,
        assignments,
        day_index=0,
        slot_index=0,
        recipe_id=recipe.id,
        recipe=recipe,
        is_workout=False,
        schedule=schedule,
        variant_index=variant_index,
        variant_nutrition=variant_nutrition,
    )

    # Now remove the same assignment
    assert len(assignments) == 1
    assignment = assignments[0]
    _remove_assignment(
        daily_trackers,
        weekly_tracker,
        assignments,
        assignment,
        recipe,
        is_workout=False,
        schedule=schedule,
        profile=profile,
        completed_days=set(),
    )

    # Search-visible state must be exactly as before
    assert daily_trackers == daily_before
    assert assignments == assignments_before
    assert weekly_tracker.weekly_totals.calories == weekly_before.weekly_totals.calories
    assert weekly_tracker.weekly_totals.protein_g == weekly_before.weekly_totals.protein_g
    assert weekly_tracker.weekly_totals.fat_g == weekly_before.weekly_totals.fat_g
    assert weekly_tracker.weekly_totals.carbs_g == weekly_before.weekly_totals.carbs_g
    assert weekly_tracker.days_completed == weekly_before.days_completed
    assert weekly_tracker.carryover_needs == weekly_before.carryover_needs


def test_full_day_unwind_subtracts_full_day_from_weekly():
    """When a completed day is unwound in reverse slot order, weekly must be reduced by the full day (per-slot subtract)."""
    recipe = _make_recipe_with_primary_carb()
    profile = _make_profile_for_variants()

    # One day, two slots
    schedule: List[List[MealSlot]] = [
        [MealSlot(time="08:00", busyness_level=2, meal_type="breakfast"), MealSlot(time="12:00", busyness_level=2, meal_type="lunch")],
    ]
    D = 1

    daily_trackers: Dict[int, DailyTracker] = {}
    weekly_tracker = WeeklyTracker()
    assignments: List[Assignment] = []
    completed_days: set = set()

    # Apply slot 0 and slot 1 (fill the day)
    _apply_assignment(
        daily_trackers,
        assignments,
        day_index=0,
        slot_index=0,
        recipe_id=recipe.id,
        recipe=recipe,
        is_workout=False,
        schedule=schedule,
        variant_index=0,
    )
    _apply_assignment(
        daily_trackers,
        assignments,
        day_index=0,
        slot_index=1,
        recipe_id=recipe.id,
        recipe=recipe,
        is_workout=False,
        schedule=schedule,
        variant_index=0,
    )
    assert len(assignments) == 2
    assert 0 in daily_trackers and daily_trackers[0].slots_assigned == 2

    # Simulate day completion: add day to weekly
    _update_weekly_after_day(daily_trackers, weekly_tracker, 0, schedule, profile, D)
    completed_days.add(0)
    day_cal = daily_trackers[0].calories_consumed
    assert weekly_tracker.weekly_totals.calories == day_cal
    assert weekly_tracker.days_completed == 1

    # Unwind in reverse order (slot 1 then slot 0) — same order as _unwind_to
    to_remove = sorted(assignments, key=lambda a: (a.day_index, a.slot_index), reverse=True)
    for a in to_remove:
        r = recipe
        day_slots = schedule[a.day_index]
        next_first = schedule[a.day_index + 1][0] if a.day_index + 1 < len(schedule) else None
        from src.planning.slot_attributes import activity_context, is_workout_slot
        act_ctx = activity_context(day_slots[a.slot_index], a.slot_index, day_slots, next_first, profile.activity_schedule or {})
        _remove_assignment(
            daily_trackers,
            weekly_tracker,
            assignments,
            a,
            r,
            is_workout_slot(act_ctx),
            schedule,
            profile,
            completed_days=completed_days,
        )

    # Weekly must be back to zero; daily_trackers empty
    assert weekly_tracker.weekly_totals.calories == 0.0
    assert weekly_tracker.weekly_totals.protein_g == 0.0
    assert weekly_tracker.weekly_totals.fat_g == 0.0
    assert weekly_tracker.weekly_totals.carbs_g == 0.0
    assert weekly_tracker.days_completed == 0
    assert len(daily_trackers) == 0
    assert len(assignments) == 0

