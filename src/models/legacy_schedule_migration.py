"""Legacy ``HH:MM`` → ``busyness`` schedule migration and deprecation helpers.

Legacy format (deprecated)
--------------------------

- Mapping **keys** are ``"HH:MM"`` strings.
- Mapping **values** are integers:

  - ``1``–``4``: meal slot busyness (assignable meal).
  - ``0``: **workout** time (not a meal); must not be planned as food after migration.

Deprecation strategy
--------------------

1. **API**: Clients should send ``schedule_days`` (canonical ``DaySchedule[]``). The
   flat dict remains accepted as ``schedule`` or ``legacy_schedule``; each use
   emits structured warnings (see ``merge_schedule_warnings_into_result``).
2. **YAML**: Prefer a top-level ``schedule_days`` block. The legacy ``schedule``
   map is still loaded, converted to canonical form, and a stderr notice is printed.

Conversion rules (deterministic)
--------------------------------

- Entries with value ``0`` become ``WorkoutSlot`` entries; entries ``1``–``4`` become
  ``MealSlot`` rows ordered by clock time.
- Workout gap: for each workout time ``tw``, find consecutive meal times ``t_a < tw < t_b``;
  ``after_meal_index`` is the 1-based index of meal at ``t_a``.
- Workouts outside any strict gap (before first meal, after last meal, or equal to a
  meal time) are **dropped** with a warning.
- More than two workouts in one template day: keep the first two by time order, warn.
- ``WorkoutSlot.type`` is inferred from ``tw``: before 12:00 → ``AM``, from 17:00 → ``PM``,
  else ``general``.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Literal, MutableMapping, Optional, Sequence, Tuple

from src.models.schedule import DaySchedule, MealSlot, WorkoutSlot, validate_day_schedule

DEPRECATION_MESSAGE_LEGACY_SCHEDULE_DICT = (
    "Legacy flat schedule (HH:MM -> int) is deprecated; "
    "use schedule_days with MealSlot and WorkoutSlot."
)

_DEFAULT_MEAL_CLOCKS: Tuple[str, ...] = (
    "07:00",
    "08:30",
    "12:00",
    "15:00",
    "18:00",
    "19:00",
    "20:00",
    "21:00",
)


def _minutes(hhmm: str) -> int:
    parts = hhmm.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f'Invalid time (expected HH:MM): {hhmm!r}')
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Invalid time: {hhmm!r}")
    return h * 60 + m


def _fmt_minutes(total: int) -> str:
    total = max(0, min(total, 23 * 60 + 59))
    h, m = divmod(total, 60)
    return f"{h:02d}:{m:02d}"


def _infer_workout_type(hhmm: str) -> Literal["AM", "PM", "general"]:
    try:
        mins = _minutes(hhmm)
    except ValueError:
        return "general"
    if mins < 12 * 60:
        return "AM"
    if mins >= 17 * 60:
        return "PM"
    return "general"


def _default_tags_for_position(i: int, n: int) -> List[str]:
    if i == 0 and n >= 3:
        return ["breakfast"]
    if n >= 3 and i == n - 1:
        return ["dinner"]
    if n >= 3 and i == n // 2:
        return ["lunch"]
    return []


def legacy_schedule_dict_to_day_schedule(
    legacy: Dict[str, int],
    *,
    day_index: int = 1,
) -> Tuple[DaySchedule, List[str]]:
    """Convert one legacy day template into a canonical ``DaySchedule``.

    ``legacy`` values must be integers. Meal busyness is ``1``–``4``; ``0`` marks
    workout times. Invalid values produce ``ValueError``.
    """
    warnings: List[str] = []

    entries: List[Tuple[str, int]] = []
    for k, v in legacy.items():
        time_s = str(k).strip()
        try:
            iv = int(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Schedule value for {time_s!r} must be int, got {v!r}") from e
        entries.append((time_s, iv))

    if not entries:
        raise ValueError("Legacy schedule is empty.")

    meals_raw: List[Tuple[str, int]] = []
    workouts_raw: List[str] = []
    for time_s, iv in entries:
        if iv == 0:
            workouts_raw.append(time_s)
        elif 1 <= iv <= 4:
            meals_raw.append((time_s, iv))
        else:
            raise ValueError(
                f"Invalid legacy schedule value {iv} at {time_s!r}; expected 0–4."
            )

    if not meals_raw:
        raise ValueError("Legacy schedule has no meal slots (values 1–4).")

    meals_raw.sort(key=lambda x: _minutes(x[0]))
    n = len(meals_raw)
    meal_slots: List[MealSlot] = []
    for i, (clock, busy) in enumerate(meals_raw):
        tags = _default_tags_for_position(i, n)
        meal_slots.append(
            MealSlot(
                index=i + 1,
                busyness_level=busy,
                tags=tags or None,
                preferred_time=clock,
            )
        )

    meal_times = [m.preferred_time or "12:00" for m in meal_slots]
    gap_workouts: List[Tuple[str, int]] = []

    def _gap_for_workout(tw: str) -> Optional[int]:
        try:
            mw = _minutes(tw)
        except ValueError:
            warnings.append(f"Workout time {tw!r} is invalid; skipped.")
            return None
        for i in range(n - 1):
            t_lo = _minutes(meal_times[i])
            t_hi = _minutes(meal_times[i + 1])
            if t_lo < mw < t_hi:
                return i + 1
        if mw <= _minutes(meal_times[0]):
            warnings.append(
                f"Workout at {tw!r} is not strictly between two meals; skipped."
            )
        elif mw >= _minutes(meal_times[-1]):
            warnings.append(
                f"Workout at {tw!r} is not strictly between two meals; skipped."
            )
        else:
            warnings.append(
                f"Workout at {tw!r} coincides with a meal boundary; skipped."
            )
        return None

    for tw in sorted(workouts_raw, key=lambda x: _minutes(x)):
        gap = _gap_for_workout(tw)
        if gap is not None:
            gap_workouts.append((tw, gap))

    deduped: Dict[int, str] = {}
    for tw, gap in gap_workouts:
        if gap in deduped:
            warnings.append(
                f"Duplicate workout in gap after meal {gap}; ignoring {tw!r}."
            )
            continue
        deduped[gap] = tw

    sorted_gaps = sorted(deduped.items(), key=lambda kv: kv[0])
    if len(sorted_gaps) > 2:
        warnings.append(
            f"More than 2 workouts in one day; keeping first 2 of {len(sorted_gaps)}."
        )
        sorted_gaps = sorted_gaps[:2]

    wslots: List[WorkoutSlot] = []
    for gap, tw in sorted_gaps:
        wslots.append(
            WorkoutSlot(
                after_meal_index=gap,
                type=_infer_workout_type(tw),
                intensity=None,
            )
        )

    day = DaySchedule(day_index=day_index, meals=meal_slots, workouts=wslots)
    validate_day_schedule(day)
    return day, warnings


def legacy_schedule_dict_to_schedule_days(
    legacy: Dict[str, int],
    *,
    days: int,
) -> Tuple[List[DaySchedule], List[str]]:
    """Replicate one legacy template across ``days`` (same canonical day each time)."""
    if days < 1 or days > 7:
        raise ValueError(f"days must be in [1, 7], got {days}")

    out: List[DaySchedule] = []
    all_warnings: List[str] = []
    for d in range(1, days + 1):
        day, w = legacy_schedule_dict_to_day_schedule(legacy, day_index=d)
        out.append(day)
        all_warnings.extend(w)

    return out, all_warnings


def schedule_days_to_meal_only_legacy_dict(
    schedule_days: List[DaySchedule],
) -> Tuple[Dict[str, int], List[str]]:
    """Pick a single legacy meal dict for ``UserProfile.schedule`` (day 1 template).

    If later days differ from day 1, emit one warning; the planner still uses one
    template until full per-day integration.
    """
    if not schedule_days:
        raise ValueError("schedule_days is empty.")
    warnings: List[str] = []
    first = canonical_day_to_meal_only_legacy_dict(schedule_days[0])
    for d in schedule_days[1:]:
        if canonical_day_to_meal_only_legacy_dict(d) != first:
            warnings.append(
                "schedule_days differ across days; planner currently uses day 1 meal template only."
            )
            break
    return first, warnings


def canonical_day_to_meal_only_legacy_dict(day: DaySchedule) -> Dict[str, int]:
    """Build legacy-style dict **only** from meals (values 1–4), for old planner paths.

    Workouts are omitted; times come from ``preferred_time`` or defaults.
    """
    out: Dict[str, int] = {}
    for i, m in enumerate(day.meals):
        clock = m.preferred_time
        if not clock:
            clock = _DEFAULT_MEAL_CLOCKS[i] if i < len(_DEFAULT_MEAL_CLOCKS) else "12:00"
        out[clock] = m.busyness_level
    return out


def merge_schedule_warnings_into_result(
    result: MutableMapping[str, Any],
    messages: Sequence[str],
    *,
    deprecated_legacy: bool = False,
) -> None:
    """Merge migration / deprecation messages into a plan JSON ``warnings`` object (in place)."""
    if not messages and not deprecated_legacy:
        return
    w = result.get("warnings")
    if not isinstance(w, dict):
        w = {}
    block: Dict[str, Any] = {}
    if deprecated_legacy:
        block["deprecated"] = True
        block["message"] = DEPRECATION_MESSAGE_LEGACY_SCHEDULE_DICT
    if messages:
        block["messages"] = list(messages)
    if block:
        w["schedule_migration"] = block
        result["warnings"] = w


def log_legacy_schedule_deprecation(source: str) -> None:
    """Emit a single stderr line for CLI/YAML migration visibility."""
    print(
        f"Warning ({source}): {DEPRECATION_MESSAGE_LEGACY_SCHEDULE_DICT}",
        file=sys.stderr,
    )
