# BE-15 — Backend readiness contract tests

**Status:** implemented  ·  **Complexity:** M  ·  **Depends on:** BE-10, BE-11, BE-12, BE-13, BE-14

Sprint 2 close-out (DOC-1, 2026-11-14): Implemented: all 5 bullets are covered by existing tests, named below.

## Summary

Add focused backend contract tests for frontend-critical plan, pin, tag, recipe, and meal-prep payloads.

## Context

Audit highlighted missing route-level coverage for the exact API contracts frontend depends on. This task locks the minimum stable behaviors before frontend implementation expands.

Unblocks: FE-9 (contract confidence).

## Acceptance criteria

- [x] `/api/v1/plan` test proves `required_tag_slugs` empty-candidate case returns `FM-TAG-EMPTY` in `report.failures[]`. Test: `tests/api/test_plan_contract.py::test_plan_fm_tag_empty_failure_shape_on_schedule_days`.
- [x] `/api/v1/plan` test proves active meal-prep lock returns `source`, `batch_id`, `slot_index`, `servings` in planned meal payload. Test: `tests/api/test_plan_contract.py::test_plan_response_meal_metadata_meal_prep_batch_contract`.
- [x] Tag route tests cover create, duplicate handling, alias normalization, merge, and list. Test: `tests/api/test_tag_routes_contract.py`: `test_create_tag_returns_slug_type_display`, `test_create_duplicate_slug_returns_tag_conflict`, `test_add_alias_normalizes_input`, `test_merge_src_into_dst_updates_registry`, `test_list_tags_includes_dm6_runtime_metadata`.
- [x] Recipe route tests cover typed tags + `default_servings` round-trip through create/update/sync/detail. Test: `tests/api/test_recipe_routes.py::test_create_roundtrip_returns_typed_tags_and_default_servings` (create + detail), `::test_put_roundtrip_updates_default_servings_and_derivation` (update + detail), `tests/api/test_recipe_sync.py::test_sync_roundtrip_tags_and_default_servings` (sync + detail).
- [x] Pin route tests cover create/read/clear, missing recipe, and batch-lock precedence behavior. Test: `tests/api/test_profile_pins.py`: `test_profile_pins_crud_idempotent_and_clear`, `test_profile_pins_unknown_recipe_id_returns_structured_not_found`, `test_plan_meal_source_batch_lock_overrides_pin_on_same_slot`.

## Implementation notes

- Keep assertions at API contract level, not internal implementation detail level.
- Use DM-7 canonical seed data for deterministic test fixtures.
- Keep this backend-only; frontend parser tests remain in FE tasks.

## Out of scope

- Exhaustive planner determinism testing beyond frontend-critical contracts.
- Broad validation taxonomy refactors.
- OpenAPI codegen pipeline rollout.
