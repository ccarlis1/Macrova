"""Tests for src/planning/slot_attributes.py — derived slot attributes (Spec 2.1.2)."""

from src.planning.phase0_models import MealSlot, PlanningUserProfile
from src.planning.slot_attributes import (
    cooking_time_max,
    explicit_workout_gaps_for_day,
    time_until_next_meal,
)


def _slot(time: str, busyness: int = 2, meal_type: str = "lunch") -> MealSlot:
    return MealSlot(time=time, busyness_level=busyness, meal_type=meal_type)


def _profile(workouts_by_day=None) -> PlanningUserProfile:
    return PlanningUserProfile(
        daily_calories=2000,
        daily_protein_g=150.0,
        daily_fat_g=(50.0, 80.0),
        daily_carbs_g=200.0,
        workout_after_meal_indices_by_day=workouts_by_day,
    )


class TestCookingTimeMax:
    def test_busyness_band_mapping(self):
        assert cooking_time_max(1) == 5
        assert cooking_time_max(2) == 15
        assert cooking_time_max(3) == 30

    def test_busyness_4_is_unbounded(self):
        assert cooking_time_max(4) is None

    def test_out_of_range_falls_back_defensively(self):
        assert cooking_time_max(0) == 30
        assert cooking_time_max(99) == 30


class TestTimeUntilNextMeal:
    def test_same_day_gap_in_hours(self):
        day = [_slot("08:00"), _slot("12:30")]
        assert time_until_next_meal(day[0], 0, day, None) == 4.5

    def test_last_slot_overnight_to_next_day_first_slot(self):
        day = [_slot("20:00")]
        next_first = _slot("08:00")
        assert time_until_next_meal(day[0], 0, day, next_first) == 12.0

    def test_last_slot_with_no_next_day_is_infinite(self):
        day = [_slot("20:00")]
        assert time_until_next_meal(day[0], 0, day, None) == float("inf")

    def test_non_positive_delta_wraps_to_next_day(self):
        # Two slots with identical times: delta 0 is treated as a 24 h wrap.
        day = [_slot("09:00"), _slot("09:00")]
        assert time_until_next_meal(day[0], 0, day, None) == 24.0


class TestExplicitWorkoutGaps:
    def test_none_means_legacy_activity_schedule_only(self):
        assert explicit_workout_gaps_for_day(_profile(None), 0) is None

    def test_empty_day_returns_empty_set(self):
        assert explicit_workout_gaps_for_day(_profile([[]]), 0) == set()

    def test_gap_indices_returned_as_set(self):
        profile = _profile([[1], [1, 2]])
        assert explicit_workout_gaps_for_day(profile, 0) == {1}
        assert explicit_workout_gaps_for_day(profile, 1) == {1, 2}

    def test_out_of_range_day_index_returns_empty_set(self):
        profile = _profile([[1]])
        assert explicit_workout_gaps_for_day(profile, 5) == set()
        assert explicit_workout_gaps_for_day(profile, -1) == set()
