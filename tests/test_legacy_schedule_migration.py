"""Legacy HH:MM schedule dict migration tests."""

import pytest

from src.models.legacy_schedule_migration import (
    canonical_day_to_meal_only_legacy_dict,
    legacy_schedule_dict_to_day_schedule,
    legacy_schedule_dict_to_schedule_days,
    schedule_days_to_meal_only_legacy_dict,
)
from src.models.schedule import DaySchedule, MealSlot, WorkoutSlot


def test_no_workouts_meals_only():
    day, w = legacy_schedule_dict_to_day_schedule(
        {"07:00": 2, "12:00": 3, "18:00": 3},
        day_index=1,
    )
    assert not w
    assert len(day.meals) == 3
    assert not day.workouts
    assert day.meals[0].index == 1


def test_workout_between_meal_2_and_3():
    day, w = legacy_schedule_dict_to_day_schedule(
        {"07:00": 4, "12:00": 4, "14:00": 0, "18:00": 4},
        day_index=1,
    )
    assert len(day.workouts) == 1
    assert day.workouts[0].after_meal_index == 2
    legacy_meals = canonical_day_to_meal_only_legacy_dict(day)
    assert "14:00" not in legacy_meals
    assert set(legacy_meals.values()) <= {1, 2, 3, 4}


def test_replicate_across_days():
    days, w = legacy_schedule_dict_to_schedule_days(
        {"08:00": 2, "18:00": 3},
        days=3,
    )
    assert len(days) == 3
    assert days[0].day_index == 1
    assert days[2].day_index == 3
    assert days[0].meals[0].busyness_level == 2


def test_schedule_days_template_warning_when_days_differ():
    d1 = DaySchedule(
        day_index=1,
        meals=[MealSlot(index=1, busyness_level=2, preferred_time="07:00")],
    )
    d2 = DaySchedule(
        day_index=2,
        meals=[MealSlot(index=1, busyness_level=4, preferred_time="08:00")],
    )
    _, w = schedule_days_to_meal_only_legacy_dict([d1, d2])
    assert w


def test_invalid_legacy_value():
    with pytest.raises(ValueError):
        legacy_schedule_dict_to_day_schedule({"07:00": 99}, day_index=1)


def test_canonical_schedule_days_request_shape():
    """Example JSON shape accepted by POST /api/v1/plan (schedule_days)."""
    raw = {
        "day_index": 1,
        "meals": [
            {"index": 1, "busyness_level": 2, "tags": ["breakfast"], "preferred_time": "07:00"},
            {"index": 2, "busyness_level": 3, "preferred_time": "12:00"},
        ],
        "workouts": [{"after_meal_index": 1, "type": "PM", "intensity": "moderate"}],
    }
    d = DaySchedule.model_validate(raw)
    assert d.workouts[0].type == "PM"
