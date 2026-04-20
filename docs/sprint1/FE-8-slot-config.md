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

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `frontend/lib/screens/profile_screen.dart` — `ProfileScreen`; the new "Week Template" tab/section is added here — do not create a new screen
- `frontend/lib/models/user_profile.dart` — `UserProfile_frontend`; confirm whether `schedule_days` or equivalent `DaySchedule` list field exists; add if missing
- `frontend/lib/models/models.dart` — `DaySchedule`, `MealSlot`, `WorkoutSlot`; the editors bind to these models; `WorkoutSlot` fields are `after_meal_index`, `type`, `intensity` — do not add `busyness_level=0` meal slots
- `frontend/lib/widgets/tags/tag_chip_picker.dart` (FE-5 output) — `TagChipPicker` is reused for `required_tag_slugs` and `preferred_tag_slugs` pickers; import, do not reimplement
- `frontend/lib/services/api_service.dart` — add profile-write method if the profile save endpoint exists; check `src/api/server.py` for a profile write route before creating a new one

**Do NOT create:**
- A new screen separate from `ProfileScreen`
- A `busyness_level=0` meal slot — workouts use `WorkoutSlot`
- Reimplementation of `TagChipPicker`

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `frontend/lib/screens/profile_screen.dart` in full.** Map existing sections/tabs. Identify where the "Week Template" tab is inserted.
2. **Read `frontend/lib/models/user_profile.dart` and `frontend/lib/models/models.dart`.** Confirm `DaySchedule`, `MealSlot`, `WorkoutSlot` fields on the Flutter side. Note whether `schedule_days: List<DaySchedule>` is on `UserProfile_frontend`.
3. **Check `src/api/server.py` for a profile write/update endpoint.** If absent, note that FE-8 needs a new endpoint (or confirm it will be added as part of this task).
4. **Confirm FE-5's `TagChipPicker` is importable** and note its constructor interface for `required_tag_slugs` / `preferred_tag_slugs` pickers.
5. **Read `src/models/legacy_schedule_migration.py` (DM-4 output)** to understand the legacy `schedule: Dict[str, int]` migration prompt that shows on first load.
6. State the tab structure, the `MealSlot` row widget fields, and the profile save endpoint before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] "Week Template" section is a new tab/section inside `ProfileScreen` — not a separate screen
- [ ] Day-type selector (Workout / Golf / Rest / + Add) renders; each day type has an ordered list of `MealSlot` rows
- [ ] Per `MealSlot` row: drag handle (reorder), `preferred_time`, `busyness_level` dropdown 1–4, `required_tag_slugs` + `preferred_tag_slugs` chip pickers (FE-5), delete button
- [ ] Workout slots are `WorkoutSlot` rows with `after_meal_index`, `type`, `intensity` — not `busyness_level=0` meal slots
- [ ] 7-day pattern editor maps each day (Mon–Sun) to a day type
- [ ] Legacy `schedule: Dict[str, int]` profiles trigger a one-time migration prompt on first load
- [ ] Can't delete a slot referenced by an active batch — inline error shown
- [ ] Unknown required tag slug → inline warning with "Create tag" shortcut (FE-5 inline creator)
- [ ] Save persists via profile-write API call through `api_service.dart`
- [ ] Widget tests pass: add/delete slot, reorder, tag selection, validation
