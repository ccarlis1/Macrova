"""Tests for canonical schedule models and validation."""

import pytest
from pydantic import ValidationError

from src.models.schedule import DaySchedule, MealSlot, WorkoutSlot, validate_day_schedule


def test_validate_day_schedule_ok():
    day = DaySchedule(
        day_index=1,
        meals=[
            MealSlot(index=1, busyness_level=2, preferred_time="07:00"),
            MealSlot(index=2, busyness_level=3, preferred_time="12:00"),
        ],
        workouts=[WorkoutSlot(after_meal_index=1, type="general")],
    )
    validate_day_schedule(day)


def test_meal_indices_must_be_contiguous():
    with pytest.raises(ValidationError):
        DaySchedule(
            day_index=1,
            meals=[
                MealSlot(index=1, busyness_level=2),
                MealSlot(index=3, busyness_level=3),
            ],
        )


def test_workout_gap_must_be_valid():
    with pytest.raises(ValidationError):
        DaySchedule(
            day_index=1,
            meals=[
                MealSlot(index=1, busyness_level=2),
                MealSlot(index=2, busyness_level=3),
            ],
            workouts=[WorkoutSlot(after_meal_index=2, type="PM")],
        )


def test_max_two_workouts():
    with pytest.raises(ValidationError):
        DaySchedule(
            day_index=1,
            meals=[
                MealSlot(index=1, busyness_level=2),
                MealSlot(index=2, busyness_level=3),
                MealSlot(index=3, busyness_level=3),
                MealSlot(index=4, busyness_level=3),
            ],
            workouts=[
                WorkoutSlot(after_meal_index=1, type="general"),
                WorkoutSlot(after_meal_index=2, type="general"),
                WorkoutSlot(after_meal_index=3, type="general"),
            ],
        )


def test_duplicate_workout_gap():
    with pytest.raises(ValidationError):
        DaySchedule(
            day_index=1,
            meals=[
                MealSlot(index=1, busyness_level=2),
                MealSlot(index=2, busyness_level=3),
                MealSlot(index=3, busyness_level=3),
            ],
            workouts=[
                WorkoutSlot(after_meal_index=1, type="general"),
                WorkoutSlot(after_meal_index=1, type="PM"),
            ],
        )
