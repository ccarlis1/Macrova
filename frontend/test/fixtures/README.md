# Test fixtures

Real `POST /api/v1/plan` responses, captured in-process (FastAPI `TestClient`) from
the committed backend at the sprint2-wave2 base, using the request that
`build_plan_request_from_profile` builds for `config/user_profile.yaml.example`
(1 day, `planning_mode: deterministic`, `active_batches` removed — the BE-16
parity probe in `docs/sprints/sprint2/probes/parity_probe.py`).

| File | Request change | Outcome |
| --- | --- | --- |
| `plan_failure_recipe_gap.json` | none | `partial`, FM-4 (`nutrient_gap`), `failure_cause.recipe_could_help: true` with a `recipe_gap` |
| `plan_failure_impossible_targets.json` | `max_daily_calories: 800` | `failed`, FM-4 (`IMPOSSIBLE_TARGETS`), `recipe_could_help: false` |

Used by `test/plan_failure_dto_test.dart` (FE-11). Re-capture if the
`PlanFailure` / `PlanFailureCause` contract changes.

## Tag fixtures (FE-12)

Captured in-process (FastAPI `TestClient`) from the committed backend at the
sprint2-wave2 BE-19 commit, with `MACROVA_DATA_DIR` pointing at an empty temp folder.

| File | Request | Notes |
| --- | --- | --- |
| `tags_list_response.json` | `GET /api/v1/tags` | The seeded registry: 4 `context`/`meal_role`, `meal-prep` (`capability`), 3 `nutrition`, 1 `constraint`, 5 `time`; all `source: system`. |
| `recipe_detail_meal_prep.json` | `POST /api/v1/recipes/sync` (`default_servings: 2`, `context: [breakfast, meal-prep]`, `nutrition: [high-fiber]`, `cuisine: american`, `cost_level: cheap`), then `GET /api/v1/recipes/fe12-oat-bowl` | Detail carries `tag_slugs_by_type` (with the server-derived `time`), `is_meal_prep_capable: true` and the stored `cuisine` / `cost_level` / `dietary_flags` (re-captured after commit 4593309; null when a recipe has no tag entry). |

Used by `test/tag_registry_dto_test.dart`, `test/recipe_sync_payload_test.dart`,
`test/providers/recipe_provider_server_tags_test.dart` and
`test/widgets/recipe_builder_tags_test.dart`.

## Meal-prep fixtures (FE-14)

Captured in-process (FastAPI `TestClient`) from the committed backend at the
sprint2-wave2 FE-13 commit (`7501f26`), with `MACROVA_DATA_DIR` pointing at a temp
folder seeded with `data/recipes/recipes.json`. First `POST /api/v1/recipes/sync`
of `fe14-oat-bowl` (`default_servings: 3`, `context: [breakfast, meal-prep]`) and
`fe14-plain` (1 serving, no `meal-prep`), then, in order:

| File | Request | Notes |
| --- | --- | --- |
| `meal_prep_error_not_batchable.json` | `POST /api/v1/meal_prep_batches` for `fe14-plain` | 422 `RECIPE_NOT_BATCHABLE` |
| `meal_prep_batch_created.json` | `POST` `fe14-oat-bowl`, `total_servings: 3`, `cook_date: 2026-11-14`, assignments `(0,0)` and `(1,0)` | 200; `status: active`, assignment `date` = cook_date + day_index |
| `meal_prep_error_conflict.json` | `POST` another batch at `(0,0)` | 409 `BATCH_CONFLICT` |
| `meal_prep_batches_list.json` | `GET /api/v1/meal_prep_batches` | `{"batches": [...]}` |
| `plan_with_meal_prep_batch.json` | `POST /api/v1/plan`, 2 days, request from `build_plan_request_from_profile(config/user_profile.yaml.example)` minus `active_batches` / `recipe_ids` | `partial` (FM-4); day 1 and day 2 `slot_index: 0` are `source: meal_prep_batch` with the batch id and `servings: 1.0` |

Used by `test/meal_prep_api_test.dart` (DTO, client, index bases),
`test/widgets/meal_prep_tray_test.dart`, `test/widgets/create_batch_sheet_test.dart`
and `test/providers/meal_plan_provider_meal_prep_test.dart`.
