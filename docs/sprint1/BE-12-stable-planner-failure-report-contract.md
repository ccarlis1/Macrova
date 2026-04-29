# BE-12 — Stable planner failure report contract

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** BE-7

## Summary

Stabilize planner response fields so `PlanResponse` always exposes a first-class `plan_status` and structured `report.failures[]`.

## Context

Current planner failure outputs are mixed between structured and legacy shapes. Frontend-rich failure handling is blocked until failure objects are stable and consistently present.

Unblocks: FE-9, BE-15.

## Acceptance criteria

- `PlanResponse` includes stable `plan_status` values (`success`, `partial`, `failed`).
- `report.failures` is always present as a list (empty on success).
- Failure objects always include `code` and `message`, plus `day_index`/`slot_index` for slot-scoped failures.
- `FM-TAG-EMPTY`, `FM-BATCH-CONFLICT`, and `FM-MACRO-INFEASIBLE` emit structured failure objects.
- Legacy `FM-1`, `FM-3`, `FM-4`, `FM-5` are mapped into the same stable failure object shape.

## Implementation notes

- Extend BE-7 additively; preserve existing response fields consumed by clients.
- Keep canonical slot coordinates for frontend consumption.
- Keep planner-originated failures distinct from generic FastAPI request validation errors.

## Out of scope

- Full failure taxonomy redesign.
- Field-path validation detail improvements for all request errors.
- Frontend model/parser implementation.
