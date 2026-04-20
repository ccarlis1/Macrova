# FE-1 — Planner screen card-based rebuild

**Status:** todo  ·  **Complexity:** L  ·  **Depends on:** DM-2, DM-4, BE-3

## Summary

Rebuild the Flutter planner screen as a card-based layout: one column per day, meal cards inside, tag chips visible, no spreadsheet aesthetics.

## Context

Problem P4: the current UI reads like a spreadsheet. This is the most visible Sprint 1 UX change and the foundation for FE-2, FE-3, FE-9.

## Acceptance criteria

- [ ] New widgets under `frontend/lib/widgets/planner/`:
  - `DayColumn` — vertical column, header with date + day type badge.
  - `MealCard` — compact card: recipe name, 2–4 tag chips, servings indicator for batches, swap button.
  - `TagChip` — uses FE-5's reusable chip.
  - `EmptySlotCard` — dashed outline with "Pick a recipe" CTA.
- [ ] Planner screen replaces the grid with a horizontally scrollable row of 7 `DayColumn`s. Week navigation buttons (prev/next) + a "Generate Plan" primary CTA in the header.
- [ ] `MealCard` variants by `source`:
  - `planner` — default.
  - `meal_prep_batch` — accent color, diamond glyph, `(n/N)` serving counter.
  - `user_override` — subtle highlight + "Edited" tag.
- [ ] Tap a `MealCard` opens a bottom sheet (`MealDetailSheet`) with macros, ingredients, instructions, Swap CTA.
- [ ] No fixed-width columns, no row numbers, no "edit cell" affordance. Matches `SPRINT_1.md` §5.2.1.
- [ ] Widget tests:
  - `MealCard` renders correct variant per `source`.
  - Planner with a fixture 7-day plan renders without overflow errors at 1440×900 and at mobile-web 390×844.
- [ ] Manual QA checklist appended to the PR.

## Implementation notes

- Use existing Riverpod providers (per `frontend/lib/`) — do not introduce a second state management library. Follow patterns in `.claude/skills/flutter-tester/SKILL.md`.
- Keep widgets dumb; data comes from a single `PlannerState` provider.
- Colors follow FE-5's tag palette for consistency.
- Do not implement drag-and-drop here — that's FE-2.

## Out of scope

- Drag-and-drop (FE-2).
- Meal Prep Tray panel (FE-3).
- Failure-state banners (FE-9).
- Recipe editing inline.

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `frontend/lib/screens/meal_plan_view_screen.dart` — existing `MealPlanViewScreen`; the card layout replaces its day-by-day render section; do not delete the nutrition summary, micronutrient bars, or warnings
- `frontend/lib/providers/meal_plan_provider.dart` — existing `MealPlanProvider`; widgets must read from this Riverpod provider — do not introduce a second state source
- `frontend/lib/models/models.dart` — `DaySchedule`, `MealSlot` (used to address days and slots)
- `frontend/lib/models/recipe.dart` — `Recipe_frontend` (displayed in `MealCard`)
- `frontend/lib/widgets/app_shell.dart` — `AppShell` context; confirm navigation setup does not conflict

**New directory to create:** `frontend/lib/widgets/planner/` — all new widgets (`DayColumn`, `MealCard`, `TagChip`, `EmptySlotCard`, `MealDetailSheet`) go here.

**Do NOT create:**
- A second state management library alongside Riverpod
- A `PlannerState` provider that duplicates `MealPlanProvider` — use `MealPlanProvider` as the data source, or rename/extend it if a `PlannerState` shape is cleaner (document the decision)
- Drag-and-drop logic (FE-2)
- Meal Prep Tray (FE-3)

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `frontend/lib/screens/meal_plan_view_screen.dart` in full.** Map the current render structure — identify what must be preserved (nutrition totals, micronutrient bars, warnings, calendar toggle placeholder) and what is being replaced (day/meal grid).
2. **Read `frontend/lib/providers/meal_plan_provider.dart`.** Note the exposed state shape — specifically how days and meals are structured so `DayColumn` and `MealCard` can consume them.
3. **Read `frontend/lib/models/models.dart` and `frontend/lib/models/recipe.dart`.** Note `DaySchedule`, `MealSlot`, and `Recipe_frontend` field names used by the new widgets.
4. **Check `frontend/lib/widgets/planner/` directory** — confirm it doesn't exist yet.
5. **Check `.claude/skills/flutter-tester/SKILL.md`** for Riverpod provider testing patterns that apply to widget tests.
6. State which sections of `meal_plan_view_screen.dart` are preserved vs. replaced before writing any widget code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `frontend/lib/widgets/planner/` contains `DayColumn`, `MealCard`, `TagChip`, `EmptySlotCard` — no inline widget definitions in `meal_plan_view_screen.dart`
- [ ] `MealCard` renders three source variants (`planner`, `meal_prep_batch`, `user_override`) with correct visual differentiation
- [ ] Planner screen is a horizontally scrollable row of 7 `DayColumn`s; prev/next week navigation and "Generate Plan" CTA are in the header
- [ ] Tap on `MealCard` opens `MealDetailSheet` with macros, ingredients, instructions, and Swap CTA
- [ ] No fixed-width columns, no row numbers, no "edit cell" affordance
- [ ] Nutrition summary, micronutrient bars, warnings, and calendar toggle placeholder still render (not removed)
- [ ] No second state management library introduced
- [ ] Widget tests pass at 1440×900 and 390×844 without overflow errors
- [ ] Manual QA checklist appended to PR
