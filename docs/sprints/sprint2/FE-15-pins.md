# FE-15 — Pin and unpin a meal; pinned meal cards

**Status:** done  ·  **Complexity:** S  ·  **Depends on:** FE-14 (same files: `meal_card.dart`, `meal_detail_sheet.dart`)
**Supersedes:** the pin half of Sprint 1 FE-10 (forcing-mode UX). The tag-forcing half is deferred with Sprint 1 FE-8.

## Summary

Let the user pin the recipe in a planned slot, so re-planning keeps it, and unpin it. Show pinned meals as pinned. Explain the precedence in one line: meal prep beats pin beats tags.

## Context

Follow-up 3. Backend (Sprint 1 BE-10, implemented). Four routes:

- `GET /api/v1/profile/pins` → `{pins: [{day_index, slot_index, recipe_id}]}`
- `PUT /api/v1/profile/pins/{day_index}/{slot_index}` with body `{recipe_id}` → `{pin}`; `RECIPE_NOT_FOUND` if the recipe is unknown
- `DELETE /api/v1/profile/pins/{day_index}/{slot_index}` → `{deleted, pin}`
- `DELETE /api/v1/profile/pins` → `{cleared_count}`

`PlanRequest` has no pin field. `/api/v1/plan` reads pins from the server profile YAML (`hydrate_parity_plan_context`) and returns `PlannedMeal.source == "pinned_assignment"`. Precedence: batch lock > pin > required tags > search (AGENTS.md).

Follow-up 7c, checked 2026-11-14: pins are validated against the server YAML's `schedule_days` (`src/data_layer/user_profile.py::_validate_pin_against_schedule`) **only when the YAML has `schedule_days`**. The committed YAML has only a legacy `schedule`, so any index is accepted. At plan time, the pin is applied to the schedule Flutter sends. A pin outside that schedule is the one edge case this task must test. It's why `/api/v1/profile/schedule` doesn't need wiring this sprint.

## Acceptance criteria

- [x] `ApiService` gains `listPins()`, `pin(dayIndex, slotIndex, recipeId)`, `unpin(dayIndex, slotIndex)` and `clearPins()`, with a `ProfilePin` DTO. Tests with fixture JSON, including `RECIPE_NOT_FOUND`.
  - Done: `ProfilePin` / `ProfilePinDeleteResult` (`lib/models/profile_pin.dart`); `unpin` returns `{deleted, pin}`, `clearPins` the `cleared_count`. Fixtures captured from the committed backend (`test/fixtures/README.md`, "Pin fixtures"); tests `test/profile_pin_api_test.dart`.
- [x] `MealDetailSheet` has a Pin/Unpin action for the slot it shows, using the plan's own `(day_index, slot_index)` (0-based). Unpinned → Pin, pinned → Unpin. After either, pins are re-fetched; the plan is **not** re-run automatically (copy: "Applies next time you plan"). Widget test with a fake API.
  - Done: the coordinate is `MealPlanProvider.pinSlotFor(day, mealIndex, meal)` = `(day - 1, meal.slotIndex ?? mealIndex)`. Pin state lives on `MealPlanProvider` (`pins`, `loadPins`, `pinRecipe`, `unpinSlot`, `clearPins`, injectable `pin*Fn`s); no pins provider, no pin field on `PlanRequest`. A server error shows its code in the sheet (e.g. `RECIPE_NOT_FOUND`). The sheet fetches pins if no screen has yet; without a `MealPlanProvider` above it the action is hidden. Tests `test/widgets/meal_pin_widgets_test.dart`, `test/providers/meal_plan_provider_pins_test.dart`.
- [x] `MealCard` shows a pin badge when `source == "pinned_assignment"`, and also when a pin exists for that slot but the plan predates it. Widget test for both.
  - Done: `MealCard(hasPin:)`, key `MealCard.pinBadgeKey`: "Pinned" for `pinned_assignment`, "Pinned · next plan" for a slot pinned since the plan; never on a batch meal (meal prep wins). Wired on Meal Plan View (daily list, and the calendar, which now also passes `source`/`servings`) and Today. Meal Plan View and Planner Config fetch pins; Today shows the "next plan" badge only once pins were fetched in the session. Tests `test/widgets/meal_pin_widgets_test.dart`, `test/widgets/pinned_meals_section_test.dart` (Meal Plan View).
- [x] A batch slot (`source == "meal_prep_batch"`) shows Pin disabled with the precedence line "Meal prep overrides pins for this meal". Widget test.
  - Done: if a pin already exists on a batch slot, Unpin stays enabled (removing it is harmless). Other slots show the one-line precedence "Meal prep beats pins; pins beat tags." Test in `test/widgets/meal_pin_widgets_test.dart`.
- [x] Planner Config shows the pin count and a "Clear pins" action (confirm first). Widget test.
  - Done: `PinnedMealsSection` (`lib/widgets/planner/pinned_meals_section.dart`) under Schedule; disabled at 0 pins; a list failure shows the server code with Retry; clearing doesn't re-run the plan. Tests `test/widgets/pinned_meals_section_test.dart`.
- [x] Backend edge test (Python, `tests/api/`): a pin at a `slot_index` beyond the meals Flutter sends for that day. Assert today's actual behavior (ignored, a warning, or a failure code) and document it in this stub. If the behavior is a crash or a silent wrong-slot assignment, stop and report: that's a backend bug for its own task, not something to fix here.
  - Done: a **failure code**, not a crash or a wrong slot (finding 3 below). Tests in `tests/api/test_profile_pins.py`, on the real planner (no mocked `plan_meals`).
- [x] `cd frontend && flutter analyze && flutter test` green.
  - Done: analyze clean, 265 tests passing; `python3 scripts/run_pytest.py` 1438 passed. Not run: the manual pin → re-plan check against a running local API (the in-process capture in the findings covered pin → plan).

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `src/api/server.py` (pin DTOs ~lines 243–270, routes ~2056–2100), `src/data_layer/user_profile.py` (pin storage and validation, lines 57–160), `src/planning/orchestrator.py` (`hydrate_parity_plan_context`, `build_planned_meal_metadata_index`), `frontend/lib/services/api_service.dart`, `widgets/meal_detail_sheet.dart`, `widgets/meal_card.dart`, `screens/planner_config_screen.dart`, `providers/meal_plan_provider.dart`.
- Entities to reuse: `Meal.source`, `Meal.slotIndex`, `MealPlanProvider`.
- Do NOT create: a pin field on the Flutter `PlanRequest` (the server owns pins), or a pins provider (keep pin state on `MealPlanProvider`).

### 🧠 Pre-implementation analysis
1. `REQUIRES_VERIFICATION`: where the day index comes from. `daily_plans[].day` may be 1-based while pins are 0-based. Find the mapping the redesign uses (`MealPlanDay`) and test it.
2. `REQUIRES_VERIFICATION`: whether pin writes need a write-capable profile YAML on the server. Pins are written to `config/user_profile.yaml`, which BE-20 untracks (W7), so it may not exist on a fresh clone. Check what a pin write does when it's missing, and test it.

#### Findings (2026-11-14, committed backend `4c952e8`, in-process `TestClient`; responses saved as fixtures)
1. Index bases: pins are **0-based** `(day_index, slot_index)`, the same as batch assignments. `convert_profile` turns a pin into planner key `(day_index + 1, slot_index)`; `format_result_json` writes `daily_plans[].day = day_index + 1` and `PlannedMeal.slot_index` = the 0-based slot; `build_planned_meal_metadata_index` marks `source: pinned_assignment` at the same `(day_index, slot_index)` (a batch on that slot wins). Captured: pins (0, 1) and (1, 0), then a 2-day `/plan` → day 1 `slot_index: 1` and day 2 `slot_index: 0` are `pinned_assignment` with the pinned recipes (`plan_with_pin.json`; "Index bases" test in `test/profile_pin_api_test.dart`). Flutter's `MealSlot.index` (1-based) is not the pin coordinate; the sheet uses `(MealPlanDay.day - 1, Meal.slotIndex)`.
2. Missing profile YAML (`NUTRITION_USER_PROFILE_PATH` → absent file): `GET` lists `{"pins": []}` and creates nothing. The first `PUT` **creates the file (and its parent folder)** holding only `pins: [...]` (atomic temp-file write); the `DELETE` routes do the same (`pins: []`). `/plan` takes its targets from the request and reads only `pins` from the YAML, so a pins-only file plans fine and the pin is applied (`test_pin_write_without_a_profile_yaml_creates_a_pins_only_file`). A write needs the YAML's folder to be writable; there is no dedicated error code for that (an OS error goes through `map_exception_to_api_error`; not exercised). With no `schedule_days` in the YAML, any index is accepted on `PUT`.
3. Edge: a stored pin at a `slot_index` past the meals the request sends for that day (pin (0, 5), 1-day 2-meal request). The `PUT` succeeds. `/plan` returns 200 with `success: false`, `plan_status: failed`, `termination_code: TC-2`, and one `report.failures[]` entry: `code: FM-3`, `day_index: 0`, `slot_index: 5`, `cause: PIN_OR_BATCH_CONFLICT`, `details.recipe_id` = the pinned recipe (`validate_pinned_assignments`, HC-6). Nothing is placed, so the pin isn't moved to another slot; it isn't ignored and doesn't crash. Unpinning makes the same request plan again (`test_pin_beyond_the_requested_days_meals_fails_the_plan_with_fm3_failure`; control `test_pin_in_range_is_placed_on_its_own_slot`). The same check covers a pin on a day past the requested horizon. So a pin made on a 3-meal plan fails a later 2-meal plan until it's unpinned; Planner Config's "Clear pins" is the way out (no schedule wiring this sprint).

### ✅ Post-implementation validation
- `cd frontend && flutter analyze && flutter test`; `python3 scripts/run_pytest.py` for the edge test
- Manual: pin a lunch, re-plan, the same recipe stays in that slot; unpin, re-plan, it can change.

## Out of scope

- Tag-forcing mode and the slot config editor (Sprint 1 FE-8/FE-10 rest, deferred).
- Wiring `/api/v1/profile/schedule`.
- Recurring pins.
