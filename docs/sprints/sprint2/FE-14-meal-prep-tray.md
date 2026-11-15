# FE-14 — Meal-prep tray, batch meal cards and create-batch sheet

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** FE-12 (`Recipe.isMealPrepCapable`); P0 transitively
**Supersedes:** Sprint 1 FE-3 (meal-prep tray, carried) and FE-7 (meal-prep wizard, merged and reduced to one sheet). Also the `meal_prep_batch` card variant from Sprint 1 FE-1.

## Summary

Wire the four `/api/v1/meal_prep_batches` routes into Flutter:
- an always-visible tray on Meal Plan View listing active batches, with cancel;
- a single create-batch sheet;
- meal cards that show when a planned meal comes from a batch (`source == "meal_prep_batch"`, `batch_id`, `servings`).

## Context

Follow-ups 2 and 7b. Backend (Sprint 1 DM-3/BE-2/BE-5/BE-13/BE-14, all implemented):

- `POST /api/v1/meal_prep_batches`: body `{recipe_id, total_servings ≥ 1, cook_date, assignments[{day_index, slot_index, servings}]}`. Errors: `RECIPE_NOT_FOUND`, `RECIPE_NOT_BATCHABLE` (recipe isn't meal-prep capable) and `BATCH_CONFLICT`.
- `GET /api/v1/meal_prep_batches?active=true` (default true), `GET /{batch_id}`, `DELETE /{batch_id}` (cancel).
- Response: `{id, recipe_id, total_servings, assigned_servings, remaining_servings, cook_date, status, assignments[{day_index, slot_index, servings, date, slot_id}]}`.
- `/api/v1/plan` reads active batches server-side (client `active_batches` is ignored with a warning) and returns `PlannedMeal.source/batch_id/servings`.

Flutter on `merge-frontend-redesign`: `Meal` already parses `source`, `batchId` and `servings` (`models/models.dart` ~line 441), but nothing renders them, and no code calls the batch routes.

Sprint 1 decision kept: the tray is **always visible** (never hidden when empty). With bundled data the tray starts empty and no recipe is batchable (none has the `meal-prep` tag; all have `default_servings` 1). The demo path is to mark a recipe meal-prep capable in the builder (FE-12), then create a batch here.

## Acceptance criteria

- [x] `ApiService` gains `listMealPrepBatches({bool active = true})`, `createMealPrepBatch(...)` and `cancelMealPrepBatch(id)`, with a `MealPrepBatch` DTO built from the response above. Structured errors map to `ApiException` with the server `code`. Tests with fixture JSON, including `BATCH_CONFLICT` and `RECIPE_NOT_BATCHABLE`.
  - Done: DTOs `MealPrepBatch` / `MealPrepAssignment` (`lib/models/meal_prep_batch.dart`). The list response is `{"batches": [...]}`; cancel returns `{"cancelled_id"}`. Fixtures captured from the committed backend (`test/fixtures/README.md`, "Meal-prep fixtures"); tests `test/meal_prep_api_test.dart`.
- [x] `MealPrepTray` widget at the top of Meal Plan View:
  - always rendered;
  - empty state explains meal prep and offers "+ New batch";
  - populated state lists recipe name, `remaining/total` servings and cook date, with a cancel action that confirms first;
  - collapse is user-controlled and stored with the existing `StorageService` convenience pattern, but the tray is expanded on first load.

  Widget tests: empty, populated, cancel confirm, collapse.
  - Done: `MealPrepTray` (`lib/widgets/meal_prep_tray.dart`) sits under the Meal Plan View title, also when there is no plan. A list failure shows the server code with Retry. Cancel doesn't re-run the plan (its batch meals stay until the next one; the snackbar says so). Tests `test/widgets/meal_prep_tray_test.dart`.
- [x] Create-batch sheet:
  - recipe list filtered to `isMealPrepCapable`, with a hint when none are ("Mark a recipe meal-prep capable in the Recipe Builder");
  - servings stepper (min 2);
  - cook date (defaults to today);
  - slot picker from the current plan's days and slots, which can't select more slots than servings.

  On submit it POSTs, refreshes the tray, and re-runs the plan. Copy says selected slots are fixed assignments, not preferences. On `BATCH_CONFLICT` the sheet stays open with the server message; on `RECIPE_NOT_BATCHABLE` it shows the fix. Widget tests for the overflow guard, success refresh (fake provider) and conflict message.
  - Done: `CreateBatchSheet` (`lib/widgets/create_batch_sheet.dart`, one `MacrovaSheet`, no wizard). Beyond the stub, from the backend checks below: the picker allows **one slot per day** (two on a day fail the plan with FM-3), the servings stepper can't go below the picked slots, and the sheet warns when the current plan used a selected pool without the recipe. Opening the sheet refreshes `is_meal_prep_capable` for recipes with the `meal-prep` tag, and a recipe save now invalidates its loaded detail tags (`RecipeProvider`), so the FE-12 switch → batch demo path works in one session. Re-run = `lastRequest` re-sent unchanged; for a plan-from-text result nothing is re-run and the snackbar says to generate a plan. Tests `test/widgets/create_batch_sheet_test.dart`, `test/providers/meal_plan_provider_meal_prep_test.dart`.
- [x] `MealCard` (and `MealDetailSheet`) show a batch variant when `source == "meal_prep_batch"`: a "Meal prep" badge, plus the serving count when `servings` is present. Planner meals look unchanged. Widget test per variant.
  - Done: `MealCard(source:, servings:)`, `Meal.isMealPrepBatch` and `Meal.source*` constants; wired on Meal Plan View's daily list and Today. Tests `test/widgets/meal_card_meal_prep_test.dart`, plus the captured plan rendered on Meal Plan View in `create_batch_sheet_test.dart`.
- [x] Batch state lives on an existing provider (`MealPlanProvider`) unless analysis shows a clear reason otherwise. If a new provider is unavoidable, justify it in the PR (AGENTS.md: no duplicate providers).
  - Done: `MealPlanProvider` holds the fetched list, loading/error (`mealPrepErrorCode`), tray collapse, `planSlotOptions`, and injectable `mealPrepListFn` / `mealPrepCreateFn` / `mealPrepCancelFn`. No client batch store; plan requests never carry batches.
- [x] `cd frontend && flutter analyze && flutter test` green.
  - Done: analyze clean, 236 tests passing. Not run: the manual check against a running local API with a screenshot; the in-process probe above covered create → plan → cancel on the committed backend.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `src/api/meal_prep_routes.py` (models ~lines 25–115, validation ~175–230), `src/api/server.py` (`PlannedMeal` ~line 271, plan endpoint batch hydration ~1205), `frontend/lib/models/models.dart` (`Meal`, `MealPlan`), `services/api_service.dart`, `providers/meal_plan_provider.dart`, `screens/meal_plan_view_screen.dart`, `screens/today_screen.dart`, `widgets/meal_card.dart`, `widgets/meal_detail_sheet.dart`, `widgets/macrova_sheet.dart`, `services/storage_service.dart`.
- Entities to reuse: `Meal.source/batchId/servings`, `MacrovaSheet`, `EmptyState`, `MacrovaChip`, `AdvisoryCard`.
- Do NOT create: drag-and-drop (Sprint 1 FE-2, deferred), a multi-step wizard, or a client-side batch store.

### 🧠 Pre-implementation analysis
1. `REQUIRES_VERIFICATION`: index base. Batch `assignments.day_index`/`slot_index` vs plan `daily_plans[].day` (1-based?) vs `PlannedMeal.slot_index`. Write a test that creates a batch at (0, 0) and checks it lands on the first meal of day 1 in the plan response.
2. `REQUIRES_VERIFICATION`: how batch assignments relate to the schedule Flutter sends. Batches are stored server-side by index, so an index beyond the requested schedule probably gives `FM-BATCH-CONFLICT` or FM-3. Check `phase*` and BE-2. The picker only offers slots in the current plan.
3. Decide where `cook_date` comes from relative to the plan horizon. The API validates the date format only (`_valid_cook_date`); note any semantics you find.

#### Findings (2026-11-14, committed backend `7501f26`, in-process `TestClient` probe; responses saved as fixtures)
1. Index bases: batch `day_index` / `slot_index` are **0-based**. `format_result_json` writes `daily_plans[].day = day_index + 1` (1-based) and `PlannedMeal.slot_index` = the 0-based slot; `build_planned_meal_metadata_index` keys batch metadata by the same `(day_index, slot_index)`, and `_merge_batch_locks_into_pins` turns a lock into pin key `(day_index + 1, slot_index)`. A batch at (0, 0) came back on day 1, `slot_index: 0`, `source: meal_prep_batch`, its `batch_id`, `servings: 1.0` (test: `test/meal_prep_api_test.dart`, "Index bases"). Flutter's `MealSlot.index` in the request schedule is 1-based (1, 2, 3); it is not the batch coordinate.
2. Batches vs the schedule: batches are stored by index and applied to **every** `/plan` (`hydrate_parity_plan_context`, client `active_batches` ignored). Batch locks become pins and go through `validate_pinned_assignments` (`phase1_state.py`): a slot outside the requested horizon/schedule is HC-6 and the whole plan fails with **FM-3** (probe: batch on day_index 1, 1-day plan → `failed`, FM-3). Two slots of one batch on the same day are HC-2 (same recipe twice in a day) → FM-3 too (probe confirmed), so the picker allows one slot per day. A batch recipe excluded by the request's `recipe_ids` is dropped before planning (`keep_batch_recipes` only protects against tag filters) → FM-3 (probe confirmed); the sheet warns. Two batches on one slot can't be created (`BATCH_CONFLICT` 409); FM-BATCH-CONFLICT is only reachable for stored data that bypassed the route. Pin checks HC-1/HC-3/HC-5 apply as well (e.g. a cook time over the slot's busyness cap → FM-3).
3. `cook_date`: the route validates the ISO format only. Its one use is the response's assignment `date = cook_date + day_index` (and mapping legacy `(date, slot_id)` input to `day_index`); the planner never reads it, and the plan horizon has no calendar date. The sheet defaults it to today and says plan day 1 is the cook date. Other observed semantics: `total_servings >= 2` (`BATCH_INVALID` 400 otherwise), at most `total_servings` assignments, created batches list as `status: active`, and a cancelled one is `consumed` in `?active=false`.

### ✅ Post-implementation validation
- `cd frontend && flutter analyze && flutter test`
- Manual, against a local API: mark a recipe meal-prep capable (FE-12), create a 3-serving batch on three slots, re-plan, and see three batch cards. Cancel the batch, re-plan, and they're gone. Screenshot for the PR.

## Out of scope

- Moving or detaching servings (needs an endpoint that doesn't exist).
- A "Start a batch" entry point on recipe cards (Sprint 3 if the friction log asks for it).
- Batch conflict highlighting from `FailurePanel`.
