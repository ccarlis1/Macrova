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

## Toast / success snackbar

Show a success toast for NL plan generation **only when** `plan.success == true` (see `agent_pane_screen.dart`). Partial/failed in-body plans still call `applyPlanResult` and navigate; they must not claim success via toast.

## Related

- [failure-handling.md](failure-handling.md)
- [plan-response.md](../contracts/plan-response.md)
