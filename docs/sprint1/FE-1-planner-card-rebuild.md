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
