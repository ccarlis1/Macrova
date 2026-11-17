# Frontend — Flutter client over the /api/v1 planner, with device-local profile and library state

Status: implemented · Code: `frontend/lib/`, `frontend/test/` · Facts: [generated/frontend.md](generated/frontend.md)

## Purpose
The Flutter app is a thin client for the FastAPI backend: it edits a profile, ingredients and recipes, builds a `PlanRequest`, and renders the planner's `PlanResponse`, including structured failures. State management is `provider` (`ChangeNotifier`s); there is no Riverpod, GetIt or code generation. The server owns planning, pins, meal-prep batches, the tag registry and the starter pack; the device owns the profile, saved ingredients, locally authored recipes, cooked slots and favorites.

## Entry points
- `frontend/lib/main.dart` — constructs the six providers, awaits their `load()` calls in order (profile → meal plan → LLM gate → ingredients → recipes → server recipe summaries), then `runApp(MacrovaApp)`.
- `frontend/lib/widgets/app_shell.dart::AppShell` — `IndexedStack` of tabs; sidebar rail at ≥760 px, bottom `NavigationBar` below. Nav order (index): Today 0, Profile 1, Ingredients 2, Recipe Builder 3, Library 4, Planner 5, Plan View 6, Agent 7.
- Screens, in nav order: `frontend/lib/screens/today_screen.dart`, `frontend/lib/screens/profile_screen.dart`, `frontend/lib/screens/ingredient_hub_screen.dart`, `frontend/lib/screens/recipe_builder_screen.dart`, `frontend/lib/screens/recipe_library_screen.dart`, `frontend/lib/screens/planner_config_screen.dart`, `frontend/lib/screens/meal_plan_view_screen.dart`.
- Agent tab: `frontend/lib/features/agent/agent_pane_screen.dart::AgentPaneScreen` when the LLM gate is ready, otherwise `frontend/lib/features/agent/agent_setup_screen.dart`.
- Commands, run from `frontend/`: `flutter pub get`, `flutter analyze`, `flutter test`. API base URL: `--dart-define=API_BASE_URL=...` (default `http://localhost:8000`).

## How it works
**Provider graph.** `ProfileProvider` owns `UserProfile` (device storage) and caches GET /micronutrient_defaults. `MealPlanProvider` owns planner config (days, schedule, pool selection, pool filters, `planning_mode`, `ingredient_source`), the current `MealPlan`, error code/message, `lastRequest`, the last-fetched pins and meal-prep batches, and cooked slots. `RecipeProvider` owns local recipes, server summaries, sync rejections, server tag details, the tag registry, the starter list and favorites. `IngredientProvider` owns saved ingredients (device only). `RecipeBuilderCoordinator` hands a one-shot create/edit action from Library to Builder (siblings in the `IndexedStack`). `LlmConfigProvider` is the LLM gate. HTTP goes through static `ApiService` methods, called by providers through injectable function fields (`planFn`, `recipeSyncFn`, `pinListFn`, ...) so tests can fake them. Two screens call `ApiService` directly for one-shot lookups: Recipe Builder (`nutritionSummary`) and Ingredient Hub (`searchIngredients`, `resolveIngredientJson`). LLM endpoints go through `AgentApi`.

**Plan flow.** `PlannerConfigScreen._generate` builds a `PlanRequest` → `MealPlanProvider.generatePlanWithRecipeSync` POSTs local recipes to /recipes/sync first (rejections become `syncWarnings`), then `generatePlan` → `ApiService.plan` → `MealPlan.fromPlanApiV1Response`. A 200 response is branched on `planStatus` (`success | partial | failed`); `FailureViewModel.fromMealPlan` turns `report.failures[]` into a hero `FailurePanel` plus per-slot rows (Today and Plan View). A non-200 response becomes an `ApiException` whose envelope `code` lands in `MealPlanProvider.errorCode`; Today shows envelope `FM-*` codes in a `FailurePanel`. The "Find a recipe" action re-sends `lastRequest` with `planning_mode: assisted` (`MealPlanProvider.rerunLastRequest`); an `EMPTY_POOL` cause offers the starter pack instead.

**LLM gate.** `LlmConfigProvider.llmReady` is true only when the profile key passes a local shape check and GET /llm/status reports `enabled`. The key is never sent to the API. If the gate is not ready, assisted modes fall back to `deterministic` at boot and on Planner Config, the Agent tab shows setup, and the Builder and Hub LLM actions are hidden or no-ops. A failing agentic call calls `revokeReady`.

**Storage.** `StorageService` wraps `shared_preferences`: profile, planner config, ingredients, local recipes, `cooked_slots`, `favorite_recipe_ids`, tray-collapsed flag. Cooked slots are cleared on every new plan. Favorites are not planner tags.

**Starter pack.** `StarterPackSheet` → `RecipeProvider.importStarterRecipes` POSTs /starter_recipes/import, then refreshes GET /recipes; nothing is written to the device. Entry points: Library, Today's empty state, and the `EMPTY_POOL` failure row.

**Meal prep and pins.** Both are server-owned. `MealPlanProvider.createMealPrepBatch` POSTs, reloads the list and re-sends `lastRequest`. Pin edits re-fetch the pin list but don't re-plan. `PlanRequest` carries neither, because the server applies its own on every /plan.

## Modules
| Module | Role | Status |
|---|---|---|
| `frontend/lib/main.dart`, `frontend/lib/widgets/app_shell.dart` | Boot order, `MultiProvider`, responsive nav | implemented |
| `frontend/lib/screens/` | Seven tabs; Planner builds requests, Today/Plan View render results | implemented |
| `frontend/lib/features/agent/` | Agent pane (plan-from-text, ingredient match, validated generation), setup, gate, `AgentApi` | implemented, gated |
| `frontend/lib/providers/` | The only state owners (five providers plus the gate in features/agent) | implemented |
| `frontend/lib/models/` | Hand-written DTOs mirroring OpenAPI; `models.dart` holds plan request/response | implemented |
| `frontend/lib/services/` | `ApiService` (HTTP + error envelope), `StorageService` (device prefs) | implemented |
| `frontend/lib/theme/` | `AppTheme` light/dark and `MacrovaTokens` design tokens | implemented |
| `frontend/lib/widgets/` | Shared UI; failure surfaces; meal-prep tray and sheet; starter sheet | implemented |
| `frontend/lib/widgets/planner/` | Pinned-meals and pool-filter sections of Planner Config | implemented |
| `frontend/lib/widgets/meal_plan_calendar.dart` | Plan-horizon day strip on Plan View, not a Gregorian month grid | partial |
| Ingredient Hub "Add to Recipe" | Shows a snackbar pointing to Recipe Builder | partial |
| Slot-level tag editors | `required_tag_slugs` / `preferred_tag_slugs` round-trip in the DTO, but no UI edits them | out of scope |
| `frontend/test/` | Root: DTO/API contract tests on JSON fixtures (`frontend/test/fixtures/`); `frontend/test/providers/`, `frontend/test/screens/`, `frontend/test/widgets/` mirror `frontend/lib/` | implemented |

## Key types
- `frontend/lib/providers/meal_plan_provider.dart::MealPlanProvider` — planner config, current plan, errors, pins, batches, cooked slots.
- `frontend/lib/providers/recipe_provider.dart::RecipeProvider` — local and server recipes, sync errors, tag registry, starter pack, favorites.
- `frontend/lib/providers/profile_provider.dart::ProfileProvider` — device profile, micronutrient defaults cache.
- `frontend/lib/features/agent/llm_config_provider.dart::LlmConfigProvider` — LLM-ready gate, `isAssistedPlanningMode`.
- `frontend/lib/models/models.dart::PlanRequest` — /plan body; `withPlanningMode` copies every field.
- `frontend/lib/models/models.dart::MealPlan` — parsed `PlanResponse`: `planStatus`, `failures`, `dailyPlans`.
- `frontend/lib/models/models.dart::PlanFailure` — one `report.failures[]` entry (code, slot, fix hint, cause).
- `frontend/lib/services/api_service.dart::ApiService` — every non-agent backend call; `baseUrl`.
- `frontend/lib/services/api_service.dart::ApiException` — parses the `{"error":{"code","message"}}` envelope.
- `frontend/lib/widgets/failure_view_model.dart::FailureViewModel` — maps failures to panel, rows and actions.
- `frontend/lib/widgets/failure_panel.dart::FailurePanel` — the one failure UI.
- `frontend/lib/services/storage_service.dart::StorageService` — all `shared_preferences` keys except the gate fingerprint.

## Invariants
1. No duplicate providers or DTOs: one plan/failure parse path in `frontend/lib/models/models.dart`, one owner per state. Enforced by review and `docs/frontend/state-invariants.md`; no automated check.
2. Plan UX branches on `MealPlan.planStatus` and `report.failures`, never on `termination_code`. Enforced in `frontend/lib/screens/meal_plan_view_screen.dart` and `frontend/lib/widgets/failure_view_model.dart::FailureViewModel.fromMealPlan`. Guarded by `frontend/test/widgets/plan_failure_surfaces_test.dart` and `frontend/test/plan_failure_dto_test.dart`.
3. Assisted modes require `LlmConfigProvider.llmReady`, with a fallback to `deterministic`. Enforced in `frontend/lib/main.dart`, `frontend/lib/screens/planner_config_screen.dart::PlannerConfigScreen` and `frontend/lib/widgets/app_shell.dart::AppShellState`. Guarded by `frontend/test/widgets/agent_pane_test.dart` and `frontend/test/screens/planner_config_screen_test.dart`.
4. Pins, batches, starter recipes and the tag registry are server-owned, and `PlanRequest` never carries pins or batches. Enforced by `frontend/lib/models/models.dart::PlanRequest`. Guarded by `frontend/test/providers/meal_plan_provider_pins_test.dart` and `frontend/test/providers/meal_plan_provider_meal_prep_test.dart`.
5. Cooked slots and favorites stay on the device and cooked slots reset on each new plan. Enforced in `frontend/lib/providers/meal_plan_provider.dart::MealPlanProvider` and `frontend/lib/services/storage_service.dart::StorageService`. Guarded by `frontend/test/providers/meal_plan_provider_cooked_test.dart` and `frontend/test/providers/recipe_provider_favorites_test.dart`.
6. Unsupported `demographic` values are never sent. Enforced by `frontend/lib/models/user_profile.dart::UserProfile` normalization. Guarded by `frontend/test/plan_request_demographic_test.dart`.

## Depends on / used by
Depends only on the /api/v1 routes (see [generated/routes.md](generated/routes.md); per-call table in [generated/frontend.md](generated/frontend.md)) and on `frontend/assets/dev/cached_ingredients.json`, which is merged only with `--dart-define=BUNDLE_CACHED_INGREDIENTS=true`. Nothing in the repo imports the app. The backend `openapi/openapi.json` is the contract the DTOs mirror by hand.

## Known gaps and traps
- CI never runs Flutter. The Stop hook (`.claude/hooks/verify_stop.py`) runs `flutter analyze` and `flutter test` when `frontend/` is dirty and `flutter` is on PATH. On some machines `flutter test` rewrites `frontend/pubspec.lock`, so restore it before committing.
- Plan and tag fixtures in `frontend/test/fixtures/` are hand-captured backend responses (see its README). A backend contract change does not fail Flutter tests until someone re-captures them.
- `RecipeProvider.deleteRecipe` only removes the device copy, and no screen calls it. The server pool keeps synced recipes even though DELETE /api/v1/recipes/{id} exists.
- `AgentApi` posts with raw `http` and reuses `ApiService.baseUrl`/`ApiException`, so agent calls bypass `ApiService` and its test `client` hooks.
- `LlmConfigProvider` writes its fingerprint to `shared_preferences` directly, outside `StorageService`.
- Nav indices are hard-coded (`AppShellState._onDestinationSelected` checks index 3, and `FailureViewModel.agentNavIndex` is 7). Inserting a tab means updating them.
