# FE-12 — Recipe builder: meal-role, cuisine and cost tags, and a meal-prep switch

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** P0 (PR #63 merged), BE-19 (sync accepts `cuisine`/`cost_level`)
**Supersedes:** Sprint 1 FE-5 (tag chip picker, merged: reuse `MacrovaChip`) and the Tags section and meal-prep switch of Sprint 1 FE-4.

## Summary

Give Flutter's `Recipe` its tags. Read `tag_slugs_by_type` and `is_meal_prep_capable` from the recipe detail, send `tag_slugs_by_type` on sync, and add a Tags section to the Recipe Builder: meal role (required), cuisine and cost (optional), and a "Meal-prep capable" switch. Warn in Planner Config when a pool filter will exclude recipes with no value for it.

## Context

Follow-ups 4 (Flutter half) and 7b.

- Flutter's `Recipe` (`frontend/lib/models/recipe.dart`) has no tags, `toSyncPayload` sends none, and `fromJson` reads none.
- Recipes made in the app get no meal-role tag (breakfast/lunch/dinner/snack). `meal_type_matches` (`src/planning/phase4_scoring.py` ~line 163) then returns no match, and the redesign shows a "Not tagged as <meal>" chip.
- Pool filters are hard constraints. The probe on 2026-11-14 confirmed an app recipe with no `tags_by_id` entry is dropped by every one of `cuisine`, `cost_level`, `prep_time_bucket` and `dietary_flags`. BE-19 gives every synced recipe a derived prep-time entry. Cuisine and cost remain unknown unless the user sets them, so a cuisine filter still (correctly) excludes those recipes. The user has to see that.
- `is_meal_prep_capable` (detail response) is `default_servings >= 2` and the canonical `context` tag `meal-prep` (hard-eligible). **No bundled recipe is meal-prep capable today**: none has the tag, and all have `default_servings` 1. In the demo, this switch is the only way to get a batchable recipe (FE-14).

The sync contract already accepts `tag_slugs_by_type` (`RecipeSyncItem`, BE-11) and validates slugs against the registry (`TAG_NOT_FOUND`, `TAG_INVALID`).

## Acceptance criteria

- [ ] `Recipe` gains `tagSlugsByType: Map<String, List<String>>` and `isMealPrepCapable: bool` (read-only, from the server). `fromJson` reads `tag_slugs_by_type` / `is_meal_prep_capable` when present. `toSyncPayload` sends `tag_slugs_by_type` when non-empty. Tests: extend `test/recipe_sync_payload_test.dart`, and add a detail-JSON fixture test.
- [ ] Recipe Builder has a Tags section built from `MacrovaChip`:
  - **Meal role:** multi-select from the registry's `context` tags with `semantic_class == meal_role`, at least one required to save (inline error otherwise).
  - **Cuisine:** single-select, optional, closed vocabulary. Sent as the sync field `cuisine` (BE-19).
  - **Cost:** single-select, optional. Sent as `cost_level` (BE-19).

  Meal-role options come from `GET /api/v1/tags` (cached per session), not a hard-coded list. Widget tests: save blocked without a meal role; meal roles land in `tagSlugsByType`; cuisine/cost land in the sync payload's top-level fields.
- [ ] "Meal-prep capable" switch: ON adds `meal-prep` to `context` and enforces `servings >= 2` (bumps to 2 with a note); OFF removes it. Widget test for both directions.
- [ ] Opening an existing server recipe pre-selects its tags (from the detail payload). Widget test with a fixture.
- [ ] Planner Config: when a cuisine or cost filter is selected and some recipes in the selected pool have no value for it, show an `AdvisoryCard`: "N recipes have no cuisine set and will be left out." The count comes from the loaded `tagSlugsByType`/detail data, not from guessing. Widget test.
- [ ] `ApiService` gains `listTags()` for `GET /api/v1/tags`, with a typed DTO from the actual response shape (`tag_routes.py::_to_payload`: slug, display, tag_type, eligibility, ...). Only `approved` and system/user tags are offered. Test with a fixture response.
- [ ] No new chip widget and no new provider. Tags live on `Recipe` / `RecipeProvider`.
- [ ] `cd frontend && flutter analyze && flutter test` green.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `frontend/lib/models/recipe.dart`, `providers/recipe_provider.dart` (`syncSummariesFromApi`, sync), `providers/recipe_builder_coordinator.dart`, `screens/recipe_builder_screen.dart`, `screens/planner_config_screen.dart`, `widgets/planner/tag_pool_filter_section.dart`, `widgets/macrova_chip.dart`, `services/api_service.dart`, `src/api/tag_routes.py`, `src/api/recipe_sync.py` (`RecipeSyncItem`), `src/api/server.py` (`RecipeDetailResponse` ~line 296, detail ~line 1900), `docs/tagging/tag-semantics-contract.md`.
- Entities to reuse: `MacrovaChip`, `AdvisoryCard`, `RecipeProvider`, `ApiService`.
- Do NOT create: `TagChip`/`TagChipPicker` widgets (Sprint 1 FE-5's design), a `TagProvider`, or a second tag write path (tags go only through recipe sync).

### 🧠 Pre-implementation analysis
1. `REQUIRES_VERIFICATION`: the exact `GET /api/v1/tags` response shape and query params (`tag_routes.py` ~line 64). Write the DTO from it, not from the Sprint 1 stub.
2. Checked 2026-11-14: the registry has 4 `context`/`meal_role` tags, 1 `context`/`capability` (`meal-prep`), 5 `time`, 3 `nutrition` and 1 `constraint`. Cuisine and cost are **not** slugs: they're `RecipeTagsJson` fields, which BE-19 makes settable on sync (`cuisine`, `cost_level`). Send them as those top-level sync fields, not inside `tag_slugs_by_type`. Take the cuisine options from the tagger's closed vocabulary as exposed by BE-19; `REQUIRES_VERIFICATION` whether BE-19 exposes it through an endpoint or the OpenAPI enum.
3. Check how `syncSummariesFromApi` builds `Recipe`s from the list endpoint (`id`/`name` only) and whether it already fetches detail. The filter warning needs tags for every pool recipe; if that means N detail calls, note it and cap it to the selected pool.

### ✅ Post-implementation validation
- `cd frontend && flutter analyze && flutter test`
- Manual: create a recipe with Breakfast + Meal-prep capable, sync, then `GET /api/v1/recipes/{id}` shows the tags and `is_meal_prep_capable: true`.

## Out of scope

- Slot `required_tag_slugs`/`preferred_tag_slugs` editors (deferred with Sprint 1 FE-8).
- Approving LLM-proposed tags, or the inline "+ New tag" creator (follow-up 5, deferred).
- Unit guard and sync errors (FE-13).
