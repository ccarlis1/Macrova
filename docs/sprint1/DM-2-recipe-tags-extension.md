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

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/data_layer/models.py` — `Recipe` dataclass; add `default_servings` and tag slug fields with safe defaults; preserve every existing field and constructor call site
- `src/llm/schemas.py` — `RecipeTagsJson`; the tag shape here must align with how tags are stored on `Recipe`
- `src/llm/tag_repository.py` — `TagRegistry.resolve()` (DM-1 output); called on `RecipeDB.load()` to hydrate tags; read its API before using it
- `frontend/lib/models/recipe.dart` — `Recipe_frontend`; read only; **do not modify** in this task

**Entities to reuse:**
- `Recipe` in `src/data_layer/models.py` — extend in-place; do not create a parallel class
- `RecipeTagsJson` in `src/llm/schemas.py` — tag fields must round-trip with `Recipe` tag storage

**Do NOT create:**
- A `RecipeWithTags` parallel class
- HTTP routes or UI code
- A separate JSON file for recipe tags outside `recipes.json`

**Known gap:** `data/recipes/recipe_tags.json` is absent from the repo snapshot but referenced in `server.py`. After DM-2, tags live in `recipes.json` alongside each recipe record — ensure the migration script confirms this.

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/data_layer/models.py` in full.** List every field on the `Recipe` dataclass and its default values. Identify `RecipeDB.load()` and `RecipeDB.save()` implementations.
2. **Search the codebase for `Recipe(` constructor calls.** Confirm all existing sites remain valid after adding new optional fields with defaults.
3. **Read `src/llm/schemas.py`.** Note the current `RecipeTagsJson` field names; decide the exact JSON shape for `tags` on `Recipe` (stub specifies `[{"slug": "...", "type": "..."}]`).
4. **Confirm `scripts/migrate_recipes_tags.py` does not already exist** before creating it.
5. **Identify the `recipes.json` path** used in `RecipeDB` to confirm the migration script targets the correct file.
6. State the exact new fields on `Recipe`, their types, and defaults before writing the first line of code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `Recipe` in `src/data_layer/models.py` has `default_servings: int = 1` and tag slug storage with `[]` default — no existing call sites broken
- [ ] `RecipeDB.load()` silently falls back to empty tags and `default_servings=1` for recipes missing these fields (backward-compatible)
- [ ] `RecipeDB.save()` writes the new fields; a round-trip (save then load) preserves values exactly
- [ ] `is_meal_prep_capable` is derived (not stored) and returns `True` iff `default_servings >= 2` AND `meal-prep` context slug is present
- [ ] `scripts/migrate_recipes_tags.py` runs without error, writes `.bak`, and every migrated recipe has `tags: []` and `default_servings: 1`
- [ ] All round-trip tests in `tests/data_layer/test_recipe_db.py` pass
- [ ] No frontend Dart files were modified in this task
