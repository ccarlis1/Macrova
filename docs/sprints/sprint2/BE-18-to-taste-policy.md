# BE-18 — `to taste` only for seasonings; drop recipes that hide nutrients

**Status:** done  ·  **Complexity:** M  ·  **Depends on:** —

## Summary

A `to taste` line counts as 0 g. That's right for salt and pepper and wrong for oats. Allow `to taste` only for ingredients on a committed seasoning list. At planning time, drop any recipe with a `to taste` line outside that list, with `warnings.nutrition`. At save time, reject such lines.

## Context

Follow-up 10. In `data/recipes/recipes.json`, one "Oatmeal with Fruits" has `rolled oats`, `water` and `cinnamon` all `to taste`, so it plans at 169 kcal without the oats. "Quinoa Salad" has `cherry tomatoes` `to taste`. The planner trusts these numbers.

Chosen option (of the two in the follow-up), for consistency with AGENTS.md: "Recipes with unresolved ingredients … are dropped from the pool with `warnings.nutrition` (no silent zeros)." A nutrient-bearing ingredient with no quantity is unresolved in the same sense.

Current mechanics:
- `src/api/recipe_sync.py::_normalize_ingredient_for_storage` turns any unit containing "to taste" into `quantity 0.0, unit "to taste"`.
- `src/planning/converters.py::convert_recipes` drops recipes with unresolved ingredients and logs them to `unresolved_log`, but skips `is_to_taste` lines.
- `src/nutrition/calculator.py` excludes to-taste lines from nutrition.
- `src/llm/recipe_validator.py` already treats to-taste specially (lines ~216, 238, 270).

## Acceptance criteria

- [x] A committed list of ingredients allowed as `to taste` exists in one place (see notes). Each entry has a `category` from a closed set: `salt`, `water`, `spice`, `herb`. It covers at least the salt, pepper, water and spice names in the committed data (for example cinnamon). A test asserts every entry has a category from that set, and that `rolled oats` and `cherry tomatoes` are not on the list.
- [x] `convert_recipes` drops a recipe with a `to taste` line whose name is not allowed, adds it to `unresolved_log` with a reason that names the ingredient (for example `"rolled oats (to taste: needs grams)"`), and so it appears in `warnings.nutrition`. Test in `tests/test_converters.py` with a fixture recipe; fails today because the recipe stays in the pool.
- [x] Allowed `to taste` lines still count as 0 g and don't drop the recipe. Same test module.
- [x] `POST /api/v1/recipes/sync`, `POST /api/v1/recipes` and `PUT /api/v1/recipes/{id}` reject a non-allowed `to taste` line with a structured error. Register a new code (proposed: `INGREDIENT_QUANTITY_REQUIRED`) in `src/api/error_mapping.py`, with `details.ingredient`. Tests in `tests/api/test_recipe_routes.py`; fail today because the line is stored.
- [x] The LLM path still enforces the same rule: a generated draft with a non-allowed `to taste` line is rejected by `validate_recipe_draft`. Test in `tests/test_recipe_validator.py`.
- [x] `/api/v1/plan` on the committed `recipes.json` lists the affected committed recipes in `warnings.nutrition`. Record the list in this stub when closing. Don't edit the recipes' quantities: amounts are recipe data, and nobody has supplied them.
- [x] OpenAPI regenerated; the new error code appears in the error schema; contract test updated (`tests/test_api_v1_and_openapi.py`).
- [x] Flutter: if `ApiException` maps known codes to messages, add the new code. If not, no Flutter change. `REQUIRES_VERIFICATION` in `frontend/lib/services/api_service.dart`.
- [x] `benchmark-audit`: 153/153, 0 regressions. If a benchmark scenario uses a now-dropped recipe, stop and report rather than editing the scenario.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `src/api/recipe_sync.py`, `src/planning/converters.py`, `src/nutrition/calculator.py`, `src/llm/recipe_validator.py`, `src/api/error_mapping.py`, `src/api/server.py` (`_merge_nutrition_warnings`-style helper near line 560), `data/reference/` (existing reference files and their header style).
- Allowed-list location: prefer a small committed reference file `data/reference/to_taste_allowed.json` (names normalized with the existing ingredient normalizer). An alternative is a boolean on each `ingredient_nutrition.json` record, but that file is under human review, so don't add fields to it in this task.
- Name matching: reuse the existing ingredient normalization (`src/ingestion/ingredient_normalizer.py`). Do NOT write another normalizer.
- Do NOT: change quantities in `data/recipes/recipes.json`; add a second drop mechanism next to `unresolved_log`.

### 🧠 Pre-implementation analysis
1. List every `to taste` ingredient name in `data/recipes/recipes.json`, `recipes.json.example` and the benchmark fixtures. Those names are the candidates for the allowed list. On 2026-11-14 the committed data had: cherry tomatoes, salt, pepper, garlic, rolled oats, water, cinnamon. `.example` had none.
2. `REQUIRES_VERIFICATION`: does the benchmark use `data/recipes/recipes.json` or its own pool? (`evaluation/harness/run_benchmark.py`.)
3. Garlic (fresh) is about 149 kcal per 100 g, but is used in small amounts. Decide by the written rule and note the call.

### ✅ Post-implementation validation
- `python3 scripts/run_pytest.py`; `python3 scripts/run_export_openapi.py --check` after regenerating
- `benchmark-audit`: 153/153, 0 regressions
- `cd frontend && flutter analyze && flutter test` only if Flutter changed

## Out of scope

- Deduplicating `recipes.json` (deferred, see README).
- Adding gram quantities to committed recipes.
- Unit conversions (BE-19).

## Close-out (2026-11-14)

- **List:** `data/reference/to_taste_allowed.json` (24 names, categories `salt`/`water`/`spice`/`herb`), matched after `IngredientNormalizer` (so "ground cinnamon" → `cinnamon`). Loader and rule (`load_to_taste_allowed`, `is_to_taste_allowed`) live in `src/nutrition/calculator.py`, next to the "to taste counts as 0 g" rule, so the planner, save and LLM paths share one definition. Tests: `tests/test_to_taste_allowed.py`.
- **Garlic call:** fresh garlic is **not** allowed. It is a vegetable (≈149 kcal/100 g), not salt, water, spice or herb; `garlic powder` is listed as a spice.
- **Planning:** no second drop mechanism. `NutritionCalculator.unresolved_ingredient_names` now reports a non-allowed `to taste` line as `"<name> (to taste: needs grams)"`, so `convert_recipes` drops it through the existing `unresolved_log` → `warnings.nutrition` path (also used by the MCP sample readiness check and LLM recovery). Tests: `tests/test_converters.py::TestToTastePolicy`.
- **Save:** `recipe_sync._normalize_ingredient_for_storage` raises `ApiContractError("INGREDIENT_QUANTITY_REQUIRED", details={"ingredient": name})` → HTTP 422 with `details.ingredient`. `ApiContractError` gained an optional `details`. The sync loop builds every row before writing, so one bad line rejects the whole request and nothing (recipes or tags) is written. Tests: `tests/api/test_recipe_routes.py` (sync, create, put, mixed batch, salt accepted).
- **LLM:** `validate_recipe_draft` gate 2b returns `INGREDIENT_QUANTITY_REQUIRED`. Tests: `tests/test_llm_recipe_validator_gates.py`.
- **OpenAPI:** `ApiErrorBody.code` is a free string (no enum), so the code is documented as a 422 `ApiErrorResponse` on the six save routes (`RECIPE_SAVE_ERROR_RESPONSES`). This replaces FastAPI's default 422 `HTTPValidationError` entry on those routes, which the app never sends: schema errors are 400 `INVALID_REQUEST` (`_request_validation_exception_handler`). Contract test: `test_openapi_recipe_save_routes_document_ingredient_quantity_required`.
- **Flutter:** no change. `ApiException.fromResponse` passes the server `message` through and maps no codes.
- **Committed recipes now in `warnings.nutrition`** (7, all LLM-generated; quantities not edited): `llm_0415c122c1511957` Quinoa Salad (cherry tomatoes); `llm_59834f6218eb974e` Oatmeal with Fruits (rolled oats); Grilled Chicken with Vegetables ×5 (garlic): `llm_26427200aaed5fee`, `llm_922a991802b00168`, `llm_b9f9293329997a31`, `llm_e404d7d8e053dacb`, `llm_ee4f05b19ed0ee4a`. Test: `tests/integration/test_to_taste_plan_warnings.py`.
- **Benchmark:** its library (`evaluation/benchmark/recipes.json`) has no `to taste` lines, and `recipes.json.example` has none either.
