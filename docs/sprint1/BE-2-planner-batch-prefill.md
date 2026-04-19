# BE-2 — Meal-prep batch locks in planner path

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-3, DM-4

## Summary

Wire **`MealPrepBatch`** assignments as **locked `(day_index, slot_index) → recipe_id`** into the **existing** deterministic planner pipeline (`PlanningUserProfile` / `plan_meals` / `phase7_search`), at the **same addressing scheme** as **`pinned_assignments`**.

## Context

Batches must not pre-fill via a shadow `plan()` helper. Locks integrate with orchestrator + `MealPlanResult` reporting (architecture-aligned).

Unblocks: BE-5, FE-3, FE-7.

## Acceptance criteria

- [ ] Active batches loaded server-side and passed into the planning entrypoint (exact parameter: **REQUIRES_VERIFICATION** against `planner.plan_meals` signature at implementation time).
- [ ] Batch lock **precedence** vs pins vs required tags matches `docs/SPRINT_1.md` §3.5.
- [ ] Two batches targeting same `(day_index, slot_index)` → `FM-BATCH-CONFLICT` in extended `MealPlanResult.report`.
- [ ] Locked slots skipped by free search; nutrition totals include locked meals.
- [ ] Tests: 3-day batch spread; conflict; tag mismatch → warning in report (not hard fail).

## Implementation notes

- Prefer reusing `pinned_assignments` merge semantics internally (implementation detail) **or** a dedicated `batch_locks` dict merged with explicit precedence — document choice in code comment.
- Determinism: sort batch ids and assignments before merge.
- Do **not** name-drop phase files not confirmed in `architecture.json`; hook at **`planner.py` / `phase0_models.py`** level unless repo audit adds phase modules to the snapshot.

## Out of scope

- Creating batches inside planner.
- Auto-placement of batch servings without user-selected slots.
