# BE-21 — Recipe detail returns real per-100 g nutrition and unit conversions

**Status:** done  ·  **Complexity:** S  ·  **Depends on:** —

## Summary

`GET /api/v1/recipes/{id}` returns `calories_per_100g: 0` (and zeros for every other nutrient) on every measurable ingredient line, plus `unit_conversions: {}`. It calls a calculator method that doesn't exist, and a bare `except Exception` hides the error. Call the real conversion, and return the record's `grams_per_unit` as `unit_conversions`.

## Context

Found while planning Sprint 2.

- `src/api/server.py::_flutter_ingredient_entries` (~line 774) calls `calculator._convert_quantity_to_grams(ing)`. `NutritionCalculator` has no such method: it has `to_grams`, `_grams` and `normalize_ingredient` (`src/nutrition/calculator.py`).
- The `AttributeError` falls into `except Exception`, which emits an all-zero line.

Probe, 2026-11-14: all 32 committed recipes through `GET /api/v1/recipes/{id}` returned **167 measurable lines, 0 with non-zero `calories_per_100g`**.

Impact: Flutter's Recipe Builder opens a server recipe with `openForEdit` and the detail payload, so it shows zero nutrition, and its live recompute and `unit_conversions` have nothing to work with. This is also half of follow-up 11 ("the server returns `unit_conversions: {}` today"): the detail endpoint never sends the record's real conversions.

Unblocks: BE-19 (unit conversions on save) and FE-13 (Flutter `toGrams` needs real conversions to be strict).

## Acceptance criteria

- [x] For a committed recipe whose ingredients all resolve, every non-`to taste` line in `GET /api/v1/recipes/{id}` has `calories_per_100g` equal to the ingredient record's `per_100g.calories` (within 1e-6), and the same for protein, carbs and fat. Test in `tests/api/test_recipe_routes.py` against the local provider; fails today (0.0).
- [x] `unit_conversions` on each line is the record's `grams_per_unit` (including `g: 1.0` and any explicit size fields `to_grams` uses). Same test module; fails today (`{}`).
- [x] A line whose ingredient doesn't resolve, or whose unit has no conversion, is still returned. Add an explicit `resolved: false` (optional field, additive) rather than silent zeros. Test included.
- [x] No `except Exception` remains around the conversion: catch only the calculator's documented unresolved/unit errors. A test that monkeypatches the calculator to raise `AttributeError` expects a 500 with the standard envelope, not zeros.
- [x] API shape is additive (`resolved` only). Regenerate OpenAPI, update `tests/test_api_v1_and_openapi.py`, and have the Flutter `RecipeIngredientEntry.fromJson` read `resolved` (default `true`). `REQUIRES_VERIFICATION`: the DTO class name in `frontend/lib/models/recipe.dart`. If touching Flutter here before P0 lands is a problem, ship the backend first and do the DTO line in FE-13.
- [x] `benchmark-audit` not required: no planner or nutrition calculation changes, read path only. If the fix ends up changing `calculator.py`, run it (153/153, 0 regressions).

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `src/api/server.py` (`_flutter_ingredient_entries`, `get_recipe_detail` ~line 1900), `src/nutrition/calculator.py` (`to_grams`, `_grams`, `calculate_ingredient_nutrition`, `unresolved_ingredient_names`), `src/providers/local_provider.py`, `tests/api/test_recipe_routes.py`.
- Entities to reuse: the calculator's public `to_grams` (or `normalize_ingredient`). Don't add a new conversion function.
- Do NOT create: a per-endpoint gram-conversion helper.

### 🧠 Pre-implementation analysis
1. `REQUIRES_VERIFICATION`: `to_grams`'s signature and what it raises on an unknown unit. Read `calculator.py` lines 217–262.
2. `REQUIRES_VERIFICATION`: whether the provider exposes the raw record (`grams_per_unit`) in a public method, or only through `calculate_ingredient_nutrition`. Use the provider abstraction; don't open `ingredient_nutrition.json` directly.
3. `git log -S "_convert_quantity_to_grams"` shows when the method was renamed. Note it in the PR.

### ✅ Post-implementation validation
- `python3 scripts/run_pytest.py`; `python3 scripts/run_export_openapi.py --check` after regenerating
- `cd frontend && flutter analyze && flutter test` if the DTO changed
- Re-run the probe: 0 zero-kcal lines among resolvable ingredients.

## Out of scope

- Accepting client-sent conversions (BE-19).
- Flutter UI changes (FE-13).
- The list endpoint `GET /api/v1/recipes` (returns `id`/`name` only).

## Close-out (2026-11-14)

- `NutritionCalculator.unit_conversions(info)` (public, static) returns the record's `g: 1.0`, `grams_per_unit` and `scoop_size_g`/`large_size_g`. `to_grams` now calls it, so the size-field rule lives in one place (keys stay verbatim, so lookups are unchanged).
- `_flutter_ingredient_entries` calls `to_grams` + `calculate_ingredient_nutrition` and catches only `IngredientNotFoundError`; unknown ingredient or unit → `resolved: false` with zeros. Anything else reaches the endpoint's error envelope (500).
- `_convert_quantity_to_grams` was removed from the calculator in a1690ad ("Fix unit conversions…", 2026-10-05) without updating this caller; the bare `except` hid it.
- Probe on the 32 committed recipes: 167 measurable lines, 0 unresolved, 1 with 0 kcal/100 g (water, which is correct). Before: 0 of 167 non-zero.
- OpenAPI: no snapshot change (`ingredients` is `List[Dict[str, Any]]`); `--check` exits 0. Contract test: `tests/test_api_v1_and_openapi.py::test_recipe_detail_ingredient_line_contract`.
- Flutter: `RecipeIngredientEntry.resolved` (default `true`), `frontend/test/recipe_ingredient_entry_resolved_test.dart`. `flutter analyze` clean, 105 tests pass.
