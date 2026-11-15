# FE-13 — Unknown units fail in Flutter; sync errors shown

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** BE-19 (server validation and `errors`), FE-12 (same file: `recipe_builder_screen.dart`)
**Supersedes:** the unit part of Sprint 1 FE-4.

## Summary

Make Flutter's gram conversion strict the way the backend is: an unknown unit is an error, not "treat the number as grams". Block saving a recipe with an unconvertible unit, and show the server's per-recipe sync `errors`.

## Context

Follow-ups 11 (Flutter half) and 7a.

- `Ingredient.toGrams` (`frontend/lib/models/ingredient.dart` ~line 63) and `RecipeIngredientEntry._grams` (`models/recipe.dart` ~line 26) return `quantity` unchanged when the unit has no conversion. So "2 cup" of something with no `cup` conversion shows as 2 g in the builder, while the backend marks the ingredient unresolved and drops the recipe from planning.
- After BE-19, sync returns per-item `errors` and leaves rejected items out of `synced_ids`. `ApiService.syncRecipes` (~line 107) returns only `synced_ids` and drops `errors`.
- After BE-21, recipe detail returns real `unit_conversions` per line, so the strict path has data to work with.

## Acceptance criteria

- [x] `Ingredient.toGrams` and `RecipeIngredientEntry._grams` throw a typed `UnknownUnitException(unit, ingredientName)` for an unknown non-`g` unit. Callers that compute totals catch it and mark the line unresolved instead of summing a wrong number. Unit tests: `test/ingredient_to_grams_test.dart` (fails today: returns the quantity).
- [x] Recipe Builder shows an inline "No gram weight for '<unit>'" error on an unconvertible line and disables Save while any line is in that state. Choosing `g` or a known unit clears it. Widget test.
- [x] `ApiService.syncRecipes` returns a `RecipeSyncResult(syncedIds, errors)`. `RecipeProvider` keeps the latest errors, and Recipe Library shows them in an `AdvisoryCard` naming each rejected recipe. The redesign's existing sync banner is reused, not duplicated. Tests: provider test with a fake sync fn returning one error; widget test for the advisory.
- [x] `MealPlanProvider`'s pre-plan sync (~line 508) surfaces sync errors as a plan warning instead of ignoring them. Test with a fake.
- [x] Every existing caller of `syncRecipes` compiles against the new return type.
- [x] `cd frontend && flutter analyze && flutter test` green.

Delivered notes: strict grams follow the server's `record_grams` for the units it knows without a record (`g`/`gram(s)`, line conversions, `oz`/`ounce(s)` at 28.35 g, `to taste` = 0 g); anything else throws. Tests: `test/ingredient_to_grams_test.dart`, `test/widgets/recipe_builder_unit_guard_test.dart` (also checks the builder's `/nutrition/summary` lines carry `grams_per_unit`), `test/recipe_sync_result_test.dart`, `test/recipe_provider_sync_test.dart`, `test/widgets/recipe_library_screen_test.dart`, `test/providers/meal_plan_provider_sync_test.dart`. Sync rejections on a plan that fails or is partial sit in `MealPlan.warnings`, which Today / Meal Plan View show only on success, so there they are not visible yet. Not run: the manual fixture-server check.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `frontend/lib/models/ingredient.dart`, `models/recipe.dart`, `services/api_service.dart`, `providers/recipe_provider.dart`, `providers/meal_plan_provider.dart` (~line 508), `screens/recipe_builder_screen.dart`, `screens/recipe_library_screen.dart`, `test/recipe_provider_sync_test.dart`, `test/recipe_available_units_test.dart`, and BE-19's final `RecipeSyncResponse`.
- Entities to reuse: `AdvisoryCard`, `ApiException`, `RecipeProvider`.
- Do NOT create: a new error widget or provider.

### 🧠 Pre-implementation analysis
1. List every caller of `toGrams`, `_grams` and the nutrition getters (`grep -rn "toGrams\|\.calories\b" frontend/lib`). Each needs a decision: catch and mark unresolved, or propagate.
2. `REQUIRES_VERIFICATION`: `recipe_available_units_test.dart` expectations. Units offered in the dropdown should already be convertible; make sure the strict path doesn't break offered units.

### ✅ Post-implementation validation
- `cd frontend && flutter analyze && flutter test`
- Manual: add a line with a unit the ingredient can't convert. Save is blocked. Force-sync a bad recipe through a fixture server: the library shows the error.

## Out of scope

- Server validation (BE-19).
- Editing an ingredient's conversions in the Ingredient Hub.
