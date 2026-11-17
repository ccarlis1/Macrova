# BE-14 — Planner meal metadata output

**Status:** implemented  ·  **Complexity:** S  ·  **Depends on:** BE-2, BE-8, BE-10, BE-13

## Summary

Add optional planned-meal metadata fields so API consumers can distinguish planner-selected, batch-locked, and pinned meals.

## Context

Planner currently merges locks internally but does not expose source metadata in output. Frontend cannot safely render batch/pin semantics without these fields.

Unblocks: FE-1, FE-3, FE-9, BE-15.

## Acceptance criteria

- Planned meal output includes optional `slot_index`, `source`, `batch_id`, `servings`.
- `source` enum is stable: `planner`, `meal_prep_batch`, `pinned_assignment`.
- Batch-origin meals include `batch_id` and serving count.
- Pin-origin meals include `source: pinned_assignment` and do not masquerade as batch meals.
- Existing clients remain compatible when ignoring new optional fields.

## Implementation notes

- Extend existing `Meal`/API DTO shape additively; no breaking renames.
- Attach metadata after planner resolution, not by bypassing planner phases.
- Preserve BE-3 vs BE-8 boundaries (pool filtering vs slot-level evaluation).

## Out of scope

- UI badge rendering.
- Historical audit trails.
- New planner scoring/optimization logic.
