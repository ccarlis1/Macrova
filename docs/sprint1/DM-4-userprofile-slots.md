# DM-4 — MealSlot + day_type_schedules in UserProfile

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-1

## Summary

Replace the loose `schedule: Dict[str, int]` with typed `MealSlot`s grouped by day type (`workout | golf | rest | ...`) while preserving `busyness=0` as a workout-only marker. Preserve backwards compatibility with existing YAML profiles.

## Context

Problem P1 is rooted in the current schedule shape: it only encodes time → busyness, not slot intent. Sprint 1 elevates slots to first-class: each slot has `required_tags`, `preferred_tags`, and a `busyness_max`. Day-type templates (workout/golf/rest) then compose into a weekly plan.

Unblocks: BE-3, BE-6, FE-8.

## Acceptance criteria

- [ ] New `src/models/meal_slot.py`:
  - `@dataclass MealSlot { slot_id: str, day_type: str, ordinal: int, required_tags: List[str], preferred_tags: List[str], busyness_max: int }`.
  - `@dataclass WorkoutSlot { slot_id: str, day_type: str, ordinal: int, workout_type: Optional[str], relative_to_meal_index: Optional[int] }`.
- [ ] `UserProfile` gains:
  - `day_type_schedules: Dict[str, List[MealSlot]]` (defaults to `{}`).
  - `week_template: List[str]` (length 7, defaults to 7 × `"default"`).
- [ ] Extended `src/models/legacy_schedule_migration.py`:
  - If `day_type_schedules` is empty and legacy `schedule: Dict[str, int]` is set:
    - Entries with `busyness_level in 1..4` become `MealSlot`s.
    - Entries with `busyness_level == 0` become `WorkoutSlot`s (or `schedule_days.workouts`) and are excluded from meal slots.
- [ ] Example profile YAML under `config/user_profile.yaml.example` extended with a commented `day_type_schedules:` block showing workout/golf/rest for reference.
- [ ] Fixture: `config/fixtures/profile_workout_golf_rest.yaml` materializing the notes' week (workout, workout, golf, rest, workout, workout, rest).
- [ ] Unit tests:
  - Legacy profile load → non-empty `day_type_schedules["default"]`.
  - New profile load → slots match YAML verbatim.
  - Tag slugs on slots are validated against `TagRegistry` with a clear error for unknowns.

## Implementation notes

- `slot_id` is stable, human-readable, namespaced by day type (e.g. `workout.meal_2`). Do not reuse numeric indices across day types.
- Keep the legacy `schedule` attribute on `UserProfile` populated (derive from default template) until all callers are migrated; do not break existing planner code paths in this task.
- Validation of tag slugs belongs here at profile-load time, not in the planner.

## Out of scope

- Planner reading the new slots (BE-3 + BE-6).
- Flutter UI for editing slots (FE-8).
