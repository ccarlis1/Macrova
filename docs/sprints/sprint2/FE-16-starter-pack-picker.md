# FE-16 — Starter-pack picker; no personal profile in the app bundle

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** P0, BE-22 (starter API); after DATA-1 is preferred (all 18 plannable)
**Supersedes:** nothing. New from the owner's 2026-11-14 decision: users start from an empty pool and choose what to eat.

## Summary

A new user's recipe library starts empty. The app offers the starter pack (the 18 sample recipes) as a list the user picks from: tick what you'd eat, import, and plan. Also stop shipping the owner's personal profile inside the Flutter bundle.

## Context

- **Backend:** BE-22 adds `GET /api/v1/starter_recipes` and `POST /api/v1/starter_recipes/import` (`{recipe_ids}` → `{imported, skipped[{id, reason}]}`) and an empty default pool in the user data folder. Sync (`/api/v1/recipes/sync`) upserts and never deletes, so imported recipes survive the sync Flutter runs before each plan.
- **Flutter today** (`merge-frontend-redesign`, checked 2026-11-14):
  - `main.dart` calls `hydrateBundledServerRecipesFromAsset()` (always) and `mergeBundledServerRecipesIfEnabled()` (only with `--dart-define=BUNDLE_SERVER_RECIPES=true`). The asset `assets/dev/server_recipes.json` is described as a copy of `data/recipes/recipes.json`, but it has drifted: 25 recipes, different ids from today's 32.
  - `main.dart` calls `profile.mergeBundledUserProfileIfEnabled()` (only with `BUNDLE_USER_PROFILE=true`). Its asset `assets/dev/user_profile.yaml` matches the owner's personal `config/user_profile.yaml` except for two values (τ 0.85 vs 0.8; breakfast busyness 1 vs 4). `pubspec.yaml` lists all three `assets/dev/*` files, so they are **packaged into every build** even when the flag is off.
  - `Recipe.fromServerRecipeMap` / `fromServerRecipesJsonRoot` already parse server recipe JSON.
  - `EmptyState` is used in `recipe_library_screen.dart` (~line 144) and `today_screen.dart` (~line 571).
- **W7 (decided):** the owner's profile is personal and leaves git (BE-20). Untracking `config/user_profile.yaml` doesn't help while a near-copy ships in the app.

## Acceptance criteria

- [x] `ApiService` gains `listStarterRecipes()` and `importStarterRecipes(List<String> ids)`, with a `StarterRecipe` DTO (`id, name, cookingTimeMinutes, caloriesPerServing, proteinGPerServing, tagSlugsByType`) and an import result DTO. Tests with fixture JSON, including a partial `skipped`.
- [x] **Picker sheet** (`MacrovaSheet`):
  - lists the starter recipes with name, kcal and protein per serving, cooking time and meal-role chips;
  - each row has a checkbox; nothing is pre-selected; "Select all" exists;
  - Import is disabled at 0 selected;
  - recipes already in the library show as "In your library" and can't be ticked.

  Widget tests: nothing pre-selected; import disabled at 0; already-imported rows disabled.
- [x] **After import:** the imported recipes appear in the Recipe Library as normal, editable recipes, with no "sample" badge needed. Then the next plan uses them.
  `REQUIRES_VERIFICATION` first: whether Flutter's plan request restricts the pool to local recipe ids (`recipe_ids` / `_filter_recipes_by_ids`). If it does, the imported recipes must be added to the local store (fetch them, `Recipe.fromServerRecipeMap`); otherwise a refresh of the server list is enough. Test the chosen path with a fake API: import 3 → library has 3 → the plan request includes them.
  Done with the refresh path (see Findings). Caveat: 6 starter recipes with a `large` line can't be re-saved from the Recipe Builder until a backend fix (Findings, "Known gap").
- [x] **Entry points:**
  - the Recipe Library empty state offers "Start from the starter pack" and "Build a recipe";
  - Today's empty state, and `FailurePanel` when `failure_cause.cause == "EMPTY_POOL"`, link to the same sheet;
  - the library app bar has a "Starter pack" action for adding more later.

  Widget test per entry point.
- [x] **No personal data in the bundle:** `assets/dev/user_profile.yaml` is removed, or replaced with the content of `config/user_profile.yaml.example` (after BE-20's defaults, if BE-20 has landed). `mergeBundledUserProfileIfEnabled` still works with the flag on. Test: the bundled asset's targets equal the example's, or the asset is gone and the flag path is removed with its test.
- [x] `assets/dev/server_recipes.json`: decide in Phase 1 whether `hydrateBundledServerRecipesFromAsset` is still needed now that recipes come from the server. If it is, regenerate the asset from `data/recipes/recipes.json.example` (the starter pack), not the full dev pool, and document the regeneration command. If it isn't, remove the asset and both calls. Either way, record the decision in this stub.
- [x] Add `Key`s on the picker's rows and Import button (cheap groundwork for W8).
- [x] `cd frontend && flutter analyze && flutter test` green.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect:
  - `lib/main.dart` (~lines 20–40)
  - `lib/providers/recipe_provider.dart` (bundling ~8–24, `hydrateBundledServerRecipesFromAsset` ~177, `mergeBundledServerRecipesIfEnabled` ~278, sync)
  - `lib/providers/profile_provider.dart` (~6–55)
  - `lib/models/recipe.dart` (`fromServerRecipeMap` ~204)
  - `lib/services/api_service.dart`
  - `lib/screens/recipe_library_screen.dart`, `lib/screens/today_screen.dart`
  - `lib/widgets/empty_state.dart`, `macrova_sheet.dart`, `failure_panel.dart`, `failure_view_model.dart`
  - `pubspec.yaml` (assets)
- Entities to reuse: `RecipeProvider` (no new provider), `MacrovaSheet`, `EmptyState`, `MacrovaChip`, `Recipe.fromServerRecipeMap`.
- Do NOT: auto-import anything on first launch, add a client-side copy of the starter pack, or add onboarding screens beyond the sheet.

### 🧠 Pre-implementation analysis
1. The `recipe_ids` question in criterion 3.
2. File overlap: FE-11 edits `failure_panel.dart`; FE-12 and FE-13 edit recipe screens and `recipe.dart`. Rebase onto whichever has merged, and keep this task's edits in those files to the entry-point link.
3. `REQUIRES_VERIFICATION`: whether any test or script relies on `assets/dev/user_profile.yaml` or `server_recipes.json` (`grep -rn "assets/dev" frontend scripts docs`).

### ✅ Post-implementation validation
- `cd frontend && flutter analyze && flutter test`
- Manual, against a local API with `MACROVA_DATA_DIR` set to a fresh folder (BE-22): the library is empty → open the starter pack → pick 5 → import → plan succeeds using only those 5. Screenshot for the PR.

## Out of scope

- Choosing which recipes are in the starter pack (owner's call).
- Removing personal data from git history (the PR notes that removed files stay in history).
- Recipe recommendations, or "you might like" ranking.

## Findings and decisions (implementation, 2026-11-14)

Checked against `sprint2-wave2` at `d788976` (FE-15) with BE-22 merged. Backend shapes confirmed in `src/api/server.py` (`StarterRecipe`, `StarterImportRequest` / `StarterImportResponse`, routes ~2028–2110) and `openapi/openapi.json`. Fixtures were captured in-process with `MACROVA_DATA_DIR` and `NUTRITION_USER_PROFILE_PATH` on temp paths (`frontend/test/fixtures/README.md`). The server also sends `ready_for_planning` and `unresolved`; the DTO reads both (the sheet notes a recipe the planner would skip; all 18 are ready today).

- **Pre-analysis 1, the `recipe_ids` pool question.** Flutter sends `recipe_ids` only when Planner Config has recipes ticked (`planner_config_screen.dart::_generate`, `selectedRecipeIds`); otherwise the field is omitted and `_filter_recipes_by_ids` returns the whole server pool. So the default path is **not** restricted, and **a refresh of the server list is enough**: `RecipeProvider.importStarterRecipes` posts the import, then re-runs `syncSummariesFromApi`. Nothing is copied to device storage (not `fromServerRecipeMap` either: its lines carry no unit conversions, so FE-13 would flag `cup` / `tbsp` lines as unresolved). Opening an import in the Recipe Builder loads `GET /recipes/{id}`, whose lines carry `unit_conversions`. With a Planner Config selection, imports appear in the pool list unticked, and the import snackbar says to tick them there. Tests: `test/widgets/starter_import_flow_test.dart` (import 3 → library has 3 → the plan request omits `recipe_ids`, so the server pool holding the 3 is used; ticked → `recipe_ids` lists them and their details sync first; an imported cup/tbsp/scoop recipe opens with no flagged line and Update enabled) and `test/providers/recipe_provider_starter_test.dart`.
- **Known gap (backend, not fixed here).** 6 of the 18 starter recipes (recipe_005, 006, 008, 012, 013, 017) have an `eggs` / `bananas` line in `large`. The server weighs it from `BASE_SERVING_WEIGHTS` but doesn't export that weight in the detail's `unit_conversions` (`server.py::_flutter_ingredient_entries` uses `NutritionCalculator.unit_conversions`, which holds record weights only). Flutter's `gramsForUnit` then has no weight for `large`, so the Recipe Builder flags that line and blocks saving until the unit is changed. Planning is unaffected, since the server resolves the line. This predates FE-16 (it affects any server recipe with such a unit). The fix is server-side (export the line's resolved grams per unit in the detail) and needs a BE follow-up.
- **Pre-analysis 2, file overlap.** FE-11/12/13 have merged. Edits in their files are limited to the entry links: `failure_view_model.dart::toHeroPanel` (EMPTY_POOL row), `recipe_library_screen.dart` (empty state, header action) and `today_screen.dart` (empty-state link). For `EMPTY_POOL` the hero row is "Start from the starter pack" **instead of** "Find a recipe" / "Set up AI help": BE-22 sets `recipe_could_help: true`, but the assisted recovery declines an empty pool, so the AI row would offer a fix that can't work.
- **Pre-analysis 3, who relies on `assets/dev`.** No test or script read `user_profile.yaml` or `server_recipes.json`: only `frontend/README.md`, a comment in `docs/frontend/design/data.js`, and the code paths below. The cached-ingredients export script writes `cached_ingredients.json`, which isn't personal data and stays.
- **`server_recipes.json` decision: removed**, with `hydrateBundledServerRecipesFromAsset`, `mergeBundledServerRecipesIfEnabled`, `BUNDLE_SERVER_RECIPES` and the provider's bundled fallback. Recipes come from the server now, and the drifted asset actively broke imports: it held `recipe_001`…`018`, so `_withBundledFallback` replaced the id+name rows of imported starter recipes with asset lines that carry no unit conversions or nutrition.
- **`user_profile.yaml` decision: removed**, with `BUNDLE_USER_PROFILE` and `ProfileProvider.mergeBundledUserProfileIfEnabled` (it had no test). Removing it, rather than shipping a copy of `config/user_profile.yaml.example`, means no personal data in the bundle and no copy to re-sync when BE-20 changes the example's defaults. `test/bundle_assets_test.dart` fails if `pubspec.yaml` lists a profile or recipe asset (or any YAML) again. The removed files stay in git history (out of scope).
- **Entry points.** The Recipe Library has no `AppBar` (the shell has none), so its "Starter pack" action sits in the library's `SectionHeader`, next to "New". Today shows its starter-pack link only while the library is empty. Tests: `test/widgets/starter_pack_entry_points_test.dart` (one per entry point, plus Meal Plan View's EMPTY_POOL panel and a non-EMPTY_POOL control).
- **Keys.** `StarterPackSheet.rowKey(id)`, `checkboxKey(id)`, `importKey`, `selectAllKey`; `RecipeLibraryScreen.starterPackKey` / `emptyStarterPackKey` / `emptyBuildKey`; `TodayScreen.starterPackKey`; `FailureViewModel.starterPackKey`. `StickyCtaAction` gained an optional `key`.
- **Validation.** `flutter analyze`: no issues. `flutter test`: 299 passed (baseline 265).
- **Not done:** the manual run against a local API with a fresh `MACROVA_DATA_DIR` (pick 5 → import → plan) and the PR screenshot.
