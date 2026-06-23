# BE-15 — Backend readiness contract tests

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** BE-10, BE-11, BE-12, BE-13, BE-14

## Summary

Add focused backend contract tests for frontend-critical plan, pin, tag, recipe, and meal-prep payloads.

## Context

Audit highlighted missing route-level coverage for the exact API contracts frontend depends on. This task locks the minimum stable behaviors before frontend implementation expands.

Unblocks: FE-9 (contract confidence).

## Acceptance criteria

- `/api/v1/plan` test proves `required_tag_slugs` empty-candidate case returns `FM-TAG-EMPTY` in `report.failures[]`.
- `/api/v1/plan` test proves active meal-prep lock returns `source`, `batch_id`, `slot_index`, `servings` in planned meal payload.
- Tag route tests cover create, duplicate handling, alias normalization, merge, and list.
- Recipe route tests cover typed tags + `default_servings` round-trip through create/update/sync/detail.
- Pin route tests cover create/read/clear, missing recipe, and batch-lock precedence behavior.

## Implementation notes

- Keep assertions at API contract level, not internal implementation detail level.
- Use DM-7 canonical seed data for deterministic test fixtures.
- Keep this backend-only; frontend parser tests remain in FE tasks.

## Out of scope

- Exhaustive planner determinism testing beyond frontend-critical contracts.
- Broad validation taxonomy refactors.
- OpenAPI codegen pipeline rollout.
