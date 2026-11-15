# Frontend plan failure handling

How Flutter surfaces planner outcomes. Backend contracts are unchanged; the UI consumes existing `PlanResponse` fields.

**Source:** `frontend/lib/models/models.dart`, `frontend/lib/widgets/failure_view_model.dart`, `frontend/lib/widgets/failure_panel.dart`, `frontend/lib/screens/today_screen.dart`, `frontend/lib/screens/meal_plan_view_screen.dart`. Contract detail: [plan-response.md](../contracts/plan-response.md).

## Branch key: `plan_status`

UX branching uses **`plan_status`** (`success` | `partial` | `failed`), not `success` and not `termination_code`.

| `plan_status` | UI |
| --- | --- |
| `success` | Meals + optional advisories from `warnings` |
| `partial` | Meals **and** `FailurePanel` |
| `failed` | `FailurePanel` (meals usually empty) |

## Actionable failures: `report.failures[]`

`report.failures[]` (`PlanFailure`) is the source of truth for actionable planner failures. Every entry renders; none is dropped.

`FailureViewModel` maps each failure to `FailurePanel` fields:

| `PlanFailure` | `FailurePanel` |
| --- | --- |
| `code` | code chip (`terminationCode` prop) |
| `explanation` (else `message`) | headline (`cause` prop) |
| `fix` (else `fix_hint`) | fix line (`fixHint` prop) |
| `cause` | not shown (diagnosis id, informational) |

`explanation`, `fix` and `cause` come from `src/api/failure_explanations.py` and are optional; older servers send only `message` / `fix_hint`, which are the fallbacks.

### Where each failure shows

- **Slot failures** (`day_index` and `slot_index` both set, 0-based) render inline on that slot as `FailurePanel.slot` (code + headline + fix), in slot order next to the meals:
  - **Meal Plan View**, daily list: every slot failure, including days with no meals.
  - **Today**: slot failures on the plan's first day.
- **Hero panel** (`FailurePanel`, key `failure-hero`): the first remaining failure is the headline; the others are rows. "Remaining" means every failure the current view doesn't show inline: failures without a slot, slot failures on Today's later days, and all slot failures in Meal Plan View's calendar mode.
- If every failure is inline, the hero shows `plan_status_message` (label `Incomplete plan`) and points to the marked slots.

## Recipe help: `report.failure_cause`

`report.failure_cause` (`PlanFailureCause`: `cause`, `recipe_could_help`, `recipe_gap`) parses into `MealPlan.failureCause`.

- `recipe_could_help == true`: the hero panel adds one row whose description is a one-line gap summary built only from non-null `recipe_gap` fields (per-meal calories/protein/carbs/max fat, `nutrient_min_per_recipe`, `cook_time_cap_minutes`, `excluded_ingredients`), e.g. "A recipe near 650 kcal and 40 g protein would help."
  - `LlmConfigProvider.llmReady` and the plan came from `MealPlanProvider.generatePlan`: **Find a recipe** re-runs that request with `planning_mode: "assisted"` (`MealPlanProvider.rerunLastRequest`), which runs the server's diagnosed recovery loop. The saved planner mode is unchanged. A failed assisted call revokes the LLM gate, as in Planner Config.
  - Gate not ready: **Set up AI help** opens Agent Setup.
  - Gate ready but no request to re-run (plan from the Agent pane's plan-from-text): the gap summary only.
- `recipe_could_help == false` or `failure_cause` null: no recipe row.

If `plan_status != success` but `failures` is empty, use incomplete messaging from `plan_status_message` (label `Incomplete plan`).

## Warnings ≠ failures

- **Failures** → `FailurePanel` (user must act).
- **Warnings** → `AdvisoryCard` advisories **only when** `plan_status == success`.
- Do not treat success-with-warnings as a failure.
- Exception: **pre-plan sync rejections** (`MealPlan.syncWarnings`, added by `MealPlanProvider.generatePlanWithRecipeSync` via `recipeSyncWarning`) also show on `partial` / `failed` plans, as an `AdvisoryCard` (key `plan_sync_warnings`) next to the `FailurePanel`, since a rejected recipe may be why the plan failed. On success they are part of the advisories (they head `warnings`). The server's own `warnings` stay success-only.

## HTTP `ApiException` (no in-body plan)

When the provider has an error and no plan:

- If `errorCode` starts with `FM-` → `FailurePanel`.
- Else → `AdvisoryCard` (generic planning error).

Planner `FM-*` outcomes normally arrive as **HTTP 200** with `report.failures[]` (see contract doc). HTTP-mapped `FM-*` is the exception path.

## Do not

- Parse `termination_code` for UI branching (`TC-*` is telemetry only).
- Regex or scrape strings like `"Planner ended with…"`.
- Invent failure codes or fix hints not present on `PlanFailure`.
- Offer assisted re-planning outside the `LlmConfigProvider` ready gate.
