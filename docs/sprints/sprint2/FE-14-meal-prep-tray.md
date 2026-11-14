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

- [ ] `ApiService` gains `listMealPrepBatches({bool active = true})`, `createMealPrepBatch(...)` and `cancelMealPrepBatch(id)`, with a `MealPrepBatch` DTO built from the response above. Structured errors map to `ApiException` with the server `code`. Tests with fixture JSON, including `BATCH_CONFLICT` and `RECIPE_NOT_BATCHABLE`.
- [ ] `MealPrepTray` widget at the top of Meal Plan View:
  - always rendered;
  - empty state explains meal prep and offers "+ New batch";
  - populated state lists recipe name, `remaining/total` servings and cook date, with a cancel action that confirms first;
  - collapse is user-controlled and stored with the existing `StorageService` convenience pattern, but the tray is expanded on first load.

  Widget tests: empty, populated, cancel confirm, collapse.
- [ ] Create-batch sheet:
  - recipe list filtered to `isMealPrepCapable`, with a hint when none are ("Mark a recipe meal-prep capable in the Recipe Builder");
  - servings stepper (min 2);
  - cook date (defaults to today);
  - slot picker from the current plan's days and slots, which can't select more slots than servings.

  On submit it POSTs, refreshes the tray, and re-runs the plan. Copy says selected slots are fixed assignments, not preferences. On `BATCH_CONFLICT` the sheet stays open with the server message; on `RECIPE_NOT_BATCHABLE` it shows the fix. Widget tests for the overflow guard, success refresh (fake provider) and conflict message.
- [ ] `MealCard` (and `MealDetailSheet`) show a batch variant when `source == "meal_prep_batch"`: a "Meal prep" badge, plus the serving count when `servings` is present. Planner meals look unchanged. Widget test per variant.
- [ ] Batch state lives on an existing provider (`MealPlanProvider`) unless analysis shows a clear reason otherwise. If a new provider is unavoidable, justify it in the PR (AGENTS.md: no duplicate providers).
- [ ] `cd frontend && flutter analyze && flutter test` green.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `src/api/meal_prep_routes.py` (models ~lines 25–115, validation ~175–230), `src/api/server.py` (`PlannedMeal` ~line 271, plan endpoint batch hydration ~1205), `frontend/lib/models/models.dart` (`Meal`, `MealPlan`), `services/api_service.dart`, `providers/meal_plan_provider.dart`, `screens/meal_plan_view_screen.dart`, `screens/today_screen.dart`, `widgets/meal_card.dart`, `widgets/meal_detail_sheet.dart`, `widgets/macrova_sheet.dart`, `services/storage_service.dart`.
- Entities to reuse: `Meal.source/batchId/servings`, `MacrovaSheet`, `EmptyState`, `MacrovaChip`, `AdvisoryCard`.
- Do NOT create: drag-and-drop (Sprint 1 FE-2, deferred), a multi-step wizard, or a client-side batch store.

### 🧠 Pre-implementation analysis
1. `REQUIRES_VERIFICATION`: index base. Batch `assignments.day_index`/`slot_index` vs plan `daily_plans[].day` (1-based?) vs `PlannedMeal.slot_index`. Write a test that creates a batch at (0, 0) and checks it lands on the first meal of day 1 in the plan response.
2. `REQUIRES_VERIFICATION`: how batch assignments relate to the schedule Flutter sends. Batches are stored server-side by index, so an index beyond the requested schedule probably gives `FM-BATCH-CONFLICT` or FM-3. Check `phase*` and BE-2. The picker only offers slots in the current plan.
3. Decide where `cook_date` comes from relative to the plan horizon. The API validates the date format only (`_valid_cook_date`); note any semantics you find.

### ✅ Post-implementation validation
- `cd frontend && flutter analyze && flutter test`
- Manual, against a local API: mark a recipe meal-prep capable (FE-12), create a 3-serving batch on three slots, re-plan, and see three batch cards. Cancel the batch, re-plan, and they're gone. Screenshot for the PR.

## Out of scope

- Moving or detaching servings (needs an endpoint that doesn't exist).
- A "Start a batch" entry point on recipe cards (Sprint 3 if the friction log asks for it).
- Batch conflict highlighting from `FailurePanel`.
