# DM-5 — Busyness → time-* tag migration

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** DM-1, DM-2

## Summary

One-shot script that stamps a `time-*` tag onto every existing recipe by bucketing `cooking_time_minutes`, while keeping schedule `busyness=0` semantics untouched (workout-only).

## Context

The app has two overlapping notions of "busyness": `Meal.busyness_level ∈ {1..4}` and the raw `cooking_time_minutes`. Sprint 1 collapses both into a 5-bucket `time-*` tag scale (see `SPRINT_1.md` §2.4). This migration brings the existing recipe corpus into that scheme so BE-3 can start filtering immediately.

Unblocks: BE-3 (in practice — without `time-*` tags the planner filter has nothing to hard-constrain on).

## Acceptance criteria

- [ ] Scope guard: this task only migrates recipe tags; it does **not** reinterpret profile schedule slots.
- [ ] `scripts/migrate_recipes_time_tags.py`:
  - Reads `data/recipes/recipes.json`.
  - For each recipe, computes the bucket from `cooking_time_minutes`:
    - `0` → `time-0`
    - `1..5` → `time-1`
    - `6..15` → `time-2`
    - `16..30` → `time-3`
    - `31..∞` → `time-4`
  - Removes any existing `time-*` tag before adding the new one (idempotent).
  - Writes back in place with a `.bak` copy.
- [ ] Supports a `--dry-run` flag that prints the proposed change per recipe.
- [ ] Logs a summary: `{total, tagged, changed, unchanged}`.
- [ ] After running on the current corpus, every recipe has exactly 1 `time-*` tag (enforced by a sanity check test).
- [ ] Test `tests/scripts/test_migrate_time_tags.py` with a small fixture.

## Implementation notes

- `cooking_time_minutes` of `0` is valid (kiwi + bar case) → `time-0`. Do not treat as an error.
- Keep the bucket function small and importable; BE-3 and AI-3 can reuse it.
- Script should call `TagRegistry.resolve("time-N")` so an unseeded registry fails loudly rather than silently writing garbage.

## Out of scope

- Adding `context` tags (manual step, tracked separately).
- Migrating legacy profile `schedule` entries with `busyness=0` (handled in DM-4).
- Migrating `busyness_level` on runtime `Meal` objects (no persistent storage of those).
