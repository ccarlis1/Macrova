# Migration notes — full per-module test coverage (2026-07-06)

Goal executed: **every module in this repo has a test file, the full test suite passes.**
This document records every change made, the coverage definition used, and the verification
results. No production source was modified — this migration is **tests + docs only**.

## Scope definition

- **Module** = a Python file under `src/` excluding `__init__.py` (68 modules total).
  `__init__.py` files are package markers (the largest, `src/providers/__init__.py`, is 16
  lines of re-exports) and are exercised by every import in the suite.
- **Has a test file** = a dedicated pytest file exists following one of the repo's existing
  naming conventions: `tests/test_<stem>.py`, `tests/test_<package>_<stem>.py`, or a
  documented equivalent (table below).
- **Frontend:** the Dart/Flutter code keeps its existing suite (`frontend/test/`, 15 tests,
  all passing — run as part of this migration's verification). Per-Dart-file test creation
  was not part of this migration; the backend `src/` tree is what the repo's test suite and
  CI cover, and that is now at 100 % module coverage.

## Changes made

### New test files (15 files, 87 tests, all passing)

| New file | Module covered | What the tests pin down |
|---|---|---|
| `tests/test_version.py` | `src/__version__.py` | Version is a non-empty MAJOR.MINOR.PATCH string. |
| `tests/test_api_recipe_sync.py` | `src/api/recipe_sync.py` | Insert-into-missing-file, upsert-by-id replace + append, request-order `synced_ids`, "to taste" normalization (quantity→0), atomic write leaves no `.tmp` residue, field stripping + empty-field rejection, non-object store file raises `ValueError`. |
| `tests/test_summary_hybrid_provider.py` | `src/providers/summary_hybrid_provider.py` | Local hub hit wins without USDA lookup; miss falls back to `CachedIngredientLookup`; USDA hits memoized per instance; blank/unresolvable names → `None`; `resolve_all` no-op. |
| `tests/test_api_provider.py` | `src/providers/api_provider.py` | `resolve_all` processes names **sorted** (determinism), memoizes, fails fast (`IngredientResolutionError`) on miss or lookup exception; lookup-before-resolve raises `RuntimeError`; `_entry_to_dict` shape matches the `NutritionCalculator` contract incl. flattened micronutrients. |
| `tests/test_local_provider.py` | `src/providers/local_provider.py` | Interface conformance, delegation to `NutritionDB`, `None` on miss, `resolve_all` no-op. |
| `tests/test_ingredient_db.py` | `src/data_layer/ingredient_db.py` | Load, copy-isolation of `get_all_ingredients`, case-insensitive name + alias lookup, `None` on miss, empty file tolerated. |
| `tests/test_nutrition_db.py` | `src/data_layer/nutrition_db.py` | Default `per_100g` key, alternate unit keys, alias lookup, returned-dict copy isolation, `None` for unknown ingredient/unit key, `get_ingredient_info` passthrough. |
| `tests/test_recipe_db.py` | `src/data_layer/recipe_db.py` | File-order load, ingredient parsing, "to taste" flag + zeroed quantity, default-empty instructions, by-id miss → `None`, copy isolation. |
| `tests/test_user_profile_loader.py` | `src/data_layer/user_profile.py` | Carbs derived from median fat formula, canonical `schedule_days` parsing, preference stringification, τ defaults to 1.0, unknown micronutrient goals skipped with warning (valid ones kept), missing schedule → `KeyError`, legacy `schedule` dict migrates to one canonical day. |
| `tests/test_data_layer_exceptions.py` | `src/data_layer/exceptions.py` | `IngredientNotFoundError` carries the ingredient name and a useful message. |
| `tests/test_feedback_cache.py` | `src/llm/feedback_cache.py` | Cache key deterministic, sensitive to every component, stable under dict-key ordering; missing file → empty cache; upsert→load round-trips `RecipeDraft`s; schema-version mismatch treated as empty; corrupt file → `FeedbackCacheError`; miss → `None`; canonical sorted JSON on disk. |
| `tests/test_tag_filtering_service.py` | `src/llm/tag_filtering_service.py` | Empty pool passthrough; no-preferences → full pool as a new list; single-cuisine filter preserving input order; multi-cuisine OR-union; empty-result fallback to full pool; all-tags-missing fallback; determinism across repeated calls. |
| `tests/test_llm_types.py` | `src/llm/types.py` | `ValidatedRecipeForPersistence` is frozen; `from_validated_recipes` unwraps in order; empty-list behavior. |
| `tests/test_usda_contract.py` | `src/llm/usda_contract.py` | Capability marker semantics (absent/False/True), structured `USDAProviderRequiredError` (`error_code`, `provider_type`), `APIIngredientProvider` carries the marker. |
| `tests/test_slot_attributes.py` | `src/planning/slot_attributes.py` | `cooking_time_max` band mapping incl. unbounded level 4 and defensive fallback; `time_until_next_meal` same-day / overnight / no-next-slot (∞) / zero-delta 24 h wrap; `explicit_workout_gaps_for_day` legacy-`None`, empty-day, per-day sets, out-of-range day indices. |

All new tests follow repo conventions: plain pytest functions/classes, `tmp_path` for file
I/O, hand-rolled fakes (no network, no real API keys, no new dependencies).

### Documentation

- This file (`migration-notes.md`) — new.

### Source changes

- **None.** No file under `src/`, `frontend/lib/`, `scripts/`, `config/`, or `data/` was
  modified. The OpenAPI snapshot (`openapi/openapi.json`) is unchanged and still passes
  `python scripts/export_openapi.py --check`.

## Coverage equivalents (modules whose dedicated tests predate this migration under a different name)

| Module | Dedicated test file(s) |
|---|---|
| `src/api/server.py` | The 15 `tests/test_api_*.py` endpoint files (routes are the unit) |
| `src/cli.py` | `test_cli_llm_generation.py`, `test_cli_recipe_tag_generation.py` |
| `src/planning/phase0_models.py` | `test_phase0_meal_plan_foundation.py` |
| `src/planning/planner.py` | `test_planner_integration.py` |
| `src/planning/orchestrator.py` | `test_planning_orchestrator_feedback.py` |
| `src/models/schedule.py` | `test_schedule_contract.py` |
| `src/llm/repository.py` | `test_llm_recipe_repository.py` |
| `src/llm/tag_repository.py` | `test_tag_repository_registry.py` |
| `src/llm/tag_filter.py` | `test_tag_filter_integration.py` |
| `src/providers/ingredient_provider.py` | `test_ingredient_provider_baseline_contracts.py` |

All other modules map 1:1 by name (`test_<stem>.py` / `test_<package>_<stem>.py`). Full
68/68 mapping verified programmatically; zero modules without a dedicated test file.

## Verification results (2026-07-06, local venv, repo root)

| Check | Result |
|---|---|
| `python -m pytest tests/ -q` | **1040 passed in 2.27 s** (953 before → +87 new) |
| `python scripts/export_openapi.py --check` | OK — no drift |
| `cd frontend && flutter test` | **15 passed** ("All tests passed!") |

## Notes for future maintainers

- The 15 new files assert current behavior as the contract, including defensive edges
  (e.g. `cooking_time_max` falling back to 30 for out-of-range busyness, hybrid provider
  returning the *same memoized object* on repeat USDA hits). If you intentionally change one
  of these behaviors, the failing test is telling you to update the contract consciously —
  per CLAUDE.md, changed test expectations are a product decision to surface, not a test fix.
- The module→test mapping check used for verification lives in this migration's history and
  can be re-run ad hoc; keep new `src/` modules paired with `tests/test_<name>.py` at
  creation time (CLAUDE.md §5 naming grammar).
