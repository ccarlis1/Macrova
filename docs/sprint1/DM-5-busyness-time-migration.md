# DM-5 — Busyness → time-* tag migration

**Status:** implemented  ·  **Complexity:** S  ·  **Depends on:** DM-1, DM-2

## Summary

One-shot script that stamps a `time-`* tag onto every existing recipe by bucketing `cooking_time_minutes`, while keeping schedule `busyness=0` semantics untouched (workout-only).

## Context

The app has two overlapping notions of "busyness": `Meal.busyness_level ∈ {1..4}` and the raw `cooking_time_minutes`. Sprint 1 collapses both into a 5-bucket `time-*` tag scale (see `SPRINT_1.md` §2.4). This migration brings the existing recipe corpus into that scheme so BE-3 can start filtering immediately.

Unblocks: BE-3 (in practice — without `time-*` tags the planner filter has nothing to hard-constrain on).

## Acceptance criteria

- Scope guard: this task only migrates recipe tags; it does **not** reinterpret profile schedule slots.
- `scripts/migrate_recipes_time_tags.py`:
  - Reads `data/recipes/recipes.json`.
  - For each recipe, computes the bucket from `cooking_time_minutes`:
    - `0` → `time-0`
    - `1..5` → `time-1`
    - `6..15` → `time-2`
    - `16..30` → `time-3`
    - `31..∞` → `time-4`
  - Removes any existing `time-*` tag before adding the new one (idempotent).
  - Writes back in place with a `.bak` copy.
- Supports a `--dry-run` flag that prints the proposed change per recipe.
- Logs a summary: `{total, tagged, changed, unchanged}`.
- After running on the current corpus, every recipe has exactly 1 `time-*` tag (enforced by a sanity check test).
- Test `tests/scripts/test_migrate_time_tags.py` with a small fixture.

## Implementation notes

- `cooking_time_minutes` of `0` is valid (kiwi + bar case) → `time-0`. Do not treat as an error.
- Keep the bucket function small and importable; BE-3 and AI-3 can reuse it.
- Script should call `TagRegistry.resolve("time-N")` so an unseeded registry fails loudly rather than silently writing garbage.

## Out of scope

- Adding `context` tags (manual step, tracked separately).
- Migrating legacy profile `schedule` entries with `busyness=0` (handled in DM-4).
- Migrating `busyness_level` on runtime `Meal` objects (no persistent storage of those).

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**

- `src/data_layer/models.py` — `Recipe` (fields: `cooking_time_minutes`, `id`, `name`) and `Meal` (field: `busyness_level`); recipe is the migration target; `Meal.busyness_level` is runtime-only and untouched
- `src/llm/tag_repository.py` — `TagRegistry.resolve("time-N")` must exist (DM-1 output); the script calls this to fail loudly on an unseeded registry
- `scripts/` directory — check for `migrate_recipes_time_tags.py`; it should not exist yet

**Entities to reuse:**

- `TagRegistry.resolve()` from `src/llm/tag_repository.py` (DM-1) — the bucket function must call this, not write tags directly
- `data/recipes/recipes.json` — the backing file read and written in-place

**Do NOT create:**

- A duplicate bucket function in this script — extract it as a standalone importable helper so BE-3 and AI-3 can import it
- Any changes to `Meal.busyness_level` or profile schedule entries

**Bucket function must be importable:** Place it at `src/llm/time_bucket.py` (or inline in `tag_repository.py`) so downstream tasks (BE-3, AI-3) can reuse it without copying.

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/data_layer/models.py`.** Confirm `Recipe.cooking_time_minutes` field type (int vs. Optional[int]).
2. **Read `src/llm/tag_repository.py` (DM-1 output).** Confirm `TagRegistry.resolve("time-0")` through `resolve("time-4")` are valid calls — the five time-bucket slugs must be in the seed data.
3. **Check whether `scripts/migrate_recipes_time_tags.py` already exists.**
4. **Check whether a time-bucket helper already exists** anywhere in `src/llm/` or `src/` to avoid duplication.
5. **Identify the tag storage path on `Recipe`** (from DM-2) to ensure the script writes to the correct field.
6. State the exact bucket function signature, its import path, and the script's read/write flow before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- The bucket function is **importable** from a stable path (not embedded only in the script); BE-3 and AI-3 can `from ... import time_bucket` without copying code
- `scripts/migrate_recipes_time_tags.py --dry-run` prints proposed changes without modifying any files
- Running the script on the current corpus: every recipe gets exactly 1 `time-`* tag; `cooking_time_minutes=0` → `time-0`; no `time-*` tag left duplicated
- Script creates a `.bak` copy before writing
- Script summary output includes `{total, tagged, changed, unchanged}`
- `TagRegistry.resolve("time-N")` is called for each bucket; if the registry is empty/unseeded, the script raises loudly (not silently writes garbage)
- Test in `tests/scripts/test_migrate_time_tags.py` with a small fixture passes
- `Meal.busyness_level` and profile schedule entries are unchanged

