# BE-18 — `to taste` only for seasonings; drop recipes that hide nutrients

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** —

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

- [ ] A committed list of ingredients allowed as `to taste` exists in one place (see notes). Each entry has a `category` from a closed set: `salt`, `water`, `spice`, `herb`. It covers at least the salt, pepper, water and spice names in the committed data (for example cinnamon). A test asserts every entry has a category from that set, and that `rolled oats` and `cherry tomatoes` are not on the list.
- [ ] `convert_recipes` drops a recipe with a `to taste` line whose name is not allowed, adds it to `unresolved_log` with a reason that names the ingredient (for example `"rolled oats (to taste: needs grams)"`), and so it appears in `warnings.nutrition`. Test in `tests/test_converters.py` with a fixture recipe; fails today because the recipe stays in the pool.
- [ ] Allowed `to taste` lines still count as 0 g and don't drop the recipe. Same test module.
- [ ] `POST /api/v1/recipes/sync`, `POST /api/v1/recipes` and `PUT /api/v1/recipes/{id}` reject a non-allowed `to taste` line with a structured error. Register a new code (proposed: `INGREDIENT_QUANTITY_REQUIRED`) in `src/api/error_mapping.py`, with `details.ingredient`. Tests in `tests/api/test_recipe_routes.py`; fail today because the line is stored.
- [ ] The LLM path still enforces the same rule: a generated draft with a non-allowed `to taste` line is rejected by `validate_recipe_draft`. Test in `tests/test_recipe_validator.py`.
- [ ] `/api/v1/plan` on the committed `recipes.json` lists the affected committed recipes in `warnings.nutrition`. Record the list in this stub when closing. Don't edit the recipes' quantities: amounts are recipe data, and nobody has supplied them.
- [ ] OpenAPI regenerated; the new error code appears in the error schema; contract test updated (`tests/test_api_v1_and_openapi.py`).
- [ ] Flutter: if `ApiException` maps known codes to messages, add the new code. If not, no Flutter change. `REQUIRES_VERIFICATION` in `frontend/lib/services/api_service.dart`.
- [ ] `benchmark-audit`: 153/153, 0 regressions. If a benchmark scenario uses a now-dropped recipe, stop and report rather than editing the scenario.

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
