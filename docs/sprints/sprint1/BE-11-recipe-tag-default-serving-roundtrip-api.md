# BE-11 — Recipe tag/default serving round-trip API

**Status:** implemented  ·  **Complexity:** M  ·  **Depends on:** DM-2, DM-7, BE-1

## Summary

Extend recipe create/update/sync/detail contracts so typed tags and `default_servings` are accepted and returned consistently.

## Context

Frontend recipe tagging and meal-prep creation are blocked because recipe routes currently round-trip only basic fields. Batchability requires stable inputs (`context:meal-prep` and `default_servings >= 2`) that must survive route round-trip.

Unblocks: FE-4, FE-7, BE-13, BE-15.

## Acceptance criteria

- `POST /api/v1/recipes`, `PUT /api/v1/recipes/{id}`, and sync routes accept typed tag slugs and `default_servings`.
- `GET /api/v1/recipes/{id}` returns typed tags, `default_servings`, and derived `is_meal_prep_capable`.
- Route behavior for unknown tag slugs is deterministic: normalize through repository or reject with structured tag error.
- `default_servings` validation enforces integer `>= 1`.
- Meal-prep capability derivation remains: `default_servings >= 2` and approved `context:meal-prep`.

## Implementation notes

- Build on DM-2 storage and BE-1 tag repository normalization.
- Keep contract additive and backward compatible for existing clients.
- Do not fork a new recipe-tag persistence model.

## Out of scope

- LLM tagging quality improvements.
- Frontend recipe form implementation.
- Bulk retagging beyond route contract needs.
