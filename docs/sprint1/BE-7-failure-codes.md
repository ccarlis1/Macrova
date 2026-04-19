# BE-7 — Failure-code surfacing

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** BE-2, BE-3

## Summary

Finalize the error JSON shape for planner failures so Flutter can render actionable recovery surfaces (see FE-9).

## Context

Planner failures today are opaque. Sprint 1 ships three user-actionable modes: `FM-TAG-EMPTY`, `FM-BATCH-CONFLICT`, `FM-MACRO-INFEASIBLE`. Each needs enough context in the response for the UI to render a one-line fix.

Unblocks: FE-9.

## Acceptance criteria

- [ ] Planner `report` includes a `failures: List[Failure]` list even on success (empty list). Each `Failure`:
  ```json
  {
    "code": "FM-TAG-EMPTY",
    "slot_id": "workout.meal_3",
    "date": "2026-04-20",
    "details": { "missing_tag": "pre-workout", "recipe_count": 0 },
    "fix_hint": "No recipes match tag `pre-workout`. Add one or relax constraints."
  }
  ```
- [ ] `FM-BATCH-CONFLICT` details: `{batch_ids: [..], date, slot_id}`.
- [ ] `FM-MACRO-INFEASIBLE` details: `{date, deltas: {calories: -300, protein_g: -25, ...}}`.
- [ ] Codes registered in `src/api/error_mapping.py` and in the OpenAPI component schemas.
- [ ] Documented in `docs/DEBUG_PLANNER_PARITY.md` (append a "Failure modes" section).
- [ ] Tests:
  - Each failure mode is reachable from a crafted input and returns the exact shape.
  - `fix_hint` strings are stable (snapshot test) so UI copy doesn't drift silently.

## Implementation notes

- Keep `fix_hint` server-side so copy lives in one place and is testable. Flutter can override for i18n later.
- Do not mix partial-success and failure: a plan that succeeds with warnings is `termination_code="OK"` + `report.warnings`; only a plan the user must act on is a failure.

## Out of scope

- LLM-driven auto-recovery (Week 2+).
- i18n of fix hints.
