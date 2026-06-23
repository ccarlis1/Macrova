# BE-5 — Meal-prep endpoints

**Status:** implemented  ·  **Complexity:** M  ·  **Depends on:** DM-3, BE-2

## Summary

CRUD HTTP endpoints for `MealPrepBatch`, plus an orphan-cleanup hook triggered by recipe deletion.

## Context

Flutter needs a stable API to create, list, and delete batches; the planner reads the same store via BE-2. This task exposes the DM-3 repository over HTTP.

Unblocks: FE-3, FE-7.

## Acceptance criteria

- New router `src/api/meal_prep_routes.py`:
  - `POST /api/v1/meal_prep_batches` → body: `{recipe_id, total_servings, cook_date, assignments: [{date, slot_id}]}`. Returns created batch.
  - `GET /api/v1/meal_prep_batches?active=true` → lists non-`consumed`, non-`orphaned` batches.
  - `GET /api/v1/meal_prep_batches/{id}` → detail.
  - `DELETE /api/v1/meal_prep_batches/{id}` → soft-cancels (status → `consumed` if partial, or hard-removes if zero assignments consumed).
- Create validates:
  - `recipe_id` exists and recipe is `is_meal_prep_capable`.
  - `len(assignments) <= total_servings`, and `total_servings >= 2`.
  - No duplicate `(date, slot_id)` within the batch.
  - No `(date, slot_id)` conflict against an existing active batch → 409 `BATCH_CONFLICT`.
- On `DELETE /api/v1/recipes/{id}`, call `MealPrepBatchRepository.mark_orphaned_for_recipe(id)`; affected batches surface in `GET ... ?active=true` with status `orphaned`.
- Error taxonomy via `src/api/error_mapping.py`: `RECIPE_NOT_FOUND`, `RECIPE_NOT_BATCHABLE`, `BATCH_CONFLICT`, `BATCH_INVALID`.
- OpenAPI regenerated.
- Integration tests cover the happy path, each validation failure, and the orphan hook.

## Implementation notes

- Wire this alongside existing `src/api/recipe_sync.py`; reuse its error-mapping pattern.
- Do not build client code here — Flutter consumes these endpoints in FE-3/FE-7.
- Pay attention to timezone: `cook_date` and assignment dates are plain ISO dates (no time); treat everything in the user's local day.

## Out of scope

- Updating an existing batch's assignments (delete + recreate for Sprint 1).
- Serving splits (one assignment = one serving).

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**

- `src/api/server.py` — FastAPI app instance and `include_router` pattern; find where to mount the new `meal_prep_routes` router; confirm the existing `DELETE /api/v1/recipes/{id}` route so the orphan hook can be wired in
- `src/api/recipe_sync.py` — error-mapping and response pattern to replicate
- `src/api/error_mapping.py` — add `RECIPE_NOT_FOUND`, `RECIPE_NOT_BATCHABLE`, `BATCH_CONFLICT`, `BATCH_INVALID` here; do not define them inline in `meal_prep_routes.py`
- `src/data_layer/meal_prep.py` — `MealPrepBatchRepository` (DM-3 output); `create()`, `list_active()`, `get()`, `delete()`, `mark_orphaned_for_recipe()` must already exist

**Architecture confirmation:** `src/api/meal_prep_routes.py` is confirmed MISSING from the repo snapshot — this task creates it.

**Entities to reuse:**

- `MealPrepBatchRepository` from `src/data_layer/meal_prep.py` (DM-3) — the router is HTTP glue only; all persistence goes through the repository
- Error-mapping pattern from `src/api/recipe_sync.py`

**Do NOT create:**

- Direct file I/O in `meal_prep_routes.py`
- Flutter/frontend client code (FE-3, FE-7 consume these endpoints)

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/api/server.py`.** Find the `include_router` calls and the exact prefix pattern. Locate the `DELETE /api/v1/recipes/{id}` handler — this is where `mark_orphaned_for_recipe` is wired.
2. **Read `src/api/recipe_sync.py`.** Note the exact error-response structure (status code + body shape) to replicate in `meal_prep_routes.py`.
3. **Read `src/api/error_mapping.py`.** Check which of `RECIPE_NOT_FOUND`, `RECIPE_NOT_BATCHABLE`, `BATCH_CONFLICT`, `BATCH_INVALID` already exist; add only the missing ones.
4. **Read `src/data_layer/meal_prep.py` (DM-3 output).** Confirm `MealPrepBatchRepository` method signatures for all five operations.
5. **Confirm `is_meal_prep_capable` derivation** from DM-2 — `create` validation calls this on the recipe.
6. State the full router prefix and each endpoint path before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- `src/api/meal_prep_routes.py` is created and mounted on `/api/v1` in `server.py`
- All four endpoints exist: `POST /api/v1/meal_prep_batches`, `GET /api/v1/meal_prep_batches`, `GET /api/v1/meal_prep_batches/{id}`, `DELETE /api/v1/meal_prep_batches/{id}`
- `POST` validates: `recipe_id` exists and is `is_meal_prep_capable`; `total_servings >= 2`; `len(assignments) <= total_servings`; no duplicate `(date, slot_id)`; no conflict with existing active batch → 409 `BATCH_CONFLICT`
- `DELETE /api/v1/recipes/{id}` calls `MealPrepBatchRepository.mark_orphaned_for_recipe(id)` — hook is wired
- All four error codes exist in `src/api/error_mapping.py`
- OpenAPI spec regenerated
- Integration tests cover: happy path, each validation failure, orphan hook

