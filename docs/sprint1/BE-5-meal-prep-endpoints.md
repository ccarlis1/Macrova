# BE-5 — Meal-prep endpoints

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-3, BE-2

## Summary

CRUD HTTP endpoints for `MealPrepBatch`, plus an orphan-cleanup hook triggered by recipe deletion.

## Context

Flutter needs a stable API to create, list, and delete batches; the planner reads the same store via BE-2. This task exposes the DM-3 repository over HTTP.

Unblocks: FE-3, FE-7.

## Acceptance criteria

- [ ] New router `src/api/meal_prep_routes.py`:
  - `POST /api/v1/meal_prep_batches` → body: `{recipe_id, total_servings, cook_date, assignments: [{date, slot_id}]}`. Returns created batch.
  - `GET /api/v1/meal_prep_batches?active=true` → lists non-`consumed`, non-`orphaned` batches.
  - `GET /api/v1/meal_prep_batches/{id}` → detail.
  - `DELETE /api/v1/meal_prep_batches/{id}` → soft-cancels (status → `consumed` if partial, or hard-removes if zero assignments consumed).
- [ ] Create validates:
  - `recipe_id` exists and recipe is `is_meal_prep_capable`.
  - `len(assignments) <= total_servings`, and `total_servings >= 2`.
  - No duplicate `(date, slot_id)` within the batch.
  - No `(date, slot_id)` conflict against an existing active batch → 409 `BATCH_CONFLICT`.
- [ ] On `DELETE /api/v1/recipes/{id}`, call `MealPrepBatchRepository.mark_orphaned_for_recipe(id)`; affected batches surface in `GET ... ?active=true` with status `orphaned`.
- [ ] Error taxonomy via `src/api/error_mapping.py`: `RECIPE_NOT_FOUND`, `RECIPE_NOT_BATCHABLE`, `BATCH_CONFLICT`, `BATCH_INVALID`.
- [ ] OpenAPI regenerated.
- [ ] Integration tests cover the happy path, each validation failure, and the orphan hook.

## Implementation notes

- Wire this alongside existing `src/api/recipe_sync.py`; reuse its error-mapping pattern.
- Do not build client code here — Flutter consumes these endpoints in FE-3/FE-7.
- Pay attention to timezone: `cook_date` and assignment dates are plain ISO dates (no time); treat everything in the user's local day.

## Out of scope

- Updating an existing batch's assignments (delete + recreate for Sprint 1).
- Serving splits (one assignment = one serving).
