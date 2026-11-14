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
