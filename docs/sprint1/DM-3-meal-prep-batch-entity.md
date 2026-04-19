# DM-3 — MealPrepBatch entity + store

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-2

## Summary

Introduce `MealPrepBatch` as a first-class entity with a JSON-backed repository. Supports creating, listing, and deleting batches plus detecting orphans when a recipe is removed.

## Context

The notes identify meal prep as the single biggest usability win (P2). Sprint 1 models it explicitly so the planner can pre-fill slots deterministically instead of inferring from recipe tags alone.

Unblocks: BE-2, BE-5, BE-6, FE-3, FE-7.

## Acceptance criteria

- [ ] New `src/data_layer/meal_prep.py`:
  - `@dataclass BatchAssignment { date: str, slot_id: str, servings: float = 1.0 }`
  - `@dataclass MealPrepBatch { id: str, recipe_id: str, total_servings: int, cook_date: str, assignments: List[BatchAssignment], status: Literal["planned","active","consumed","orphaned"] }`
  - `class MealPrepBatchRepository` with `list_active()`, `get(id)`, `create(batch)`, `delete(id)`, `mark_orphaned_for_recipe(recipe_id)`.
- [ ] Persistence at `data/meal_prep/batches.json` (created if missing).
- [ ] `servings_remaining` helper: `total_servings - sum(a.servings for a in assignments)`.
- [ ] `assignments_for(date: str)` returns the list of assignments matching an ISO date.
- [ ] Deleting a recipe triggers `mark_orphaned_for_recipe`; orphaned batches keep their assignments but transition to `orphaned` status.
- [ ] Tests in `tests/data_layer/test_meal_prep.py`:
  - Round-trip save/load.
  - `servings_remaining` math.
  - `assignments_for` filtering.
  - Orphan transition on recipe delete.

## Implementation notes

- Use `uuid4().hex` for `id`.
- `cook_date` and `BatchAssignment.date` are ISO strings (`YYYY-MM-DD`), matching `DailyMealPlan.date`.
- `status` state machine (simple): `planned` → `active` (once `cook_date <= today`) → `consumed` (once `servings_remaining == 0`). Transitions computed on read; don't store stale state.
- Validate on create: `total_servings >= 2`, `len(assignments) <= total_servings`, no two assignments share the same `(date, slot_id)`.

## Out of scope

- Planner integration (BE-2).
- HTTP endpoints (BE-5).
- UI (FE-3, FE-7).
- Fractional serving splits across multiple assignments (Week 2+).
