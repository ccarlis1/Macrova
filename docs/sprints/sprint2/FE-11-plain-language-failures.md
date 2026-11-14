# FE-11 — Plain-language failure panel per failing slot

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** P0 (PR #63 merged)
**Supersedes:** Sprint 1 FE-9 (failure surfaces)

## Summary

Show each `report.failures[]` entry's `explanation`, `fix` and `cause`, and `report.failure_cause` (`recipe_could_help`, `recipe_gap`), on Today and Meal Plan View. For each failing slot: the FM code, a one-line fix, and a "find a recipe" action when a recipe could help.

## Context

Follow-up 1. The backend has added plain-language fields since the redesign was written (`src/api/failure_explanations.py`, PR #61 era):

- `PlanFailure`: `explanation`, `fix` and `cause` (all optional), next to `code`, `message`, `fix_hint`, `day_index`, `slot_index`.
- `PlanReport.failure_cause`: `{cause, recipe_could_help, recipe_gap{per_meal_calories, per_meal_protein_g, per_meal_fat_g_max, per_meal_carbs_g, cook_time_cap_minutes, excluded_ingredients, nutrient_min_per_recipe, meal_types, slots[[day, slot]]}}`.

Flutter on `merge-frontend-redesign`:
- `PlanFailure` (`frontend/lib/models/models.dart` ~line 403) parses `code`, `message`, `fix_hint` and the slot fields only.
- `FailureViewModel.fromMealPlan` (`widgets/failure_view_model.dart`) shows only `failures.first`, mapping `message` → cause.
- `FailurePanel` supports `fixes: List<FailureFixRow>` and `hardestConstraint`, which nothing fills.

Sprint 1 UX rule, carried from FE-9: per failing slot, show the FM code, a one-line fix, and LLM help. FE-6 (LLM suggest sheet) is deferred, because AI-1 and AI-2 aren't done. The LLM help here is the existing `planning_mode: "assisted"` re-plan, which runs the diagnosed recovery loop (`plan_with_llm_feedback`) behind the existing LLM-ready gate.

## Acceptance criteria

- [x] `PlanFailure` parses `explanation`, `fix` and `cause`. `MealPlan` parses `report.failure_cause` into a new `PlanFailureCause` DTO with a `PlanRecipeGap`. Unknown keys are ignored, and missing fields are null. Test: `test/plan_failure_dto_test.dart` with a fixture taken from a real `/api/v1/plan` failure response (commit the fixture under `test/fixtures/`).
- [x] `FailurePanel` headline is `explanation` when present (falling back to `message`); the fix line is `fix` (falling back to `fix_hint`); the code chip shows `code`. Widget test: a fixture with both explanation and message renders the explanation and not the message.
- [x] Every failure renders, not just the first. A failure with `day_index`/`slot_index` is shown on that slot in Meal Plan View (and on Today, when it is that day) as an inline failure row with code + fix. A failure with no slot appears in the hero panel. Widget test with two slot failures on different slots.
- [x] When `failure_cause.recipe_could_help == true`:
  - The panel shows a one-line gap summary built only from non-null `recipe_gap` fields (for example "A recipe near 650 kcal and 40 g protein would help").
  - If `LlmConfigProvider` reports ready, it shows a "Find a recipe" button that re-runs the same plan request with `planning_mode: "assisted"`.
  - If not ready, it shows the gap summary and a "Set up AI help" link to Agent Setup instead.
  - Widget tests cover the ready and not-ready cases. In the ready case, assert `MealPlanProvider` was called with `assisted`, using a fake provider.
- [x] When `recipe_could_help == false` (or `failure_cause` is null), no recipe button is shown. Test.
- [x] Success-with-warnings still renders `AdvisoryCard`, not `FailurePanel` (regression test; `docs/frontend/failure-handling.md` invariant).
- [x] No parsing of `termination_code` for UX (AGENTS.md). A grep check in review is enough.
- [x] `docs/frontend/failure-handling.md` updated with the field mapping.
- [x] `cd frontend && flutter analyze && flutter test` green.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `frontend/lib/models/models.dart` (`PlanFailure`, `MealPlan`), `widgets/failure_view_model.dart`, `widgets/failure_panel.dart`, `screens/today_screen.dart` (~lines 136, 211, 559), `screens/meal_plan_view_screen.dart` (~line 110), `providers/meal_plan_provider.dart` (`planning_mode` handling ~lines 84, 233, 283), `features/agent/llm_config_provider.dart`, `docs/frontend/failure-handling.md`, `src/api/server.py` (`PlanFailure`, `PlanFailureCause`, `PlanRecipeGap`, ~line 310).
- Entities to reuse: `FailurePanel` (use its `fixes` rows), `FailureViewModel`, `AdvisoryCard`, `MealPlanProvider`'s existing plan call. No new provider.
- Do NOT create: a second failure widget, or a parallel DTO for failures.

### 🧠 Pre-implementation analysis
1. Capture a real failing response for the fixture: POST the committed profile's request (see BE-16 for the probe) to a local server and save the JSON. Make sure it has `explanation`, `fix`, `cause` and `failure_cause`.
2. `REQUIRES_VERIFICATION`: how `MealPlanProvider` exposes "re-run last request with a different mode". If it can't, add one method; don't duplicate the request builder.
3. `REQUIRES_VERIFICATION`: whether `assisted` mode is reachable from the UI today (the comment at `meal_plan_provider.dart:84` says to keep deterministic "until assisted UX is gated"). This task is that gate. Use the existing LLM-ready check.

### ✅ Post-implementation validation
- `cd frontend && flutter analyze && flutter test`
- Manual: run the API locally, plan with an impossible `max_daily_calories`, and screenshot Today and Meal Plan View for the PR.

## Out of scope

- The LLM suggest sheet (Sprint 1 FE-6, deferred).
- Backend changes to explanation text.
- Batch/pin conflict highlighting in the tray (FE-14 and FE-15 may link to it later).
