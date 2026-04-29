# BE-10 — Pin assignment API contract

**Status:** implemented  ·  **Complexity:** M  ·  **Depends on:** BE-9

## Summary

Expose a public pin assignment contract that persists slot-level recipe pins and hydrates them into planner `pinned_assignments`.

## Context

Planner already supports internal `pinned_assignments`, but frontend work is blocked because no stable API/persistence contract exists to create, read, update, and clear pins.

Unblocks: FE-10, BE-15.

## Acceptance criteria

- API supports pin create/read/update/clear using canonical `(day_index, slot_index)` plus `recipe_id`.
- Pins persist in the profile or profile-adjacent canonical store (no planner-only shadow storage).
- `/api/v1/plan` hydration path includes persisted pins in `PlanningUserProfile.pinned_assignments`.
- Clearing pins removes their effect from subsequent plans.
- Unknown `recipe_id` returns structured `RECIPE_NOT_FOUND`.
- Conflict precedence remains unchanged: batch lock > pin > required tags > planner search.

## Implementation notes

- Reuse existing planner pin model and validation path; avoid duplicate pin abstractions.
- Keep payload additive and deterministic.
- Keep slot addressing canonical; do not introduce frontend-specific slot identifiers.

## Out of scope

- Frontend pin interaction UX.
- Pin recurrence semantics.
- Planner precedence redesign.
