# FE-15 — Pin and unpin a meal; pinned meal cards

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** FE-14 (same files: `meal_card.dart`, `meal_detail_sheet.dart`)
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

- [ ] `ApiService` gains `listPins()`, `pin(dayIndex, slotIndex, recipeId)`, `unpin(dayIndex, slotIndex)` and `clearPins()`, with a `ProfilePin` DTO. Tests with fixture JSON, including `RECIPE_NOT_FOUND`.
- [ ] `MealDetailSheet` has a Pin/Unpin action for the slot it shows, using the plan's own `(day_index, slot_index)` (0-based). Unpinned → Pin, pinned → Unpin. After either, pins are re-fetched; the plan is **not** re-run automatically (copy: "Applies next time you plan"). Widget test with a fake API.
- [ ] `MealCard` shows a pin badge when `source == "pinned_assignment"`, and also when a pin exists for that slot but the plan predates it. Widget test for both.
- [ ] A batch slot (`source == "meal_prep_batch"`) shows Pin disabled with the precedence line "Meal prep overrides pins for this meal". Widget test.
- [ ] Planner Config shows the pin count and a "Clear pins" action (confirm first). Widget test.
- [ ] Backend edge test (Python, `tests/api/`): a pin at a `slot_index` beyond the meals Flutter sends for that day. Assert today's actual behavior (ignored, a warning, or a failure code) and document it in this stub. If the behavior is a crash or a silent wrong-slot assignment, stop and report: that's a backend bug for its own task, not something to fix here.
- [ ] `cd frontend && flutter analyze && flutter test` green.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `src/api/server.py` (pin DTOs ~lines 243–270, routes ~2056–2100), `src/data_layer/user_profile.py` (pin storage and validation, lines 57–160), `src/planning/orchestrator.py` (`hydrate_parity_plan_context`, `build_planned_meal_metadata_index`), `frontend/lib/services/api_service.dart`, `widgets/meal_detail_sheet.dart`, `widgets/meal_card.dart`, `screens/planner_config_screen.dart`, `providers/meal_plan_provider.dart`.
- Entities to reuse: `Meal.source`, `Meal.slotIndex`, `MealPlanProvider`.
- Do NOT create: a pin field on the Flutter `PlanRequest` (the server owns pins), or a pins provider (keep pin state on `MealPlanProvider`).

### 🧠 Pre-implementation analysis
1. `REQUIRES_VERIFICATION`: where the day index comes from. `daily_plans[].day` may be 1-based while pins are 0-based. Find the mapping the redesign uses (`MealPlanDay`) and test it.
2. `REQUIRES_VERIFICATION`: whether pin writes need a write-capable profile YAML on the server. Pins are written to `config/user_profile.yaml`, which BE-20 untracks (W7), so it may not exist on a fresh clone. Check what a pin write does when it's missing, and test it.

### ✅ Post-implementation validation
- `cd frontend && flutter analyze && flutter test`; `python3 scripts/run_pytest.py` for the edge test
- Manual: pin a lunch, re-plan, the same recipe stays in that slot; unpin, re-plan, it can change.

## Out of scope

- Tag-forcing mode and the slot config editor (Sprint 1 FE-8/FE-10 rest, deferred).
- Wiring `/api/v1/profile/schedule`.
- Recurring pins.
