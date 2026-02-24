"""Derived slot attributes. Spec Section 2.1.2.

Pure functions computed at plan time from user profile and schedule.
No constraint or scoring logic. Deterministic.
"""

from typing import FrozenSet, List, Optional, Set

from src.planning.phase0_models import MealSlot


def _time_to_minutes(hhmm: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    parts = hhmm.strip().split(":")
    h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    return h * 60 + m


def _minutes_to_hours(m: int) -> float:
    return m / 60.0


def cooking_time_max(busyness_level: int) -> Optional[int]:
    """Maximum cooking time in minutes for the slot. Spec Section 2.1.2.

    busyness_level 4 has no upper bound (returns None).
    """
    if busyness_level == 1:
        return 5
    if busyness_level == 2:
        return 15
    if busyness_level == 3:
        return 30
    if busyness_level == 4:
        return None
    return 30  # fallback for invalid level


def time_until_next_meal(
    slot: MealSlot,
    slot_index: int,
    day_slots: List[MealSlot],
    next_day_first_slot: Optional[MealSlot],
) -> float:
    """Hours until the next meal slot (same day or next day first slot). Spec Section 2.1.2."""
    slot_min = _time_to_minutes(slot.time)
    if slot_index + 1 < len(day_slots):
        next_slot = day_slots[slot_index + 1]
        next_min = _time_to_minutes(next_slot.time)
        delta = next_min - slot_min
        if delta <= 0:
            delta += 24 * 60  # next day
        return _minutes_to_hours(delta)
    if next_day_first_slot is not None:
        # Last slot of day: time until next day's first slot (overnight)
        next_min = _time_to_minutes(next_day_first_slot.time)
        delta = (24 * 60 - slot_min) + next_min
        return _minutes_to_hours(delta)
    return float("inf")  # no next slot


def activity_context(
    slot: MealSlot,
    slot_index: int,
    day_slots: List[MealSlot],
    next_day_first_slot: Optional[MealSlot],
    activity_schedule: dict,
) -> FrozenSet[str]:
    """Derive activity_context set for the slot. Spec Section 2.1.2.

    Returns a frozenset of zero or more of: pre_workout, post_workout,
    sedentary, overnight_fast_ahead.
    """
    out: Set[str] = set()
    slot_min = _time_to_minutes(slot.time)

    # Workout window: activity_schedule may have "workout_start", "workout_end", or "workout"
    workout_start_min: Optional[int] = None
    workout_end_min: Optional[int] = None
    if activity_schedule:
        ws = activity_schedule.get("workout_start") or activity_schedule.get("workout")
        we = activity_schedule.get("workout_end")
        if ws:
            workout_start_min = _time_to_minutes(ws)
            workout_end_min = _time_to_minutes(we) if we else workout_start_min + 60
        elif we:
            workout_end_min = _time_to_minutes(we)
            workout_start_min = workout_end_min - 60

    if workout_start_min is not None and workout_end_min is not None:
        # pre_workout: a workout begins within 2 hours after this slot's time
        two_hours = 120
        delta_start = (workout_start_min - slot_min + 24 * 60) % (24 * 60)
        if 0 < delta_start <= two_hours:
            out.add("pre_workout")

        # post_workout: a workout ended within 3 hours before this slot's time
        three_hours = 180
        delta_end = (slot_min - workout_end_min + 24 * 60) % (24 * 60)
        if 0 <= delta_end < three_hours:
            out.add("post_workout")

    if "pre_workout" not in out and "post_workout" not in out:
        out.add("sedentary")

    # overnight_fast_ahead: time until next meal > 4h OR (last slot and overnight fast >= 12h)
    hours_until_next = time_until_next_meal(slot, slot_index, day_slots, next_day_first_slot)
    if hours_until_next > 4:
        out.add("overnight_fast_ahead")
    elif next_day_first_slot is not None and slot_index + 1 >= len(day_slots):
        if hours_until_next >= 12:
            out.add("overnight_fast_ahead")

    return frozenset(out)


def is_workout_slot(activity_context_set: FrozenSet[str]) -> bool:
    """True if slot is pre_workout or post_workout. Spec Section 2.1.2."""
    return "pre_workout" in activity_context_set or "post_workout" in activity_context_set


def satiety_requirement(
    time_until_next_meal_hours: float,
    is_last_slot_of_day: bool,
) -> str:
    """One of 'high' or 'moderate'. Spec Section 2.1.2.

    high: time_until_next_meal > 4 hours OR (last slot of day and overnight fast >= 12 hours).
    """
    if time_until_next_meal_hours > 4:
        return "high"
    if is_last_slot_of_day and time_until_next_meal_hours >= 12:
        return "high"
    return "moderate"
