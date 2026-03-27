"""Canonical schedule contract (API / YAML / planner input).

This module defines the **authoritative** JSON shape for per-day meal and workout
scheduling. It is shared conceptually with ``frontend/lib/models/models.dart``.

Contract summary
----------------

**DaySchedule** — one calendar day in the planning horizon.

- ``day_index``: 1-based index within the request (must align with ``days`` and
  the length of ``schedule_days`` arrays elsewhere).
- ``meals``: ordered meal slots for that day only. **Workouts are never meals.**
- ``workouts``: zero to two workout placements, each tied to a **gap** between
  two meals (see ``WorkoutSlot.after_meal_index``).

**MealSlot**

- ``index``: contiguous 1..N where N = number of meals that day.
- ``busyness_level``: integer in ``[1, 4]`` (cooking-time / complexity band).
- ``tags``: optional labels (e.g. ``breakfast``, ``lunch``); informational.
- ``preferred_time``: optional ``HH:MM`` for temporal hints; optional for the planner.

**WorkoutSlot**

- ``after_meal_index``: workout occurs **after** the meal with this 1-based index
  and **before** the next meal. Requires ``1 <= after_meal_index < len(meals)``.
- ``type``: ``AM`` | ``PM`` | ``general`` (coarse time-of-day / intent).
- ``intensity``: optional ``low`` | ``moderate`` | ``high``.

Invariants (enforced by ``validate_day_schedule``)
--------------------------------------------------

- Meal ``index`` values are exactly ``1, 2, …, N`` with no gaps or duplicates.
- At most **two** workouts per day.
- Each workout references a **valid gap**: ``1 <= after_meal_index < N`` where
  ``N`` is the meal count.
- No duplicate workouts in the **same gap** (same ``after_meal_index``).

Legacy mapping (``HH:MM`` → int) is handled in
``src.models.legacy_schedule_migration``; values ``0`` denote workout times and
must not be interpreted as meals after migration.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MealSlot(BaseModel):
    """One assignable meal slot (not a workout)."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    index: int = Field(..., ge=1, description="1-based meal index within the day.")
    busyness_level: int = Field(
        ...,
        ge=1,
        le=4,
        description="Cooking-time band: 1=snack/quick … 4=flexible/long.",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Optional labels, e.g. breakfast, lunch, dinner, snack.",
    )
    preferred_time: Optional[str] = Field(
        default=None,
        description='Optional "HH:MM" clock hint for that meal.',
    )

    @field_validator("preferred_time")
    @classmethod
    def _hhmm_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        if len(s) == 5 and s[2] == ":" and s[:2].isdigit() and s[3:].isdigit():
            return s
        raise ValueError(f'preferred_time must be "HH:MM", got {v!r}')


class WorkoutSlot(BaseModel):
    """Workout placed in the gap after meal ``after_meal_index``."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    after_meal_index: int = Field(
        ...,
        description="1-based index of the meal immediately before this workout gap.",
    )
    type: Literal["AM", "PM", "general"]
    intensity: Optional[Literal["low", "moderate", "high"]] = None


class DaySchedule(BaseModel):
    """Canonical schedule for a single day: meals + optional workouts."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    day_index: int = Field(..., ge=1, description="1-based day index in the horizon.")
    meals: List[MealSlot] = Field(default_factory=list)
    workouts: List[WorkoutSlot] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_meals_and_workouts(self) -> DaySchedule:
        validate_day_schedule(self)
        return self


def validate_day_schedule(day: DaySchedule) -> None:
    """Validate structural invariants for one day. Raises ``ValueError`` on failure."""

    meals = day.meals
    if not meals:
        raise ValueError("DaySchedule requires at least one meal.")

    n = len(meals)
    indices = [m.index for m in meals]
    expected = list(range(1, n + 1))
    if sorted(indices) != expected:
        raise ValueError(
            f"Meal indices must be contiguous 1..{n}; got {sorted(indices)}"
        )

    if len(day.workouts) > 2:
        raise ValueError("At most 2 workouts per day.")

    seen_gaps: set[int] = set()
    for w in day.workouts:
        if w.after_meal_index < 1 or w.after_meal_index >= n:
            raise ValueError(
                f"Workout after_meal_index must satisfy 1 <= i < {n}; got {w.after_meal_index}"
            )
        if w.after_meal_index in seen_gaps:
            raise ValueError(
                f"Duplicate workout in gap after meal {w.after_meal_index}"
            )
        seen_gaps.add(w.after_meal_index)
