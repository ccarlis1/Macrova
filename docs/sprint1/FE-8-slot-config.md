# FE-8 — Slot config in Profile

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-4, BE-1, FE-5

## Summary

Profile screen UI for editing **`DaySchedule`** / **`MealSlot`** rows: per-slot `required_tag_slugs`, `preferred_tag_slugs`, and **`busyness_level` (1–4)**; workouts edited as **`WorkoutSlot`** (`after_meal_index`, `type`, `intensity`) — not as `busyness_level = 0` meals.

## Context

Without this, the user cannot express slot intent in the new model — they'd have to hand-edit YAML. This closes the loop from DM-4.

## Acceptance criteria

- [ ] New tab/section "Week Template" in the Profile screen:
  - Day-type selector (Workout / Golf / Rest, plus "+ Add day type").
  - For each selected day type, an ordered list of **`MealSlot`** rows (`index` 1..N).
  - Per meal slot:
    - Drag handle to reorder (updates `index` consistently).
    - Optional `preferred_time` (`HH:MM`).
    - `busyness_level` dropdown **1–4** (maps to recipe `time-*` fit at plan time, not the same as recipe `time-0`).
    - `required_tag_slugs` / `preferred_tag_slugs` chip pickers (FE-5).
    - Delete button.
  - "+ Add slot" at the bottom.
- [ ] "Week pattern" editor: 7 day-type buttons (Mon..Sun), each a dropdown over available day types.
- [ ] Save persists via an API call that writes the profile YAML server-side (new endpoint if needed, or reuse existing profile-write route).
- [ ] Validation:
  - Can't delete a slot that's currently referenced by an active batch assignment; show an inline error pointing to the batch.
  - Required tag slugs that don't resolve → inline warning with "Create tag" shortcut (uses FE-5's inline creator).
- [ ] Widget tests cover add/delete slot, reorder, tag selection, validation.

## Implementation notes

- Back-compat with legacy `schedule: Dict[str, int]` profiles: on first load, show a one-time migration prompt ("Split into workout / golf / rest templates?") that auto-generates the 3 day types from the legacy data.
- Keep the week-pattern editor visually distinct from the slot editor — they answer different questions.

## Out of scope

- Multi-week patterns (Week 2+).
- Macro targets editing (handled elsewhere).
