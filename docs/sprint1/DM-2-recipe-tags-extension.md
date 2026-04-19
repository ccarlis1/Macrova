# DM-2 — Extend Recipe with tags

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-1

## Summary

Add **`default_servings`** and **typed tag slugs** to the recipe bank, persisted in lockstep with **`RecipeTagsJson`** (extend schema in `src/llm/schemas.py`) and **`tag_repository`** / `recipes.json` so there is a single serialization story. Migrate `data/recipes/recipes.json` without data loss.

## Context

Architecture already has **`RecipeTagsJson`** on drafts; runtime **`Recipe`** in `src/data_layer/models.py` does not yet carry tags in the snapshot. Sprint 1 adds additive fields that **merge into** the unified registry (DM-1), not a parallel `List[Tag]` graph on `Recipe` unless it mirrors persisted slugs only.

Unblocks: BE-3, BE-4, AI-3, FE-1, FE-4.

## Acceptance criteria

- [ ] `Recipe` gains (additive):
  - `default_servings: int = 1`
  - Typed tag slug storage aligned with extended **`RecipeTagsJson`** (e.g. nested dict or parallel lists per type — exact shape chosen in implementation, must round-trip JSON).
  - `is_meal_prep_capable` derived from `default_servings >= 2` and presence of `meal-prep` context slug.
- [ ] `RecipeDB.load()` reads new fields when present, otherwise falls back to empty tags + `default_servings=1`.
- [ ] `RecipeDB.save()` writes new fields.
- [ ] Migration script `scripts/migrate_recipes_tags.py`:
  - Reads current `recipes.json`.
  - Adds `tags: []` and `default_servings: 1` to every recipe missing them.
  - Writes back in place with a `.bak` copy.
- [ ] `tests/data_layer/test_recipe_db.py` adds round-trip tests for the new fields and the `is_meal_prep_capable` derivation.
- [ ] Existing tests still pass.

## Implementation notes

- JSON shape for `tags`: store as a list of `{"slug": "...", "type": "..."}` — hydrate to full `Tag` via `TagRegistry.resolve()` on load. This avoids duplicating `display` / `created_at` / `source` in every recipe.
- Unknown tag on load → log warning, drop it, continue (do not fail). Rationale: registry may evolve; recipe loading must stay robust.
- Keep the dataclass API stable; do not break existing constructor call sites.

## Out of scope

- Computing `time-*` tags from `cooking_time_minutes` (that's DM-5).
- Planner reading tags (BE-3).
- UI editing (FE-4, FE-5).
