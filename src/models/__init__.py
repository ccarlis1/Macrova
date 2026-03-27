"""Shared API and domain models (canonical schedule contract, etc.)."""

from src.models.schedule import (
    DaySchedule,
    MealSlot,
    WorkoutSlot,
    validate_day_schedule,
)
from src.models.legacy_schedule_migration import (
    DEPRECATION_MESSAGE_LEGACY_SCHEDULE_DICT,
    canonical_day_to_meal_only_legacy_dict,
    legacy_schedule_dict_to_schedule_days,
    merge_schedule_warnings_into_result,
    schedule_days_to_meal_only_legacy_dict,
)

__all__ = [
    "DaySchedule",
    "MealSlot",
    "WorkoutSlot",
    "validate_day_schedule",
    "DEPRECATION_MESSAGE_LEGACY_SCHEDULE_DICT",
    "canonical_day_to_meal_only_legacy_dict",
    "legacy_schedule_dict_to_schedule_days",
    "merge_schedule_warnings_into_result",
    "schedule_days_to_meal_only_legacy_dict",
]
