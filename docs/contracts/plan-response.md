# PlanResponse contract

Authoritative shapes for `POST /api/v1/plan` and `POST /api/v1/plan-from-text`. Do not invent fields — trust source and OpenAPI.

**Source:** `src/output/formatters.py` (`format_result_json`), `src/api/server.py` (`PlanResponse`, `PlanFailure`, `PlanRequest`, `PlanFromTextRequest`, `PlannedMeal`), [`openapi/openapi.json`](../../openapi/openapi.json).

## Top-level `PlanResponse` paths

| Path | Notes |
| --- | --- |
| `success` | Planner boolean |
| `termination_code` | Telemetry (`TC-*`); not the UX branch key |
| `plan_status` | `success` \| `partial` \| `failed` |
| `plan_status_message` | Optional incomplete reason |
| `days` | Horizon 1–7 |
| `daily_plans[]` | Per-day meals + optional `totals` |
| `weekly_totals` | Present when `days > 1` and weekly tracker exists |
| `warnings` | Advisory map/object (merged schedule/filter warnings on the API path) |
| `report.failures[]` | Actionable `PlanFailure` list |
| `goals` | Daily calorie/protein/fat/carb targets |

## `plan_status` derivation

From `format_result_json` (`src/output/formatters.py`):

1. `success` if `result.success` and no `report.failures` and no `plan_incomplete_reason`
2. Else `partial` if any usable `daily_plans` exist
3. Else `failed`

## `PlanFailure` shape

OpenAPI / `server.py` `PlanFailure`:

- `code`: `FM-1`…`FM-5`, `FM-TAG-EMPTY`, `FM-BATCH-CONFLICT`, `FM-MACRO-INFEASIBLE`
- `message` (required)
- Optional: `day_index`, `slot_index`, `slot_id`, `date`, `details`, `fix_hint`

**HTTP:** Planner `FM-*` results are returned as **HTTP 200** with the failure in `report.failures[]` (usual path). Non-2xx structured errors use `map_exception_to_api_error` — do not assume every `FM-*` is an HTTP error.

## Meal metadata on `daily_plans[].meals[]`

From `format_result_json` + `_attach_planned_meal_metadata`:

Always (when recipe resolves): `recipe_id`, `name`, `meal_type`, `cooking_time_minutes`, `ingredients`, `nutrition`, `busyness_level`, `slot_index`, `source`.

`source` is one of `meal_prep_batch` | `pinned_assignment` | `planner`. For batch slots also: `batch_id`, `servings`.

OpenAPI `PlannedMeal` allows extra fields (`extra="allow"`).

## Pool filter fields (request)

On both `/plan` (`PlanRequest`) and `/plan-from-text` (`PlanFromTextRequest`):

- `cuisine` (list of strings, optional)
- `cost_level` (optional)
- `prep_time_bucket` (optional)
- `dietary_flags` (optional)
- `recipe_tags_path` (optional)

## Recipe sync: `default_servings`

`POST /api/v1/recipes/sync` items include `default_servings` (see `RecipeDetailResponse` / sync models in `server.py`). Flutter `Recipe.toSyncPayload()` sends `default_servings` from local `servings`.
