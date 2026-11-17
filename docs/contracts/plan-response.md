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
- Optional: `day_index`, `slot_index`, `slot_id`, `date`, `details`, `fix_hint`, `explanation`, `fix`, `cause` (the last three are plain-language text from `src/api/failure_explanations.py`)

`report.failure_cause` (optional, `PlanFailureCause`): `cause`, `recipe_could_help`, `recipe_gap` — whether a new recipe could fix the failure and what it must satisfy (`failure_cause_block` in `src/api/failure_explanations.py`).

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

## Daily upper limits: `demographic` (request)

Sprint 2 BE-17. On both `/plan` (`PlanRequest`) and `/plan-from-text` (`PlanFromTextRequest`), optional `demographic` is one of `adult_male`, `adult_female`, `pregnancy`, `lactation` (the demographics `data/reference/ul_by_demographic.json` and `rdi_by_demographic.json` carry). Any other value is 400 `INVALID_REQUEST`.

- **Set:** the planner enforces that demographic's daily ULs, per day, in deterministic and assisted modes (`plan_meals(..., resolved_ul=...)`, threaded through `plan_with_llm_feedback`). It does **not** set `micronutrient_goals`.
- **Omitted:** no ULs; the request plans exactly as before the field existed.
- **Failure code:** there is no UL-specific code. A UL prunes candidates during search (FC-3); when that leaves a day unable to meet its targets the plan fails like any other target miss, typically `FM-MACRO-INFEASIBLE` (`cause: macro_gap`).
- The CLI reads the same value from the profile YAML's `demographic`, and `build_plan_request_from_profile` carries it. The API, CLI and MCP server all resolve ULs through `src/data_layer/upper_limits.py` (`upper_limits` / `upper_limits_for`).

## Default micronutrient goals: `GET /api/v1/micronutrient_defaults` (read-only)

Sprint 2 BE-20. Query parameter `demographic` (required; `adult_male`, `adult_female`, `pregnancy`, `lactation`). Any other or missing value is 400 `INVALID_REQUEST` (`{"error": {"code", "message"}}`). Response `MicronutrientDefaultsResponse`:

- `demographic`: echoed.
- `micronutrient_goals`: nutrient key → daily amount; the demographic's RDIs minus `left_out` (`default_micronutrient_goals`).
- `left_out`: nutrient keys the default drops, in reference-table order (`default_micronutrient_left_out`).
- `micronutrient_weekly_min_fraction`: the default τ (`DEFAULT_MICRONUTRIENT_WEEKLY_MIN_FRACTION`, 1.0).

All four come from `src/data_layer/upper_limits.py`, the same default the MCP server applies for `targets.demographic`. The route does not change planning: `/plan` applies micronutrient floors only when the request sends `micronutrient_goals`, with or without `demographic`. A client that wants the default sends these goals itself.

## Recipe sync: `default_servings`

`POST /api/v1/recipes/sync` items include `default_servings` (see `RecipeDetailResponse` in `server.py` and the sync models in `src/api/recipe_sync.py`). Flutter `Recipe.toSyncPayload()` sends `default_servings` from local `servings`.

## Recipe saves are plannable (sync, create, update)

Sprint 2 BE-19. A recipe saved through `POST /api/v1/recipes/sync`, `POST /api/v1/recipes` or `PUT /api/v1/recipes/{id}` is either plannable or rejected; it never drops out of the pool later.

- **Line weights.** An ingredient line may send `grams_per_unit` (> 0): the weight of one `unit` of that line. It is stored on the line in `recipes.json` (only when set) and used by `NutritionCalculator.to_grams` only after mass units and the ingredient record's own conversions. It is never written to `data/reference/ingredient_nutrition.json`. Recipe detail shows it in that line's `unit_conversions` when the record has no conversion for the unit.
- **Save-time check.** Each line must resolve against the **local** ingredient table (no USDA calls at save) and convert to grams. Create/update return HTTP 400 `UNIT_NOT_CONVERTIBLE` or `INGREDIENT_UNRESOLVED`, both with `details: {ingredient, unit}`. Sync skips the item (not stored, not in `synced_ids`) and appends `"<recipe id>: <CODE>: <message>"` to `errors`; the other items still sync. A nutrient-bearing `to taste` line is still a whole-request 422 `INGREDIENT_QUANTITY_REQUIRED` (BE-18).
- **Tags.** Every saved recipe gets a `tags_by_id` entry (merged into the tag store): `prep_time_bucket` and the `time` slug are derived from `cooking_time_minutes`; client `tag_slugs_by_type` replace the other types (omitted keeps the stored ones). Optional item fields `cuisine` (the tagger's closed vocabulary), `cost_level` and `dietary_flags` are written when sent; when omitted the stored value is kept, else `"unknown"`, `"standard"`, `[]`. An out-of-vocabulary value is 400 `INVALID_REQUEST`.
- The starter-pack import (`/api/v1/starter_recipes/import`) copies shipped recipes and tags as-is and does not run these checks.
