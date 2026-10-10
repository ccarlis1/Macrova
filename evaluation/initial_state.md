# Macrova pre-sprint baseline

**Date/time of baseline:** 2026-09-17 14:54:05 EDT through 2026-09-17 14:58:14 EDT (−0400)

This is a snapshot of the repository as it exists immediately before the 48-hour AI-assisted validation sprint. Feature implementation status is taken from `docs/sprints/sprint1/` (not re-audited). No implementation, refactors, or fixes were made.

---

## Git state

| Field | Value |
| --- | --- |
| Branch | `140-dollar-sprint` |
| Upstream | none configured |
| Commit | `ee58fcc05c1ee7912f5a63968eb2807b3a5c73a5` (`ee58fcc`) |
| Author date | 2026-06-23 16:17:19 −0400 |
| Subject | Keep backend-readiness versions of sprint-overlap files after main merge. |
| vs `origin/main` | identical (`0` ahead / `0` behind) |
| Also at this commit | local `main`, local `backend-readiness`, `origin/main`, `origin/backend-readiness` |
| Remote | `origin` → `git@github.com:ccarlis1/Macrova.git` |

### Working-tree status

```
On branch 140-dollar-sprint
Untracked files:
	evaluation/

nothing added to commit but untracked files present
```

Porcelain at start of baseline: `?? evaluation/`

- No staged or unstaged modifications to tracked files.
- The only local change relative to `HEAD` is this untracked `evaluation/` directory (including this report).
- Verification commands (`pytest`, OpenAPI check, Flutter `pub get` / `analyze` / `test` / `build web`) did not dirty the tracked working tree.
- `frontend/build/` is gitignored (`frontend/.gitignore`: `/build/`).

---

## Documented implementation state (from sprint 1 stubs)

Source: `docs/sprints/sprint1/*.md` status lines. These were **not** re-verified against source.

**Implemented (21):** DM-1, DM-2, DM-3, DM-4, DM-5, DM-6, DM-7; BE-1 through BE-14.

**Todo (16):** BE-15; AI-1 through AI-5; FE-1 through FE-10.

No sprint-1 ticket is marked `partially implemented`, `in-progress`, or `blocked`. The index (`docs/sprints/sprint1/README.md`) still describes the stub vocabulary as `todo | in-progress | blocked | done`, while the ticket files themselves use `implemented` / `todo`.

`AGENTS.md` separately lists these as known partial / mock areas (quoted as documented, not re-audited here):

- Meal-plan calendar view — placeholder in `meal_plan_view_screen.dart`
- Ingredient Hub “add to recipe” — snackbar pointing at Recipe Builder
- Frontend `PlanRequest` tag fields — may not carry all backend tag-filter fields
- `MealPrepReference` / meal-prep batching — marked `partial` in `.cursor/architecture.json`, with a note that architecture.json is stale relative to source

---

## Environment / runtime (reproducibility)

| Item | Observed |
| --- | --- |
| Host | macOS 26.3 (25D125), Darwin 25.3.0, arm64 |
| System `python3` | 3.14.3 (`/opt/homebrew/bin/python3`) |
| Pin | `.python-version` → `3.12` |
| Canonical venv | `.venv/` Python **3.12.13** (`home = /opt/homebrew/opt/python@3.12/bin`) |
| pip | 26.2.1 |
| Key packages in `.venv` | fastapi 0.141.1, pydantic 2.13.5, pytest 9.1.1 |
| Flutter | 3.41.1 stable (framework `582a0e7c55`, 2026-02-12), Dart 3.11.0, DevTools 2.54.1 |
| `flutter doctor` | no issues found (Android SDK 36.1.0, Xcode 26.2 / 17C52, CocoaPods 1.16.2, Chrome 153.0.8010.47; devices: `macos`, `chrome`) |
| Local `.env` | present, gitignored (contents not read) |
| Local data | `config/user_profile.yaml` **tracked**; `data/recipes/recipes.json` gitignored (32 recipes); `data/ingredients/custom_ingredients.json` gitignored; `data/recipes/recipe_tags.json` **tracked** |

CI (`.github/workflows/ci.yml`, not executed in this baseline) uses Python **3.11**, `python -m pytest tests/ -q`, and `python scripts/export_openapi.py --check` — not `python3 scripts/run_pytest.py` / `python3 scripts/run_export_openapi.py`, and not Python 3.12.

README badge still says “Python 3.10+”.

---

## Test commands and results

### Backend

**Command:** `python3 scripts/run_pytest.py` (repo root; runner uses `.venv`)

**Result:**

```
============================= test session starts ==============================
platform darwin -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/user1/Documents/GitHub/nutrition-agent
configfile: pytest.ini
testpaths: tests
plugins: cov-7.1.0, anyio-4.15.1
collected 1074 items
...
======================= 1074 passed, 2 warnings in 2.25s =======================
```

Exit code: **0**. No failed, skipped, or xfailed tests.

Exact warnings:

```
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  .../fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv/lib/python3.12/site-packages/starlette/testclient.py:53
  .../starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]
```

### OpenAPI snapshot

**Command:** `python3 scripts/run_export_openapi.py --check`

**Result:** exit code **0**, empty stdout. Snapshot at `openapi/openapi.json` matches the live app.

### Frontend

From `frontend/`:

| Command | Result |
| --- | --- |
| `flutter pub get` | `Got dependencies!` plus `21 packages have newer versions incompatible with dependency constraints.` |
| `flutter analyze` | `No issues found! (ran in 1.6s)` — exit 0 |
| `flutter test` | `All tests passed!` — exit 0 (counter reached `+17` across 8 files under `frontend/test/`) |
| `flutter build web` | `✓ Built build/web` after `Compiling lib/main.dart for the Web... 24.1s` — exit 0 |

`flutter build web` also printed:

```
Wasm dry run succeeded. Consider building and testing your application with the `--wasm` flag.
Use --no-wasm-dry-run to disable these warnings.
Font asset "CupertinoIcons.ttf" was tree-shaken, reducing it from 257628 to 1472 bytes (99.4% reduction).
Font asset "MaterialIcons-Regular.otf" was tree-shaken, reducing it from 1645184 to 11544 bytes (99.3% reduction).
```

No Dart analyzer issues. No failing Flutter tests.

Python `mypy` / `black` are listed in `requirements.txt` but are **not** invoked by `Makefile` or CI; they were not run.

---

## Build / run verification

### CLI planner (established workflow)

Used `.venv/bin/python` (not system Python 3.14). `--help` exit 0.

**Default data** (`config/user_profile.yaml`, `data/recipes/recipes.json` [32 recipes], `data/ingredients/custom_ingredients.json`):

- Process exit code: **0**
- JSON: `success: False`, `termination_code: 'TC-2'`, `plan_status: 'failed'`
- `report.failures[0]`:

```
code: FM-4
message: Weekly micronutrient targets are infeasible with current constraints.
fix_hint: Weekly micronutrient targets cannot be met. Lower tracked goals, add richer recipes, or relax filters.
```

Stderr (exact):

```
Loading user profile from config/user_profile.yaml...
Warning (yaml): Legacy flat schedule (HH:MM -> int) is deprecated; use schedule_days with MealSlot and WorkoutSlot.
Warning: micronutrient_weekly_min_fraction (τ) below 0.85 relaxes weekly micronutrient floors substantially.
Loading recipes from data/recipes/recipes.json...
Found 32 recipes
{"filter_applied": false, "input_recipe_count": 32, "output_recipe_count": 32}
Loading ingredients from data/ingredients/custom_ingredients.json...
{"active_batches": [], "effective_plan_request_keys": ["active_batches", "allergies", "daily_calories", "daily_fat_g_max", "daily_fat_g_min", "daily_protein_g", "disliked_foods", "liked_foods", "micronutrient_goals", "micronutrient_weekly_min_fraction", "recipe_ids", "schedule"], "persisted_pins": [], "seed": null}
Planning meals...

⚠️  Meal plan generated with warnings:
```

Observed in the same run: stderr says “Meal plan generated with warnings” while the JSON body is `success: False` / `plan_status: 'failed'`.

**Example data** (`*.example` profile/recipes/ingredients; 18 recipes): same process exit **0**, same JSON failure (`TC-2` / `FM-4` / same message and `fix_hint`), and the same stderr warning lines (paths/counts differ: example profile, 18 recipes).

The CLI binary runs. With both this machine’s local recipe file and the committed example recipe file, planning reports infeasibility rather than a successful plan.

- a combination to examine: --ingredient-source api (local cache) --days 3 generates with warnings

### REST API

`from src.api.server import app` succeeded (`title: Nutrition Agent API`, 38 routes).

Started: `.venv/bin/python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000`

Log:

```
INFO:     Started server process [43762]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Live HTTP checks:

| Request | Result |
| --- | --- |
| `GET /docs` | HTTP 200 (1018 bytes) |
| `GET /openapi.json` | HTTP 200 (44934 bytes) |
| `GET /api/v1/llm/status` | HTTP 200 `{"enabled":true}` |
| `GET /api/v1/recipes` | HTTP 200 JSON list (includes ids such as `recipe_001` … and `llm_*`) |
| `GET /` | HTTP 404 `{"detail":"Not Found"}` |

`GET /` 404 is the FastAPI default; there is no root route. The uvicorn process started for these checks was left running on `127.0.0.1:8000` (stopping it was not part of recording the snapshot).

### Flutter app

Compile (`flutter build web`) succeeded. `flutter run` (Chrome/macOS) was **not** started; no interactive UI session was exercised.

USDA API ingredient mode (`--ingredient-source api`) was **not** run.

iOS/Android installable builds were **not** run.

---

## Existing errors / warnings encountered

1. **Planner result FM-4 / TC-2** on default CLI invocation (local data and example data). Process still exits 0. Preserve the fields above to distinguish later sprint failures from this pre-existing infeasible plan.
2. **Pytest:** 2 third-party deprecation warnings (Starlette/`httpx` TestClient; `anyio.abc.BlockingPortal`). Tests still passed.
3. **CLI yaml/profile warnings:** legacy flat schedule deprecation; τ below 0.85.
4. **CLI banner vs JSON:** “generated with warnings” vs `plan_status: failed`.
5. **`flutter pub get`:** 21 packages have newer versions incompatible with current constraints (info, not a failure).
6. **`flutter build web`:** wasm-dry-run suggestion and icon tree-shake info (build succeeded).
7. **`GET /`:** HTTP 404 on the running API.

No backend test failures, no OpenAPI drift, no Flutter analyzer issues, no Flutter test failures, no web build failure.

---

## Discrepancies between audit docs and what this baseline could reproduce

These are documentation/command mismatches against files and commands actually run. They are **not** a new implementation audit.

1. **BE-15 is `todo`**, but `tests/api/` already contains six modules that passed in the 1074-test run: `test_plan_contract.py`, `test_profile_pins.py`, `test_recipe_routes.py`, `test_recipe_sync.py`, `test_tag_routes_contract.py`, `test_meal_prep_routes.py`. This baseline did not map those tests onto BE-15 acceptance criteria.
2. **DM-1 / DM-2 “Known gap”** states `data/recipes/recipe_tags.json` is absent from the repo snapshot. `git ls-files` shows `data/recipes/recipe_tags.json` **is tracked**.
3. **`AGENTS.md` known partial** says frontend `PlanRequest` may not include all backend tag-filter fields. `frontend/test/plan_request_tag_contract_test.dart` passed, asserting serialization of `cuisine`, `cost_level`, `prep_time_bucket`, `dietary_flags`, `recipe_tags_path`, and MealSlot `required_tag_slugs` / `preferred_tag_slugs`. Full `PlanRequest` vs `server.py` field parity was not compared here.
4. **CI vs AGENTS.md:** CI uses Python 3.11 and bare `python -m pytest` / `python scripts/export_openapi.py`; AGENTS.md requires 3.12 and the `scripts/run_*.py` wrappers. CI was not executed.
5. **`.gitignore` lists `config/user_profile.yaml`**, but the file is tracked (`git ls-files config/user_profile.yaml`). `git check-ignore` does not report it for that reason.
6. **Sprint index status vocabulary** (`done`) does not match ticket status strings (`implemented`).

---

## What prevented a complete baseline

- No GitHub Actions CI run (would need a push/PR or `act`); local canonical commands were used instead.
- No `flutter run` / browser or device session of the Flutter UI.
- No iOS or Android release/debug device builds.
- No USDA live-API planning run.
- No `mypy` or `black` run (not part of Makefile/CI).
- System Python is 3.14.3; CLI/API verification used `.venv` 3.12.13 only. Behavior of `python3 plan_meals.py` on the unpinned Homebrew 3.14 interpreter was not measured.
- Local gitignored `data/recipes/recipes.json` / `data/ingredients/custom_ingredients.json` are machine-specific. Example files were also run so the FM-4 result is not solely an untracked-data artifact.

No code was modified to record this baseline.

---

## Baseline Status

**BASELINE WITH KNOWN FAILURES**

The project is reproducible: git is clean except this untracked report, backend tests are 1074 passed, OpenAPI `--check` passes, Flutter analyze/test/web-build pass, and the API server starts and serves `/docs`, `/openapi.json`, `/api/v1/llm/status`, and `/api/v1/recipes`.

The known failure that later sprint work must not confuse with new breakage is the **default CLI planner outcome**: exit 0 with `success: False`, `termination_code: "TC-2"`, `plan_status: "failed"`, failure code **`FM-4`** (weekly micronutrient targets infeasible), on both this checkout’s local recipes (32) and `recipes.json.example` (18).
