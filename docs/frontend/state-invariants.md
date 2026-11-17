# Frontend plan state invariants

Invariants for meal-plan UI state after integrity remediation. Reuse existing providers/DTOs — no parallel models.

## `MealPlanProvider`

- Surface HTTP/API errors via **`errorCode`** + **`errorMessage`** (and legacy `error` string). `ApiException.code` populates `errorCode`.
- **`clearPlan()`** nulls the plan, clears errors, and clears local cooked slots.
- Successful `generatePlan` / `applyPlanResult` also clear cooked slots so mark-cooked state does not leak across plans.
- **`lastRequest`** is the `PlanRequest` behind the current plan when it came from `generatePlan`; `applyPlanResult` (plan-from-text) and `clearPlan()` null it. `rerunLastRequest(planningMode:)` re-sends it with another mode (FE-11 "Find a recipe"); it does not change the saved `planningMode`.

## Nutrition authority on planner surfaces

On Today / Meal Plan View / meal cards driven by a plan, display **`meal.nutrition`** from the plan response (and day/plan totals from the same payload). Do not recompute macros from local recipe ingredient lines for those surfaces. Library/builder may still use local recipe nutrition.

`RecipeCard` accepts optional `plannerCalories` / `plannerProteinG` / … overrides for plan heroes.

## No duplicate models

- One `MealPlan` / `PlanFailure` / `Meal` parse path in `frontend/lib/models/models.dart` aligned with OpenAPI.
- Do not add a second failure DTO or parallel plan provider.

## Agent `planFromText` pool filters

`AgentPaneScreen` must send the same pool filters as `/plan`:

`cuisine`, `cost_level`, `prep_time_bucket`, `dietary_flags` (plus `ingredient_source` / `planning_mode`) from `MealPlanProvider`.

## Meal-prep batches (FE-14)

- Batches are **server-owned** (`/api/v1/meal_prep_batches`). `MealPlanProvider` keeps only the last fetched active list (`mealPrepBatches`, `loadMealPrepBatches`) for the Meal Plan View tray and the create-batch sheet. There is no client batch store, and `PlanRequest` never carries `active_batches` (the server ignores them anyway and applies its own active batches to every `/plan`).
- `createMealPrepBatch` POSTs, reloads the list, then re-sends `lastRequest` unchanged (no re-run for a plan-from-text result). `cancelMealPrepBatch` DELETEs and reloads; it does not re-run the plan.
- Batch coordinates are 0-based `(day_index, slot_index)`; the plan shows them as `daily_plans[].day == day_index + 1` and `Meal.slotIndex == slot_index`. Meals placed from a batch have `Meal.source == "meal_prep_batch"` (`Meal.isMealPrepBatch`), `batchId` and `servings`; `MealCard` / `MealDetailSheet` show a "Meal prep" badge for them.
- Batches persist across plans. A batch slot outside the requested horizon or schedule, two slots on the same day, or a batch recipe left out of a selected `recipe_ids` pool all fail the plan with FM-3 (pinned-assignment validation); the sheet offers one slot per day from the current plan and warns about the pool case.
- Tray collapse is device-local (`StorageService` `meal_prep_tray_collapsed`, expanded by default).

## Pins (FE-15)

- Pins are **server-owned** (`/api/v1/profile/pins`, kept in the server's profile YAML; the first write creates that file). `MealPlanProvider` keeps only the last fetched list (`pins`, `pinCount`, `pinAt`, `loadPins`, `pinsErrorCode`). There is no pins provider, and `PlanRequest` never carries pins: the server applies its own to every `/plan`.
- Pin coordinates are 0-based `(day_index, slot_index)`, like batches. A planned meal's coordinate is `MealPlanProvider.pinSlotFor(day, mealIndex, meal)` = `(day - 1, meal.slotIndex ?? mealIndex)`. Flutter's request `MealSlot.index` (1-based) is not it.
- `pinRecipe` / `unpinSlot` / `clearPins` change the server, then re-fetch `pins`. None re-runs the plan ("Applies next time you plan").
- `MealCard(hasPin:)` shows "Pinned" for `Meal.source == pinned_assignment` and "Pinned · next plan" for a slot pinned since the plan; never on a batch meal. `MealDetailSheet` disables Pin on a batch slot ("Meal prep overrides pins for this meal"). Precedence: meal-prep batch → pin → required tags → preferred scoring.
- A stored pin outside the requested schedule (a slot or day the request doesn't have) fails the plan with FM-3 (`PIN_OR_BATCH_CONFLICT`), shown through `FailurePanel`. The fix is to unpin it or use "Clear pins" (Planner Config).

## Starter pack (FE-16)

- The starter pack is **server-owned** (`GET /api/v1/starter_recipes`, built from `data/recipes/recipes.json.example`). `RecipeProvider` keeps only the last fetched list (`starterRecipes`, `loadStarterRecipes`, `starterError`); there is no client copy and no bundled recipe asset.
- `RecipeProvider.importStarterRecipes(ids)` POSTs `/api/v1/starter_recipes/import`, then refreshes `GET /api/v1/recipes`. Imported recipes are ordinary server recipes (id + name rows until opened); nothing is written to device storage, so the pre-plan sync doesn't resend them. Per-id skips (`already_in_pool`, `not_a_starter_recipe`) come back in the result; a whole-request failure throws.
- Nothing is imported without the user's tap: the sheet pre-selects nothing, and recipes already in the library (`libraryRecipeIds`: local or server ids) can't be ticked.
- `/plan` without `recipe_ids` (no Planner Config selection) plans with the whole server pool, imports included. With a selection, imports join the plan only once ticked there; the sheet's snackbar says so.
- Entry points: Recipe Library empty state and header action, Today's no-plan state (while the library is empty), and the `EMPTY_POOL` failure row.

## Demographic ULs (BE-17)

- `UserProfile.demographicGroup` is one of `UserProfile.supportedDemographics` (`adult_male`, `adult_female`, `pregnancy`, `lactation`: the server's `demographic` literal) or `''` ("Not set"). `fromJson` / `fromRepoYamlMap` normalize anything else (a saved `teen_*`, `child`, `elderly_*`) to `''` via `UserProfile.normalizeDemographic`.
- `UserProfile.planDemographic` (null when not set) is what requests send: `PlanRequest.demographic` from Planner Config, and `planFromTextBody(..., demographic:)` for the Agent pane. `PlanRequest.toJson` and `planFromTextBody` also drop unsupported values, so an unsupported value is never sent (the server would answer 400 `INVALID_REQUEST`).
- The server enforces that demographic's daily ULs. It does not set micronutrient goals; `withPlanningMode` (and so `rerunLastRequest`) keeps the demographic.

## Micronutrient default for new users (BE-20)

- The default is **server-owned** (`GET /api/v1/micronutrient_defaults?demographic=...`, read-only, D-A). `ProfileProvider.loadMicronutrientDefaults` fetches it once per demographic and caches it (`micronutrientDefaultsFor`, `micronutrientDefaultsLoading`, `micronutrientDefaultsError`; a call after a failure retries). There is no client copy of the values, and the provider never writes them into `profile`.
- The Profile screen fills the goal fields and τ from it only when the user has no goals of their own: every goal field is empty or zero, or still holds a default the user hasn't edited. That happens when the screen opens with a saved demographic and no goals, and when a demographic is picked. Goals the user typed or saved are never replaced, on any demographic change. "Not set" fetches nothing and leaves the fields as they are. A response that arrives after the user picked another demographic or typed a goal is not applied.
- Saved goals count as the user's own, even if they came from the default. To start over from another demographic's default, clear the goal fields and pick it again.
- While loading, the screen shows a hint; on failure, a notice with Retry, and the fields stay as they were (no fallback values). After applying, a line names the left-out nutrients (`micronutrientLabelForKey`) and says to enter a value to add one back.
- Nothing reaches the server until the user saves and plans; `PlanRequest.micronutrient_goals` / `micronutrient_weekly_min_fraction` then carry the saved (possibly edited) values. `/api/v1/plan` itself never applies the default.

## Toast / success snackbar

Show a success toast for NL plan generation **only when** `plan.success == true` (see `agent_pane_screen.dart`). Partial/failed in-body plans still call `applyPlanResult` and navigate; they must not claim success via toast.

## Related

- [failure-handling.md](failure-handling.md)
- [plan-response.md](../contracts/plan-response.md)
