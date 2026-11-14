# BE-19 — Recipe saves are plannable: unit conversions, unit rejection, sync `errors`, derived time tags

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** P0 (Flutter DTO line), BE-18 (same file: `recipe_sync.py`), BE-21 (same files: `server.py`, `calculator.py`), BE-22 (recipe-store paths now come from the `MACROVA_DATA_DIR` setting; write tests against a temp data folder, not the committed `recipes.json`)

## Summary

A recipe saved through sync, create or update should be plannable or rejected, never silently dropped later. This task:
- accepts per-line `unit_conversions` from the client;
- rejects units with no gram conversion;
- reports per-item problems in the sync response's `errors` (always empty today);
- stores derived `prep_time_bucket` and `time-*` tags for every synced recipe, so pool filters don't drop app recipes for lack of a tag entry.

## Context

Follow-ups 11 (backend half), 7a and 4 (backend half).

- **Units.** Flutter's `Ingredient.unitConversions` (for example `cup`, `tbsp` from the Ingredient Hub) never reaches the server. `Recipe.toSyncPayload` sends only `name`, `quantity` and `unit`. On the server, an unknown unit makes the ingredient unresolved at planning, so the recipe drops out of the pool with `warnings.nutrition`. The user saved it successfully and only finds out at planning time.
- **`errors`.** `RecipeSyncResponse.errors: List[str]` exists, but every return in `sync_recipes_endpoint` (`server.py` ~1824) sends `synced_ids` only. Follow-up 7a ("show the sync response's `errors`") has nothing to show until this task.
- **Tags.** `recipe_sync.py::_build_updated_tags_by_id`:
  - If the item has no `tag_slugs_by_type`, it writes **no** `tags_by_id` entry.
  - If it has one, it writes a new entry with hard-coded `cuisine: "unknown"`, `cost_level: "standard"`, `prep_time_bucket: "weeknight_meal"`, whatever the cooking time.

  Probe, 2026-11-14: `filter_recipe_ids_by_preferences` with a tagged recipe and an untagged app recipe returned only the tagged one for `cost_level: standard` and for `prep_time_bucket: weeknight_meal`. The untagged app recipe is dropped by every pool filter. The LLM tagger already derives `prep_time_bucket` and `time-*` from `cooking_time_minutes` (AGENTS.md, Tagging Rules).

Design choice: client conversions are stored **on the recipe's ingredient line** (`grams_per_unit` for that line's unit) and used by the calculator only when the ingredient record has no conversion for that unit. They are never written into `data/reference/ingredient_nutrition.json`, which is reviewed reference data. This is the "merge into `grams_per_unit`" from follow-up 11, scoped to the recipe.

## Acceptance criteria

- [x] `RecipeSyncIngredientLine` gains an optional `grams_per_unit: Optional[float] = Field(None, gt=0)`, the weight of one `unit` of this line. It is persisted in `recipes.json` only when set (additive). Test: sync round-trip stores it and `GET /api/v1/recipes/{id}` returns it in that line's `unit_conversions`.
- [x] Calculator gram conversion order: unit `g` (and other mass units) → the ingredient record's `grams_per_unit[unit]` → the line's `grams_per_unit` → unresolved. The record wins when both exist. Tests in `tests/test_nutrition_calculator.py` (or the existing module): line-only conversion resolves; record + line uses the record; neither is unresolved.
- [x] Save-time validation on sync/create/PUT: a line whose unit converts by none of the above, or whose ingredient doesn't resolve with the local provider, is rejected.
  - Single create/PUT: 400 with a new registered code (proposed `UNIT_NOT_CONVERTIBLE`, `details: {ingredient, unit}`; reuse the existing unresolved-ingredient code for unknown names if one exists).
  - Sync: the item is **not** stored, its id is not in `synced_ids`, and `errors` gets one message naming recipe id, ingredient and unit. Other items still sync.
  - Tests in `tests/api/test_recipe_routes.py` for each; they fail today (stored and synced).
  - Done: no unresolved-ingredient API code existed, so `INGREDIENT_UNRESOLVED` (the recipe validator's internal code) is now registered; both codes are HTTP 400 with `details: {ingredient, unit}`. Sync `errors` entries read `"<recipe id>: <CODE>: <message>"`.
- [x] Every synced/created recipe gets a `tags_by_id` entry. `prep_time_bucket` and the `time-*` slug are derived from `cooking_time_minutes` using the tagger's existing derivation function. Client `tag_slugs_by_type` are merged in (canonicalized as today). Test: syncing an untagged 10-minute recipe yields `prep_time_bucket` for ≤15 min and `time-2`, and `filter_recipe_ids_by_preferences(..., {"prep_time_bucket": <that bucket>})` includes it. Fails today (no entry).
- [x] `RecipeSyncItem` gains optional `cuisine` (the tagger's closed vocabulary), `cost_level` (`BudgetLevel`) and `dietary_flags` (`List[DietaryFlag]`), all additive. When sent, they're written to the recipe's `RecipeTagsJson`. When omitted, a prior value is kept, else the current defaults (`"unknown"`, `"standard"`, `[]`). Checked 2026-11-14: these are required fields on `RecipeTagsJson`, not slugs, so sync can't set them today. FE-12's cuisine/cost pickers need this. Tests: round-trip each field; an out-of-vocabulary cuisine → 400 `INVALID_REQUEST`.
- [x] The hard-coded `prep_time_bucket: "weeknight_meal"` for new tagged recipes is replaced by the derived value. Test.
- [x] `upsert_recipe_tags` is still called in merge mode (not `replace=True`). Test that an unrelated recipe's tags survive a sync.
- [x] OpenAPI regenerated; `tests/test_api_v1_and_openapi.py` covers the new line field and error code.
- [ ] Flutter DTO (after P0): `Recipe.toSyncPayload` sends `grams_per_unit` for each line whose unit isn't `g` and whose ingredient has a conversion in `Ingredient.unitConversions`. Test in `test/recipe_sync_payload_test.dart`. If FE-12 has already changed `toSyncPayload`, rebase on it.
  - Not done here: owned by frontend track.
- [x] `benchmark-audit`: 153/153, 0 regressions (calculator change).

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `src/api/recipe_sync.py`, `src/api/server.py` (sync/create/put endpoints ~1824–1890, `RecipeSyncResponse`), `src/nutrition/calculator.py` (`to_grams`), `src/data_layer/models.py` (`Ingredient`; does it need an optional `grams_per_unit`?), `src/data_layer/recipe_db.py` (`_parse_ingredient`), `src/llm/recipe_tagger.py` (the existing `cooking_time_minutes` → bucket/`time-*` derivation), `src/llm/tag_repository.py` (`upsert_recipe_tags`), `src/llm/schemas.py` (`RecipeTagsJson` defaults), `src/api/error_mapping.py`.
- Entities to reuse: the tagger's time derivation (extract to a shared helper if it's private, but keep one implementation), `RecipeTagsJson`, `upsert_recipe_tags`.
- Do NOT create: a second tag write path, a second time-bucket mapping, or writes to `ingredient_nutrition.json`.

### 🧠 Pre-implementation analysis
1. Checked: `RecipeTagsJson.cuisine` (`StrictStr`), `cost_level` (`BudgetLevel`) and `prep_time_bucket` (`PrepTimeBucket`) are required (`src/llm/schemas.py` ~line 76). Keep the existing defaults rather than changing the schema; making them optional is a Sprint 3 question.
2. `REQUIRES_VERIFICATION`: the exact name and location of the tagger's derivation (`grep -n "prep_time_bucket\|time-" src/llm/recipe_tagger.py`).
3. Save-time resolution needs the ingredient provider at request time. Use the same local provider the plan endpoint builds, so save and plan agree. USDA-mode recipes: if the server runs with `ingredient_source=api` at plan time, document what save-time validation does (local only, plus a note in `errors`), and don't call USDA from sync.
4. BE-18 adds a save-time `to taste` check in the same functions. Build on it; don't duplicate the validation loop.

### ✅ Post-implementation validation
- `python3 scripts/run_pytest.py`; `python3 scripts/run_export_openapi.py --check`
- `benchmark-audit`: 153/153, 0 regressions
- `cd frontend && flutter analyze && flutter test`

## Out of scope

- Flutter UI for sync errors and the editor unit guard (FE-13).
- Flutter tag chips (FE-12).
- Inferring cuisine or cost for app recipes.
