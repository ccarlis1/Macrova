# DM-4 — Extend canonical `MealSlot` + `DaySchedule`

**Status:** implemented  ·  **Complexity:** M  ·  **Depends on:** DM-1

## Summary

Extend `**src/models/schedule.py::MealSlot`** with optional `**required_tag_slugs**` and `**preferred_tag_slugs**`. Keep `**WorkoutSlot**` exactly as implemented (`after_meal_index`, `type`, `intensity`) — no parallel workout model. Preserve legacy `schedule: Dict[str, int]` migration via `**src/models/legacy_schedule_migration.py**` (`0` → workout gap / `DaySchedule.workouts`, `1..4` → meals).

## Context

Canonical schedule contract is `DaySchedule` + `MealSlot` + `WorkoutSlot` per `schedule.py` and `architecture.json`. Sprint slot intent maps onto these types; `PlanningMealSlot` / converters remain downstream.

Unblocks: BE-3, BE-6, FE-8.

## Acceptance criteria

- `MealSlot` gains optional `required_tag_slugs: Optional[List[str]]`, `preferred_tag_slugs: Optional[List[str]]` (Pydantic `Field` defaults `None`); `extra="forbid"` preserved or extended per project rules.
- `WorkoutSlot` unchanged field set; no `slot_id` / `day_type` / `ordinal` additions required for Sprint 1.
- `legacy_schedule_migration` maps `busyness == 0` to workout placement per existing module contract (see `schedule.py` module docstring).
- Multi-day “templates” (workout / golf / rest) expressed as **distinct `DaySchedule` instances** (e.g. `schedule_days` list or config fixtures), not a parallel `day_type_schedules` map on `UserProfile` **unless** implemented as a thin YAML convenience that still compiles to `List[DaySchedule]`.
- Example / fixture YAML updated so Flutter + CLI load valid `DaySchedule` JSON.
- Unit tests: migration round-trip; unknown tag slug validation at load time (clear error).

## Implementation notes

- Stable slot addressing for UI + batches + pins: `**(day_index, slot_index)`** with `slot_index` aligning to `MealSlot.index` (1-based).
- Validate tag slugs against DM-1 registry at profile load.

## Out of scope

- Planner wiring (BE-3, BE-2).
- Flutter slot editor (FE-8) beyond field binding.

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**

- `src/models/schedule.py` — `MealSlot`, `WorkoutSlot`, `DaySchedule` are implemented here; extend `MealSlot` in-place with the two new optional fields
- `frontend/lib/models/models.dart` — Flutter `DaySchedule` model; must stay in sync with the backend schema for fixture YAML round-trips
- `src/planning/phase0_models.py` — `PlanningUserProfile` has `schedule -> List[List[MealSlot]]`; confirm the `MealSlot` type it references is the same one in `schedule.py`
- `src/api/server.py` — `PlanRequest` has `schedule_days -> Optional[List[DaySchedule]]`; verify no breaking change
- `src/models/legacy_schedule_migration.py` — existing migration module referenced in stub; read its contract before touching it

**Entities to reuse:**

- `MealSlot` and `WorkoutSlot` in `src/models/schedule.py` — extend `MealSlot` with optional fields; `WorkoutSlot` is explicitly unchanged
- `DaySchedule` in both `src/models/schedule.py` and `frontend/lib/models/models.dart`

**Do NOT create:**

- A `PlanningMealSlot` or parallel slot class for Sprint 1
- A `day_type_schedules` map on `UserProfile` — use `List[DaySchedule]` instead
- Planner wiring code (BE-3, BE-2)

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/models/schedule.py` in full.** List every field on `MealSlot` and `WorkoutSlot`. Confirm `extra="forbid"` or equivalent is in use (Pydantic config).
2. **Read `src/planning/phase0_models.py`.** Confirm the `MealSlot` import path — is it importing from `src/models/schedule.py` or defining its own? If it defines its own, both must be extended.
3. **Read `src/models/legacy_schedule_migration.py`.** Confirm its contract with `DaySchedule.workouts` for `busyness=0`.
4. **Read `frontend/lib/models/models.dart`.** Confirm the Flutter `DaySchedule` and `MealSlot` shape so the fixture YAML stays valid.
5. **Verify no existing code reads `MealSlot` fields with positional access** that would break on adding new fields.
6. State the exact field additions to `MealSlot` (names, types, Pydantic `Field` defaults) before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- `MealSlot` in `src/models/schedule.py` has `required_tag_slugs: Optional[List[str]] = None` and `preferred_tag_slugs: Optional[List[str]] = None`; `extra="forbid"` or equivalent is preserved
- `WorkoutSlot` fields are **unchanged** — no new fields added
- `legacy_schedule_migration.py` maps `busyness=0` to a `WorkoutSlot` entry, not a `MealSlot`
- Example/fixture YAML loads without validation errors via the updated models
- Migration round-trip test passes: legacy `schedule: Dict[str, int]` input → valid `DaySchedule` list output
- Unit test for unknown tag slug at profile load raises a clear error (not a silent drop)
- No planner files (`planner.py`, `phase0_models.py` planning code) were modified in this task

