# DM-4 — Extend canonical `MealSlot` + `DaySchedule`

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-1

## Summary

Extend **`src/models/schedule.py::MealSlot`** with optional **`required_tag_slugs`** and **`preferred_tag_slugs`**. Keep **`WorkoutSlot`** exactly as implemented (`after_meal_index`, `type`, `intensity`) — no parallel workout model. Preserve legacy `schedule: Dict[str, int]` migration via **`src/models/legacy_schedule_migration.py`** (`0` → workout gap / `DaySchedule.workouts`, `1..4` → meals).

## Context

Canonical schedule contract is `DaySchedule` + `MealSlot` + `WorkoutSlot` per `schedule.py` and `architecture.json`. Sprint slot intent maps onto these types; `PlanningMealSlot` / converters remain downstream.

Unblocks: BE-3, BE-6, FE-8.

## Acceptance criteria

- [ ] `MealSlot` gains optional `required_tag_slugs: Optional[List[str]]`, `preferred_tag_slugs: Optional[List[str]]` (Pydantic `Field` defaults `None`); `extra="forbid"` preserved or extended per project rules.
- [ ] `WorkoutSlot` unchanged field set; no `slot_id` / `day_type` / `ordinal` additions required for Sprint 1.
- [ ] `legacy_schedule_migration` maps `busyness == 0` to workout placement per existing module contract (see `schedule.py` module docstring).
- [ ] Multi-day “templates” (workout / golf / rest) expressed as **distinct `DaySchedule` instances** (e.g. `schedule_days` list or config fixtures), not a parallel `day_type_schedules` map on `UserProfile` **unless** implemented as a thin YAML convenience that still compiles to `List[DaySchedule]`.
- [ ] Example / fixture YAML updated so Flutter + CLI load valid `DaySchedule` JSON.
- [ ] Unit tests: migration round-trip; unknown tag slug validation at load time (clear error).

## Implementation notes

- Stable slot addressing for UI + batches + pins: **`(day_index, slot_index)`** with `slot_index` aligning to `MealSlot.index` (1-based).
- Validate tag slugs against DM-1 registry at profile load.

## Out of scope

- Planner wiring (BE-3, BE-2).
- Flutter slot editor (FE-8) beyond field binding.
