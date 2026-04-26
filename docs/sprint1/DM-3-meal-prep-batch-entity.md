# DM-3 — MealPrepBatch entity + store

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-2

## Summary

Introduce `MealPrepBatch` as a first-class entity with a JSON-backed repository. Supports creating, listing, and deleting batches plus detecting orphans when a recipe is removed.

## Context

The notes identify meal prep as the single biggest usability win (P2). Sprint 1 models it explicitly so the planner can pre-fill slots deterministically instead of inferring from recipe tags alone.

Unblocks: BE-2, BE-5, BE-6, FE-3, FE-7.

## Acceptance criteria

- [ ] New `src/data_layer/meal_prep.py`:
  - `SlotAddress = Tuple[int, int]  # (day_index, slot_index)`
  - `@dataclass BatchAssignment { day_index: int, slot_index: int, servings: float = 1.0 }`
  - `@dataclass MealPrepBatch { id: str, recipe_id: str, total_servings: int, cook_date: str, assignments: List[BatchAssignment], status: Literal["planned","active","consumed","orphaned"] }`
  - `class MealPrepBatchRepository` with `list_active()`, `get(id)`, `create(batch)`, `delete(id)`, `mark_orphaned_for_recipe(recipe_id)`.
- [ ] Persistence at `data/meal_prep/batches.json` (created if missing).
- [ ] `servings_remaining` helper: `total_servings - sum(a.servings for a in assignments)`.
- [ ] `assignments_for_day(day_index: int)` returns the list of assignments for that planning day index.
- [ ] Assignment invariants: every `assignment.servings > 0`; Sprint 1 default is `1.0` per assignment unless explicitly extended later.
- [ ] Inventory invariant is enforced: `sum(assignment.servings) <= total_servings`; leftovers are explicit and persisted as remaining inventory.
- [ ] Deleting a recipe triggers `mark_orphaned_for_recipe`; orphaned batches keep their assignments but transition to `orphaned` status.
- [ ] Tests in `tests/data_layer/test_meal_prep.py`:
  - Round-trip save/load.
  - `servings_remaining` math.
  - `assignments_for_day` filtering.
  - Multi-day repeated assignment of same recipe via distinct slot addresses.
  - Orphan transition on recipe delete.

## Implementation notes

- Use `uuid4().hex` for `id`.
- `cook_date` remains an ISO string (`YYYY-MM-DD`) for display/audit metadata only.
- Canonical planner/storage addressing uses `SlotAddress = (day_index, slot_index)` across entity, APIs, and planner.
- `status` state machine (simple): `planned` → `active` (once `cook_date <= today`) → `consumed` (once `servings_remaining == 0`). Transitions computed on read; don't store stale state.
- Validate on create: `total_servings >= 2`, `len(assignments) <= total_servings`, no two assignments share the same `(day_index, slot_index)`, `sum(assignment.servings) <= total_servings`.

## Out of scope

- Planner integration (BE-2).
- HTTP endpoints (BE-5).
- UI (FE-3, FE-7).
- Fractional serving splits across multiple assignments (Week 2+).

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/data_layer/models.py` — `Recipe` dataclass (for `recipe_id` FK reference and `is_meal_prep_capable` check); `DailyMealPlan` (for `date` ISO string format: `YYYY-MM-DD`)
- Architecture states `src/data_layer/meal_prep.py` is **MISSING** — this task creates it from scratch

**Entities to reuse:**
- Canonical slot address format from planner assignments in `src/planning/phase0_models.py` — use `(day_index, slot_index)`
- `uuid4().hex` pattern as specified; do not use a different ID scheme

**Do NOT create:**
- HTTP endpoints (BE-5)
- Planner integration code (BE-2)
- Any frontend code

**Persistence path:** `data/meal_prep/batches.json` — create the directory and file on first save if absent.

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/data_layer/models.py` in full.** Confirm the `DailyMealPlan.date` field type/format. Note how other dataclasses in this file are structured (field ordering, JSON serialization pattern).
2. **Check whether `src/data_layer/meal_prep.py` already exists.** Architecture marks it missing — confirm before creating.
3. **Check whether `data/meal_prep/` directory exists.** The repository will need this path created on first save.
4. **Identify the JSON serialization approach** used by other repositories in `src/data_layer/` (e.g., does `RecipeDB` use `dataclasses.asdict`, `pydantic`, or manual dicts?) — follow the same pattern for consistency.
5. State the complete `MealPrepBatch` and `BatchAssignment` field signatures before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `src/data_layer/meal_prep.py` is the only new file created; no changes made to `models.py` or other existing files
- [ ] `MealPrepBatchRepository` creates `data/meal_prep/batches.json` on first `create()` call if the directory and file don't exist
- [ ] Round-trip test: `create()` → process exit → `list_active()` returns the same batch
- [ ] `servings_remaining` returns `total_servings - sum(a.servings for a in assignments)` exactly
- [ ] `assignments_for_day(day_index)` returns only assignments matching that day index
- [ ] `mark_orphaned_for_recipe(recipe_id)` transitions matching batches to `orphaned` without deleting assignments
- [ ] Create validation enforces: `total_servings >= 2`, `len(assignments) <= total_servings`, no duplicate `(day_index, slot_index)` pairs
- [ ] All tests in `tests/data_layer/test_meal_prep.py` pass
