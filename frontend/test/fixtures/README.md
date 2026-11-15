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
