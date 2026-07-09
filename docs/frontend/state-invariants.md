# Frontend plan state invariants

Invariants for meal-plan UI state after integrity remediation. Reuse existing providers/DTOs — no parallel models.

## `MealPlanProvider`

- Surface HTTP/API errors via **`errorCode`** + **`errorMessage`** (and legacy `error` string). `ApiException.code` populates `errorCode`.
- **`clearPlan()`** nulls the plan, clears errors, and clears local cooked slots.
- Successful `generatePlan` / `applyPlanResult` also clear cooked slots so mark-cooked state does not leak across plans.

## Nutrition authority on planner surfaces

On Today / Meal Plan View / meal cards driven by a plan, display **`meal.nutrition`** from the plan response (and day/plan totals from the same payload). Do not recompute macros from local recipe ingredient lines for those surfaces. Library/builder may still use local recipe nutrition.

`RecipeCard` accepts optional `plannerCalories` / `plannerProteinG` / … overrides for plan heroes.

## No duplicate models

- One `MealPlan` / `PlanFailure` / `Meal` parse path in `frontend/lib/models/models.dart` aligned with OpenAPI.
- Do not add a second failure DTO or parallel plan provider.

## Agent `planFromText` pool filters

`AgentPaneScreen` must send the same pool filters as `/plan`:

`cuisine`, `cost_level`, `prep_time_bucket`, `dietary_flags` (plus `ingredient_source` / `planning_mode`) from `MealPlanProvider`.

## Toast / success snackbar

Show a success toast for NL plan generation **only when** `plan.success == true` (see `agent_pane_screen.dart`). Partial/failed in-body plans still call `applyPlanResult` and navigate; they must not claim success via toast.

## Related

- [failure-handling.md](failure-handling.md)
- [plan-response.md](../contracts/plan-response.md)
