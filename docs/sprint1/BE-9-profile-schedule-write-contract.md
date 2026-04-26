# BE-9 — Profile schedule write contract

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** DM-4

## Summary

Define and implement an explicit backend API contract for writing `DaySchedule` and `MealSlot` edits from FE-8.

## Context

FE-8 requires a stable persistence path; without a clear contract, slot-config UX is non-functional and brittle.

Unblocks: FE-8, FE-10.

## Acceptance criteria

- [ ] A documented request/response schema exists for profile schedule writes, including validation errors.
- [ ] Contract supports `required_tag_slugs`, `preferred_tag_slugs`, `busyness_level`, `preferred_time`, and canonical slot indexing.
- [ ] Contract preserves workout modeling via `WorkoutSlot` (`after_meal_index`, `type`, `intensity`) instead of `busyness_level=0`.
- [ ] Endpoint behavior is idempotent for equivalent payloads and returns normalized persisted shape.
- [ ] FE-8 integration test can save and re-load edited slot config without lossy field drops.

## Implementation notes

- Reuse existing profile write route if it already exists; otherwise add one additive endpoint.
- Keep payload aligned with canonical slot addressing and planner input expectations.

## Out of scope

- Frontend editor implementation (FE-8).
- Forcing mode UX copy and control behavior (FE-10).
