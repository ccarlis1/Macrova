# BE-2 — Planner Phase-B pre-fill from batches

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-3, DM-4

## Summary

Teach the planner to consume active meal-prep batches first and treat the resulting slot assignments as locked. Everything else runs afterwards on the remaining slots.

## Context

Without this, meal prep is a UI illusion. The planner has to honor batch assignments as hard constraints so the plan matches what the user actually cooked.

Unblocks: BE-5, FE-3, FE-7.

## Acceptance criteria

- [ ] `PlanRequest` (wherever defined in the planner orchestrator) accepts `active_batches: List[MealPrepBatch]`.
- [ ] New Phase-B step runs before `phase3_feasibility`:
  - For each `(date, slot_id)` pair referenced by any assignment, write a `PlannedMeal(source="meal_prep_batch", batch_id=...)` into the plan state and mark the slot `locked=True`.
- [ ] `phase3_feasibility` and `phase6_candidates` skip locked slots.
- [ ] If two active batches target the same `(date, slot_id)`, planner returns `FM-BATCH-CONFLICT` with both batch ids in the report.
- [ ] Tag validation on locked slots runs and emits a **warning** (not an error) into the plan report when the batched recipe lacks a required tag.
- [ ] Planner tests:
  - Plan with a single batch of 3 servings across 3 different days → identical recipe in those three slots.
  - Two conflicting batches → `FM-BATCH-CONFLICT`.
  - Batch targeting a slot whose required tag the recipe lacks → plan succeeds, report contains a warning.

## Implementation notes

- Introduce a small `PlannerSlotState` with a `locked` flag and a `source` hint; propagate through existing phases rather than duplicating branches.
- Determinism: iterate batches in ascending `id` order, then assignments in `(date, slot_id)` order, so the pre-fill phase is reproducible.
- Do not duplicate nutrition aggregation logic — let the existing `phase10_reporting` code recompute totals including the pre-filled meals.

## Out of scope

- Creating/deleting batches from within the planner (only reads them).
- Auto-scheduling batches when the user requests "plan my week" without specifying slots (Week 2+).
