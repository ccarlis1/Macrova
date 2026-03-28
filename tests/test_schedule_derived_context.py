"""Unit tests for canonical schedule → planner context (explicit workouts, per-meal busyness)."""

import pytest

from src.data_layer.models import UserProfile
from src.models.schedule import DaySchedule, MealSlot as CanonMeal, WorkoutSlot
from src.planning.converters import convert_profile
from src.planning.phase0_models import MealSlot as PlanMeal
from src.planning.slot_attributes import (
    activity_context,
    activity_context_for_profile,
    explicit_workout_gaps_for_day,
)


class TestExplicitWorkoutActivityContext:
    """Topology-based pre/post tagging (``after_meal_index``)."""

    def test_gap_after_meal_1_tags_pre_and_post(self):
        m0 = PlanMeal("08:00", 2, "breakfast")
        m1 = PlanMeal("12:00", 3, "lunch")
        m2 = PlanMeal("18:00", 4, "dinner")
        day = [m0, m1, m2]
        gaps = {1}
        assert "pre_workout" in activity_context(
            m0, 0, day, None, {}, workout_after_meal_indices=gaps
        )
        assert "post_workout" in activity_context(
            m1, 1, day, None, {}, workout_after_meal_indices=gaps
        )
        ctx2 = activity_context(m2, 2, day, None, {}, workout_after_meal_indices=gaps)
        assert "pre_workout" not in ctx2
        assert "post_workout" not in ctx2
        assert "sedentary" in ctx2

    def test_legacy_activity_schedule_ignored_when_explicit_set(self):
        """Explicit gaps disable legacy workout_start/end inference."""
        m0 = PlanMeal("18:00", 2, "dinner")
        day = [m0]
        ctx = activity_context(
            m0,
            0,
            day,
            None,
            {"workout_start": "18:00", "workout_end": "19:00"},
            workout_after_meal_indices=set(),
        )
        assert "pre_workout" not in ctx
        assert "post_workout" not in ctx


class TestActivityContextForProfile:
    def test_explicit_gaps_from_convert_profile(self):
        day = DaySchedule(
            day_index=1,
            meals=[
                CanonMeal(index=1, busyness_level=1, tags=["breakfast"]),
                CanonMeal(index=2, busyness_level=4, tags=["dinner"]),
            ],
            workouts=[WorkoutSlot(after_meal_index=1, type="general", intensity=None)],
        )
        up = UserProfile(
            daily_calories=2000,
            daily_protein_g=120.0,
            daily_fat_g=(50.0, 90.0),
            daily_carbs_g=180.0,
            schedule={"07:00": 1, "18:00": 4},
            liked_foods=[],
            disliked_foods=[],
            allergies=[],
            schedule_days=[day],
        )
        p = convert_profile(up, days=1)
        assert p.workout_after_meal_indices_by_day == [[1]]
        assert p.schedule[0][0].busyness_level == 1
        assert p.schedule[0][1].busyness_level == 4

        g = explicit_workout_gaps_for_day(p, 0)
        assert g == {1}
        ctx0 = activity_context_for_profile(p, 0, p.schedule[0][0], 0, p.schedule[0], None)
        assert "pre_workout" in ctx0
        ctx1 = activity_context_for_profile(p, 0, p.schedule[0][1], 1, p.schedule[0], None)
        assert "post_workout" in ctx1

    def test_legacy_profile_has_no_explicit_gaps(self):
        up = UserProfile(
            daily_calories=2000,
            daily_protein_g=120.0,
            daily_fat_g=(50.0, 90.0),
            daily_carbs_g=180.0,
            schedule={"08:00": 3, "18:00": 3},
            liked_foods=[],
            disliked_foods=[],
            allergies=[],
            schedule_days=None,
        )
        p = convert_profile(up, days=1)
        assert p.workout_after_meal_indices_by_day is None
        assert explicit_workout_gaps_for_day(p, 0) is None


class TestOvernightTags:
    def test_first_meal_has_overnight_fast_break(self):
        day_slots = [
            PlanMeal("08:00", 2, "breakfast"),
            PlanMeal("18:00", 3, "dinner"),
        ]
        ctx = activity_context(day_slots[0], 0, day_slots, None, {})
        assert "overnight_fast_break" in ctx
