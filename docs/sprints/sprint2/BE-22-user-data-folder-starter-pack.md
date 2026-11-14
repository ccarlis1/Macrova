# BE-22 — User data folder, empty starting pool, starter-pack import

**Status:** done  ·  **Complexity:** M  ·  **Depends on:** —  ·  **Blocks:** BE-19 (same recipe-store code), FE-16

## Summary

Separate the repo's own recipes from a user's recipe pool:
- One `MACROVA_DATA_DIR` setting decides where user-writable data lives. Unset, it defaults to today's paths, so nothing changes for development or tests.
- A new user's data folder starts with an **empty** recipe pool, not the owner's recipes.
- The 18 sample recipes become an **optional starter pack**. Users list it and import only the recipes they pick.
- The committed `data/recipes/recipes.json` (32 recipes) stays the dev pool and test fixture.

This settles W6 (README → D-C). The owner chose the data-folder approach on 2026-11-14, with one change from the spec's option a: the run folder starts empty instead of copying `data/`.

## Context

Owner, 2026-11-14: "it should really be up to the agent and the user to decide what they want to eat. A user does not want seemingly random recipes in the pool."

Checked 2026-11-14:
- **Who reads `data/recipes/recipes.json` as the live pool:**
  - `src/api/server.py:106` (`recipes_path`, used by `/plan`, recipe detail and sync);
  - `src/api/meal_prep_routes.py:21` (`DEFAULT_RECIPES_PATH`);
  - the CLI's `--recipes` default (`src/cli.py:158`).
- **Other user-writable files with hard-coded paths:**
  - `data/recipes/recipe_tags.json` (`server.py:110`, `tag_routes.py:15`, `recipe_db.py:28`): it holds `tag_registry`, `tag_aliases` **and** `tags_by_id`, so registry and per-recipe tags share one file;
  - `data/meal_prep/batches.json` (`src/data_layer/meal_prep.py:46`).
- **The benchmark doesn't depend on it.** `evaluation/harness/run_benchmark.py` and `compare.py` read their own library at `evaluation/benchmark/recipes.json`; the only shared file is `data/reference/ingredient_nutrition.json` (read-only). The evaluation tools that do read `data/recipes/recipes.json` (`evaluation/data_track/*`, `evaluation/llm_overhaul/harness/fdc_audit.py`) are offline audits of the repo data, not users.
- **About 20 test files read `data/recipes/recipes.json`** (for example `tests/conftest.py`, `test_planner_integration.py`, `test_api_recipe_sync.py`, `test_runtime_tag_filtering_integration.py`). With the default unchanged, they keep working as fixtures.
- **Sync adds; it never deletes.** `recipe_sync.atomic_upsert_recipes_by_id` upserts by id. Recipes imported server-side survive a Flutter sync.
- **Starter pack source:** `data/recipes/recipes.json.example` (18 recipes) is the first 18 of the committed 32, with the same ids (`recipe_001`…`recipe_018`) and names. Their tags are already in `recipe_tags.json` `tags_by_id`, and the MCP server's `_sample_recipes()` already loads them from there. DATA-1 makes all 18 plannable.
- **Empty pool today:**
  - **HTTP:** with an empty recipes file (probe, `TestClient`), `/api/v1/plan` returns 200, `FM-1` at day 0 slot 0, "No recipes were available to plan with.", `failure_cause: {cause: "EMPTY_POOL", recipe_could_help: false}`. No crash, but `recipe_could_help: false` is wrong (adding recipes is the fix), and the fix text doesn't mention the starter pack.
  - **CLI:** `--recipes <empty file>` prints `Success: False`, `Termination code: TC-2` and exits 0, with no reason. This is the known "Markdown output hides failures" gap.
  - **MCP:** `_recipe_pool` raises "Send at least one recipe, or set use_sample_recipes to true." Already fine, so no change.

## Acceptance criteria

- [x] **One setting.** A single module resolves user-data paths from `MACROVA_DATA_DIR`: recipes, the `tags_by_id` store, meal-prep batches. Unset → today's paths exactly. `server.py`, `meal_prep_routes.py`, `tag_routes.py`, `recipe_db.py`, `meal_prep.py` and the CLI default read from it, with no other hard-coded copies (`grep` test, or a test per call site). Reference data (`data/reference/`) and the MCP sample path are not user data and don't move.
  Test: with `MACROVA_DATA_DIR=<tmp>`, a recipe sync, a meal-prep batch create and a tag create all write under `<tmp>`, and the committed files' hashes are unchanged. Fails today (writes go to `data/`).
- [x] **Tags in the user folder.** The tag store the user writes lives in the data folder, while the shipped registry is still readable. Either split `tags_by_id` from the registry, or copy `recipe_tags.json` into the folder at setup. Pick the smaller change and record why in this stub. `REQUIRES_VERIFICATION`: which readers expect registry and `tags_by_id` in one file.
- [x] **Empty start.** A setup step (`scripts/setup_user_data.py`, or a Make target if W2 is decided by then) creates the folder with an empty pool (`{"recipes": []}`) plus whatever the tag decision above needs. It never overwrites an existing folder. The folder's default location is gitignored. Tests: creates on an empty dir; leaves an existing one untouched.
- [x] **Starter pack API (additive).**
  - `GET /api/v1/starter_recipes` → `{recipes: [{id, name, cooking_time_minutes, calories_per_serving, protein_g_per_serving, tag_slugs_by_type}]}`, built from `recipes.json.example` and its tags.
  - `POST /api/v1/starter_recipes/import` with `{recipe_ids: [...]}` → `{imported: [...], skipped: [{id, reason}]}`. It copies the recipe and its `tags_by_id` entry into the user's store. It's idempotent: re-importing an id is `skipped: already_in_pool`. An unknown id is `skipped: not_a_starter_recipe`, not a 4xx for the whole request.

  Error envelope, OpenAPI snapshot (`python3 scripts/run_export_openapi.py --check` after regenerating), and contract tests in `tests/api/`. The Flutter DTO is FE-16's.
  Tests: list returns 18 entries with nutrition > 0 (catches the BE-21 zero-nutrition bug if it regresses). Import into an empty folder, then plan → success for 1 day. Import twice → skipped. Unknown id → skipped.
- [x] **Empty-pool message.**
  - HTTP: `FM-1` with `cause: EMPTY_POOL` sets `recipe_could_help: true`, and the `fix` text says to add recipes or import the starter pack (`src/api/failure_explanations.py`). Test; fails today.
  - CLI: when the loaded pool is empty, print one plain line naming the file and the two ways to fill it, before planning. Keep the exit code. Test; fails today.
- [x] `python3 scripts/run_pytest.py` green with `MACROVA_DATA_DIR` unset (fixtures unchanged) **and** a smoke subset with it set to a temp folder.
- [x] `benchmark-audit`: 153/153, 0 regressions (`run_benchmark.py` imports `src.api.server`, so check that the path change doesn't touch it).

## Implementation notes

### 🔒 Implementation contract
- Files to inspect:
  - `src/api/server.py` (~106–110, `/plan` ~1205, recipe detail, sync ~1824)
  - `src/api/meal_prep_routes.py`, `src/api/tag_routes.py`, `src/api/recipe_sync.py`
  - `src/data_layer/recipe_db.py`, `src/data_layer/meal_prep.py`, `src/data_layer/tag_repository.py` (or wherever `load_canonical_recipe_tag_slugs` lives)
  - `src/api/failure_explanations.py`, `src/cli.py` (~150–170, ~300–370)
  - `src/mcp_server/tools.py` (`_sample_recipes`, to reuse its loading)
  - `.gitignore`, `tests/conftest.py`
- Entities to reuse: `RecipeDB`, `atomic_upsert_recipes_by_id` and `upsert_recipe_tags` for the import (an import is an upsert from a fixed source); the MCP `_sample_recipes()` loader for the starter list (move it to a shared module rather than copying it).
- Do NOT: move or edit `data/recipes/recipes.json` or `recipes.json.example`, change the benchmark library, make the env var required, or add per-user accounts (one user per data folder).

### 🧠 Pre-implementation analysis
1. List every reader and writer of the three user-data files (`grep -rn "recipes.json\|recipe_tags.json\|batches.json" src scripts`), and decide which need the setting.
2. Settle the tag-store question in criterion 2 before writing the setting.
3. `REQUIRES_VERIFICATION`: whether `config/user_profile.yaml` pin and schedule writes should also move into the data folder. W7 already makes that file personal and untracked (BE-20), so leave it unless a pin write breaks without it. If so, note it for FE-15.
4. Run BE-22 before BE-19 (both touch recipe storage), and coordinate the README quick-start edit with BE-20 (both add a setup step).

### ✅ Post-implementation validation
- `python3 scripts/run_pytest.py`; `python3 scripts/run_export_openapi.py --check`
- `benchmark-audit`: 153/153, 0 regressions
- Manual: on a fresh clone, run setup, start the API with `MACROVA_DATA_DIR` set, plan → the empty-pool message; import 5 starter recipes, plan → success; `git status` is clean.

## Out of scope

- The Flutter picker (FE-16).
- Removing the owner's recipes from git history.
- Multi-user storage, accounts, or a hosted data store.
- Changing which 18 recipes make up the starter pack (owner's call; this task uses `recipes.json.example` as it is after DATA-1).

## Close-out (2026-11-14)

- **One setting:** `src/data_layer/user_data.py` (stdlib-only, resolved per call): `recipes_path()`, `recipe_tags_path()`, `meal_prep_batches_path()`. Unset → `data/recipes/recipes.json`, `data/recipes/recipe_tags.json`, `data/meal_prep/batches.json` exactly. Set → `<dir>/recipes.json`, `<dir>/recipe_tags.json`, `<dir>/meal_prep_batches.json`. Wired into `server.py`, `meal_prep_routes.py`, `tag_routes.py`, `recipe_db.py`, `meal_prep.py`, the CLI (`--recipes`, tag path), `orchestrator.plan_with_llm_feedback` (generated-recipe persistence default) and the three `NUTRITION_TAG_REPO_PATH` fallbacks (`schedule.py`, `time_bucket.py`, `recipe_tagger.py`; that env var still wins). Module-level globals in `server.py`/routers are read at import, so the variable must be set before the process starts. Grep test: `tests/test_user_data.py::test_no_other_hard_coded_user_data_paths_in_src`.
- **Tag decision: copy at setup**, the smaller change. `recipe_tags.json` holds registry, aliases and `tags_by_id`, and 8 modules read the registry from that one path, so a split would touch every reader. Setup copies the shipped `tag_registry` + `tag_aliases` with an **empty** `tags_by_id`, so the user extends the shared vocabulary without inheriting anyone's per-recipe tags. Starter import copies only the picked recipes' `tags_by_id` entries (via `upsert_recipe_tags`, merge), which keeps their shipped cuisine/cost/time data. Note: without setup, a missing tag file falls back to `tag_repository`'s built-in seed tags only.
- **Setup:** `python3 scripts/setup_user_data.py [--dir …]` (default `$MACROVA_DATA_DIR`, else `./user_data`, gitignored as `/user_data/`). Never touches an existing folder. Meal-prep batches are created on first write.
- **Starter pack API:** `GET /api/v1/starter_recipes` (adds `ready_for_planning` and `unresolved` beyond the spec; `calories_per_serving` is `null` when unresolved rather than a partial sum) and `POST /api/v1/starter_recipes/import` (dedupes ids; `already_in_pool` / `not_a_starter_recipe`). Recipe rows go through `atomic_upsert_recipes_by_id(tag_path=None)`. `user_data.load_starter_recipes()` is the shared raw reader (MCP `_sample_recipes()` uses it). MCP now reads the **shipped** tag file explicitly: its `TAG_PATH` used to follow `server.DEFAULT_TAG_PATH`, which is now the user's store.
- **Empty pool:** HTTP `failure_cause.recipe_could_help` is `true` for `EMPTY_POOL`, and the fix mentions the starter pack (`failure_explanations.py`; LLM recovery still declines to generate for an empty pool, unchanged). CLI prints one `No recipes in <file>: …` line to stderr; exit code unchanged (0).
- **Tests:** `tests/test_user_data.py` (paths, setup, fresh-process isolation: sync + tag create + batch create + starter import all write under the folder, committed hashes unchanged), `tests/api/test_starter_recipes.py`. Suite with the variable unset: 1,367 passed; smoke subset (API, MCP, user data, contract) with it set: 112 passed.
- **Pre-analysis 3 (profile pins/schedule):** `config/user_profile.yaml` stays where it is; no pin write needed the folder. FE-15 may revisit.
- **Not done here:** README quick-start step (coordinate with BE-20); `QUICK_START.md` and `AGENTS.md` got a short section/bullet.
