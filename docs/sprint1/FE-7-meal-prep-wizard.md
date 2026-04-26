# FE-7 — Meal-prep creation wizard

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** BE-5, FE-3

## Summary

A 4-step modal for creating a `MealPrepBatch`: pick recipe → pick servings + cook date → pick slots → confirm.

## Context

Entry points: Meal Prep Tray "+ New batch" (FE-3) and Recipe card "Start a batch" CTA. This is the single happy path for feature F2.

## Acceptance criteria

- [ ] Wizard is reachable from both entry points: `MealPrepTray` "+ New batch" and recipe card "Start a batch".
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
- [ ] Confirmation copy explicitly states that selected slots are exact forced allocations, not soft preferences.
- [ ] Widget tests for step navigation, overflow guard, conflict rehighlight.

## Implementation notes

- Steps can be a PageView inside a Dialog or a full-screen route on mobile-web.
- Keep server calls to step 4 only; earlier steps are local state.
- Reuse slot metadata from the `PlannerState` provider (don't re-fetch).

## Out of scope

- Editing an existing batch (delete + recreate for Sprint 1).
- Partial-serving assignments.

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `frontend/lib/screens/planner_config_screen.dart` — `PlannerConfigScreen`; slot metadata (days × slots) is already rendered here; reuse the same `PlannerState`/`MealPlanProvider` data source for Step 3's mini-week grid — do not re-fetch
- `frontend/lib/services/api_service.dart` — add `createMealPrepBatch(body)` (`POST /api/v1/meal_prep_batches`) here; do not make HTTP calls from inside the wizard steps
- FE-3's `MealPrepTray` — "+ New batch" CTA in the tray opens this wizard; confirm the navigation/callback pattern
- `frontend/lib/models/recipe.dart` — `Recipe_frontend`; Step 1 filters by `is_meal_prep_capable`; confirm this field exists on the Flutter model (DM-2 backend output — may need adding to Flutter model)

**Backend dependency:** `POST /api/v1/meal_prep_batches` (BE-5) must exist before the wizard can complete.

**Do NOT create:**
- Server calls in Steps 1–3 — all local state; only Step 4 calls the server
- An editing flow for existing batches (delete + recreate)

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `frontend/lib/screens/planner_config_screen.dart`.** Identify how slot metadata (days, slot ids, occupied status) is read — Step 3 reuses this source.
2. **Read `frontend/lib/services/api_service.dart`.** Note the pattern for POST calls; add `createMealPrepBatch()` following the same pattern.
3. **Read `frontend/lib/models/recipe.dart`.** Check whether `is_meal_prep_capable` and `default_servings` fields are present — if absent, they must be added here (aligned with DM-2's backend changes).
4. **Read FE-3's `MealPrepTray` opening mechanism** to confirm the navigation pattern (push route vs. show dialog vs. callback).
5. State the step navigation approach (PageView inside Dialog vs. full-screen route) and the local state shape (`WizardState`) before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] Step 1 filters recipe list to `is_meal_prep_capable == true`; shows hint for non-capable recipes
- [ ] Step 2 servings stepper enforces min 2, max 14; date picker defaults to today
- [ ] Step 3 mini-week grid reuses slot data from `PlannerState`/`MealPlanProvider` — no new fetch; already-occupied slots are disabled with tooltip
- [ ] Selecting more slots than servings → overflow selections are disabled
- [ ] Step 4 summary shows recipe, cook date, N servings, K slots, leftovers, estimated nutrition; "Create batch" triggers `POST /api/v1/meal_prep_batches` only at this step
- [ ] On success: modal closes; planner + tray refresh; toast "Batch created"
- [ ] On `BATCH_CONFLICT`: Step 3 re-highlights conflicting cells with red border; user can re-pick
- [ ] No server calls in Steps 1–3
- [ ] Widget tests pass: step navigation, overflow guard, conflict re-highlight
