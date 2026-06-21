# BE-13 — Meal prep API contract stabilization

**Status:** implemented  ·  **Complexity:** M  ·  **Depends on:** DM-3, BE-5, BE-11

## Summary

Stabilize meal-prep batch request/response contract with explicit inventory and assignment metadata needed by frontend flows.

## Context

Meal-prep CRUD exists, but frontend remains blocked because responses omit key inventory fields and batchability depends on recipe fields that were not reliably round-tripped.

Unblocks: FE-3, FE-7, BE-15.

## Acceptance criteria

- `POST /api/v1/meal_prep_batches` validates `recipe_id`, `total_servings`, `cook_date`, and explicit assignments.
- Batch responses include `id`, `recipe_id`, `total_servings`, assigned servings, remaining servings, `cook_date`, `assignments`, and `status`.
- Assignment servings cannot exceed `total_servings`.
- Batch creation enforces recipe meal-prep capability from BE-11 contract fields.
- Missing/deleted recipe behavior is stable and aligned with orphan/not-found batch semantics.

## Implementation notes

- Reuse `MealPrepBatch` as the only assignment ownership primitive.
- Keep inventory math server-side and deterministic.
- Persist slot assignments as canonical `(day_index, slot_index)` only.

## Out of scope

- Meal-prep tray UI rendering.
- Automatic leftover assignment.
- Recurring/cross-week inventory design.
