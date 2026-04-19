# FE-7 — Meal-prep creation wizard

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** BE-5, FE-3

## Summary

A 4-step modal for creating a `MealPrepBatch`: pick recipe → pick servings + cook date → pick slots → confirm.

## Context

Entry points: Meal Prep Tray "+ New batch" (FE-3) and Recipe card "Start a batch" CTA. This is the single happy path for feature F2.

## Acceptance criteria

- [ ] Step 1 — Pick recipe:
  - Searchable list, filtered to `is_meal_prep_capable == true`.
  - Shows a hint: "Only meal-prep capable recipes appear here. Edit a recipe to enable."
- [ ] Step 2 — Servings + cook date:
  - Servings stepper (min 2, max 14).
  - Date picker defaulting to today.
- [ ] Step 3 — Pick slots:
  - Mini-week grid showing days × slots.
  - Slots already occupied by another batch are disabled with a tooltip.
  - Selecting more slots than servings → disable overflow selections.
  - Selecting fewer than servings → allowed; shows "N leftovers will not be auto-planned".
- [ ] Step 4 — Confirm:
  - Summary: recipe, cook date, N servings across K slots, leftovers, estimated total nutrition.
  - "Create batch" button → POST `/api/v1/meal_prep_batches`.
- [ ] On success: modal closes; planner + tray refresh; toast "Batch created".
- [ ] On `BATCH_CONFLICT`: step 3 re-highlights conflicting cells with a red border; user can re-pick.
- [ ] Widget tests for step navigation, overflow guard, conflict rehighlight.

## Implementation notes

- Steps can be a PageView inside a Dialog or a full-screen route on mobile-web.
- Keep server calls to step 4 only; earlier steps are local state.
- Reuse slot metadata from the `PlannerState` provider (don't re-fetch).

## Out of scope

- Editing an existing batch (delete + recreate for Sprint 1).
- Partial-serving assignments.
