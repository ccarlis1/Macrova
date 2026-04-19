# DM-2 — Extend Recipe with tags

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-1

## Summary

Add `tags`, `default_servings`, and derived `is_meal_prep_capable` to `Recipe`. Migrate `data/recipes/recipes.json` without data loss.

## Context

`Recipe` in `src/data_layer/models.py` has a `# tags: List[str]` TODO. Sprint 1 cashes it in with typed tags referencing the registry from DM-1. Every downstream system (planner filter, LLM tagger, UI chip picker) assumes this field is present.

Unblocks: BE-3, BE-4, AI-3, FE-1, FE-4.

## Acceptance criteria

- [ ] `Recipe` gains:
  - `tags: List[Tag] = field(default_factory=list)`
  - `default_servings: int = 1`
  - `is_meal_prep_capable: bool` (derived property: `default_servings >= 2 and any(t.slug == "meal-prep" and t.type == "context" for t in tags)`).
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
