"""Day and meal numbering at the MCP boundary.

MCP tools number days and meals from 1 ("day 2, meal 3"). The planner and the API
use 0-based ``day_index`` / ``slot_index`` for pins, batch assignments, failures,
FM-3 ``pinned_slots`` and ``recipe_gap.slots``. Every conversion between the two
happens in this module; nothing else in the MCP layer adds or subtracts 1.

The schedule needs no conversion: ``DaySchedule.day_index``, ``MealSlot.index``
and ``WorkoutSlot.after_meal_index`` are already 1-based.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from src.api.failure_explanations import day_number
from src.data_layer.meal_prep import BatchAssignment, MealPrepBatch
from src.data_layer.models import ProfilePin

# 1-based ``{"day": d, "meal": m}``; either may be None for day- or plan-level failures.
Where = Dict[str, Optional[int]]


class SlotNumberError(ValueError):
    """A day or meal number that doesn't exist in the plan. The MCP layer reports it as an input error."""


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SlotNumberError(f"{field} must be a whole number from 1; got {value!r}")
    return value


def to_slot(
    day: Any,
    meal: Any,
    meal_counts: Optional[Sequence[int]] = None,
) -> Tuple[int, int]:
    """1-based ``(day, meal)`` -> 0-based ``(day_index, slot_index)``.

    ``meal_counts[i]`` is the number of meals on day ``i + 1``. When given, a day
    or meal outside the schedule raises :class:`SlotNumberError`.
    """
    day = _positive_int(day, "day")
    meal = _positive_int(meal, "meal")
    if meal_counts is not None:
        if day > len(meal_counts):
            raise SlotNumberError(f"day {day} is outside the {len(meal_counts)}-day plan")
        if meal > meal_counts[day - 1]:
            raise SlotNumberError(
                f"day {day} has {meal_counts[day - 1]} meals; there is no meal {meal}"
            )
    return day - 1, meal - 1


def from_slot(day_index: Optional[int], slot_index: Optional[int]) -> Where:
    """0-based ``(day_index, slot_index)`` -> 1-based ``{"day", "meal"}``. None stays None."""
    return {
        "day": None if day_index is None else day_index + 1,
        "meal": None if slot_index is None else slot_index + 1,
    }


# --- Inputs -----------------------------------------------------------------


def pins_from_mcp(
    pins: Sequence[Mapping[str, Any]],
    meal_counts: Optional[Sequence[int]] = None,
) -> List[ProfilePin]:
    """MCP ``pins`` (``{day, meal, recipe_id}``) -> ``ProfilePin``s."""
    out: List[ProfilePin] = []
    for pin in pins:
        day_index, slot_index = to_slot(pin["day"], pin["meal"], meal_counts)
        out.append(ProfilePin(day_index=day_index, slot_index=slot_index, recipe_id=str(pin["recipe_id"])))
    return out


def pins_to_mcp(pins: Sequence[ProfilePin]) -> List[Dict[str, Any]]:
    return [{**from_slot(p.day_index, p.slot_index), "recipe_id": p.recipe_id} for p in pins]


def batches_from_mcp(
    meal_prep: Sequence[Mapping[str, Any]],
    meal_counts: Optional[Sequence[int]] = None,
) -> List[MealPrepBatch]:
    """MCP ``meal_prep`` entries -> active ``MealPrepBatch``es.

    MCP batches have no id or cook date, so ids are ``meal-prep-1``, ``meal-prep-2``…
    in input order and the cook date is left empty (planning doesn't read it).
    """
    out: List[MealPrepBatch] = []
    for n, entry in enumerate(meal_prep, start=1):
        assignments = []
        for a in entry.get("assignments") or []:
            day_index, slot_index = to_slot(a["day"], a["meal"], meal_counts)
            assignments.append(
                BatchAssignment(day_index=day_index, slot_index=slot_index, servings=float(a.get("servings", 1.0)))
            )
        out.append(
            MealPrepBatch(
                id=f"meal-prep-{n}",
                recipe_id=str(entry["recipe_id"]),
                total_servings=int(entry["total_servings"]),
                cook_date="",
                assignments=assignments,
                status="active",
            )
        )
    return out


def batches_to_mcp(batches: Sequence[MealPrepBatch]) -> List[Dict[str, Any]]:
    return [
        {
            "recipe_id": b.recipe_id,
            "total_servings": b.total_servings,
            "assignments": [
                {**from_slot(a.day_index, a.slot_index), "servings": a.servings} for a in b.assignments
            ],
        }
        for b in batches
    ]


# --- Outputs ----------------------------------------------------------------


def meal_number(planned_meal: Mapping[str, Any]) -> Optional[int]:
    """1-based meal number of a ``daily_plans[].meals[]`` row (its ``slot_index`` is 0-based)."""
    return from_slot(None, planned_meal.get("slot_index"))["meal"]


def failure_where(failure: Mapping[str, Any]) -> Where:
    """1-based ``{"day", "meal"}`` of a normalized API failure.

    Uses ``day_index``, or the ``day-N`` date when only that is set (FM-MACRO-INFEASIBLE).
    """
    return {"day": day_number(dict(failure)), "meal": from_slot(None, failure.get("slot_index"))["meal"]}


def fm3_pinned_slots(failure: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """FM-3 ``details.pinned_slots`` rows with 1-based ``day`` and ``meal``.

    Rows carry only ``slot_index``; the day comes from the failure itself.
    """
    day = failure_where(failure)["day"]
    out: List[Dict[str, Any]] = []
    for row in (failure.get("details") or {}).get("pinned_slots") or []:
        converted = {k: v for k, v in row.items() if k != "slot_index"}
        converted.update(day=day, meal=from_slot(None, row.get("slot_index"))["meal"])
        out.append(converted)
    return out


def recipe_gap_slots(slots: Sequence[Sequence[int]]) -> List[Where]:
    """``report.failure_cause.recipe_gap.slots`` (0-based ``[day_index, slot_index]``) -> 1-based."""
    return [from_slot(d, s) for d, s in slots]
