# Tooling — the tests, planning benchmark, evaluation tracks, hooks and CI that verify Macrova

Status: implemented · Code: `tests/`, `evaluation/`, `scripts/`, `.claude/hooks/`, `.github/workflows/ci.yml`, `Makefile` · Facts: [generated/tooling.md](generated/tooling.md)

## Purpose
This area checks the system without being part of it. The pytest suite pins backend behaviour. The planning benchmark scores the real planner against an independent oracle. Two closed evaluation tracks record past nutrition-data and LLM-layer measurements. Claude Code hooks enforce repo rules while an agent works. CI runs only pytest, the OpenAPI drift check and the map check, so most verification is local.

## Entry points
All commands run from the repo root, except Flutter.
- `python3 scripts/run_pytest.py` (`make test`) — runs the full backend suite (~11 s) inside .venv after validating `requirements.txt`. Run it after any backend change. Never run bare `pytest`.
- `python3 scripts/run_export_openapi.py --check` (`make openapi-check`) — checks that `openapi/openapi.json` matches the app. After an API change, run it without `--check` to regenerate (`make openapi`).
- Planning benchmark, run in order after any change to `src/planning/`, pins, batches, tags, the oracle or the scenarios:
  `.venv/bin/python evaluation/harness/run_benchmark.py` → `.venv/bin/python evaluation/harness/compare.py` → `.venv/bin/python evaluation/harness/probes.py` → `.venv/bin/python evaluation/harness/diff_results.py --base main`. Exit 1 from the diff means stop.
- `python3 evaluation/benchmark/build.py --check` — confirms the authored labels agree with the oracle. Run it after editing scenarios or the library.
- `cd frontend && flutter analyze && flutter test` — the Flutter gate (not in CI).
- `python3 scripts/gen_architecture_map.py` — regenerates `docs/architecture/map/generated/`. `--check` fails on drift or broken map references; `--stale-intent` advises which hand-written map docs to review. `make map` / `make map-check`; CI and the Stop hook run `--check`.
- Debug and setup: `python3 scripts/export_planner_debug_artifacts.py` (CLI-vs-Flutter parity artifacts), `python3 scripts/benchmark_meal_plan_search.py` (search timing), `python3 scripts/setup_user_data.py` (empty `MACROVA_DATA_DIR`), `python3 scripts/export_flutter_cached_ingredients_bundle.py` (dev ingredient asset; reads the gitignored cache).

## How it works
**Benchmark pipeline.** `evaluation/benchmark/scenarios.py` and `evaluation/benchmark/library.py` author the scenarios and recipes. `evaluation/benchmark/build.py` labels each scenario with `evaluation/benchmark/oracle.py::Oracle` and writes the committed `scenarios.json`, `recipes.json` and `recipe_tags.json`. `evaluation/harness/run_benchmark.py::run` sends each scenario down the /api/v1/plan path (`PlanRequest` validation → `src/api/server.py::_build_user_profile` → `convert_profile` → `plan_meals`). It uses stored per-serving nutrition by default and writes `evaluation/harness/results/results.json`. `evaluation/harness/compare.py` labels each scenario against `expected` and re-checks every returned plan (`evaluation/harness/compare.py::verify`). `evaluation/harness/probes.py` covers fully pinned days inside longer plans (cluster C3). `evaluation/harness/diff_results.py` compares the fresh `compare.json` with the one at a git ref, and maps every disagreement to a cluster parsed from `evaluation/reports/benchmark_failure_analysis.md` (`### C<n>.` headings, `**Scenarios:**` and `**Status:** fixed` lines). Counterfactual switches: `ALL_BATCHES=1`, `LIMIT=<n>`, `OUT=<path>`, `--nutrition computed`.

**Baseline rules.** The committed `compare.json` is the baseline: 153/153 MATCH. Only `secs` may differ between runs, because the planner is deterministic. Ask before committing refreshed results.

**Hooks** (`.claude/settings.json`). Hooks are stdlib-only, fail open, and write only under .claude/.hook-state/, which is not gitignored.
- SessionStart `.claude/hooks/session_health.py` reports interpreter vs CI, missing imports, absent runtime data, dirty user data and pre-existing OpenAPI drift. It never blocks.
- PreToolUse (Write/Edit) `.claude/hooks/guard_paths.py` denies writes to user-data files (.example files are always allowed) and known fork paths (any *_v2.py, tag_service.py, src/planning/plan_*.py). It asks before a new module is created under `src/`.
- PreToolUse (Bash) `.claude/hooks/guard_bash.py` denies `git clean`, and `git add`/`rm`/`mv`/redirects aimed at user data. It denies repo commands (pytest, `plan_meals.py`, scripts/*.py, uvicorn) run outside a checkout root. It asks before `pip install` outside `requirements.txt` and before `flutter pub add`. It backs up config/user_profile.yaml before pytest.
- PostToolUse (Write/Edit) runs three blocking checks. `.claude/hooks/check_determinism.py` flags new wall-clock, randomness or unordered iteration in `src/planning/` against the baseline. `.claude/hooks/check_llm_lane.py` flags nutrition-named fields on LLM pydantic models in `src/llm/`. `.claude/hooks/check_contract.py` catches non-additive OpenAPI changes against the `HEAD` snapshot, plus drift.
- Stop `.claude/hooks/verify_stop.py` picks its gates from `git status`. Any dirty `src/` or `tests/` runs full pytest, and dirty `src/planning/` adds a rerun under `PYTHONHASHSEED=524287`. Dirty `src/api/` or `src/models/` runs the OpenAPI check. Dirty `frontend/` runs `flutter analyze` and `flutter test` when `flutter` is on PATH. Dirty map inputs run the map `--check`. It caches by content hash and stops blocking after three tries.

**CI** (`.github/workflows/ci.yml`, push/PR to `main`): Python 3.11, `pip install -r requirements.txt`, `python -m pytest tests/ -q`, `python scripts/export_openapi.py --check`, then `python scripts/gen_architecture_map.py --check` (plus advisory `--stale-intent` on PRs).

**Test layout.** `pytest.ini` sets `pythonpath = .` and `testpaths = tests`. Planner phases have one flat file each, from `tests/test_phase0_meal_plan_foundation.py` to `tests/test_phase10_reporting.py`. Cross-phase constraint features (batch locks, scoring, slot constraints) live in `tests/planning/`. API behaviour is covered by the flat tests/test_api_*.py files, the router and contract tests in `tests/api/`, and the snapshot and route checks in `tests/test_api_v1_and_openapi.py`. Cross-layer flows (CLI/Flutter parity, pin hydration) live in `tests/integration/`. No network is the convention: USDA and LLM calls are mocked or monkeypatched, and no socket blocker exists.

## Modules
| Module | Role | Status |
|---|---|---|
| `evaluation/benchmark/` | Scenarios, recipe library, standalone oracle, build | implemented |
| `evaluation/harness/` | Run, compare, probes, diff; committed results; scoring-weight sweep | implemented |
| `evaluation/reports/` | Failure analysis (machine-parsed), reconciliation and design reviews | implemented |
| `evaluation/data_track/` | Closed nutrition-data measurement track; decision gate committed, JSON outputs gitignored | experimental (closed) |
| `evaluation/llm_overhaul/` | Closed LLM-layer evaluation; NL and tagging harnesses need a live LLM; results committed | experimental (closed) |
| `scripts/` | venv runners, OpenAPI export, user-data setup, parity and search debugging, one migration | implemented |
| `.claude/hooks/` | Session, edit, bash, post-edit and stop gates | implemented |
| `tests/` | Backend pytest suite | implemented |
| `.github/workflows/ci.yml`, `Makefile` | CI gate; `make test`/`openapi`/`openapi-check`/`map`/`map-check` aliases | implemented |

## Key types
- `evaluation/benchmark/oracle.py::Oracle` — spec-v3 feasibility oracle. It imports nothing from `src/`.
- `evaluation/benchmark/scenarios.json` — 153 scenarios with `expected` blocks. Generated; author changes in `evaluation/benchmark/scenarios.py`.
- `evaluation/harness/results/compare.json` — the baseline that `evaluation/harness/diff_results.py::load` reads through `git show`.
- `evaluation/harness/compare.py::verify` — independent hard-constraint re-check of returned plans.
- `evaluation/reports/benchmark_failure_analysis.md` — cluster registry, parsed by `evaluation/harness/diff_results.py::clusters`.
- `.claude/hooks/determinism_baseline.json` — accepted nondeterminism sites. Regenerate it with `--write-baseline` only after a deliberate cleanup.
- `scripts/_venv.py::ensure_requirements_installed` — the venv contract behind every runner.

## Invariants
1. Backend tests run through `scripts/run_pytest.py` in .venv. Enforced by `scripts/_venv.py::ensure_requirements_installed`. Only AGENTS.md guards it; hooks and CI call `python -m pytest` directly.
2. The benchmark stays at 153/153, and only timing changes. `evaluation/harness/diff_results.py::main` exits 1 on any verdict change, unmapped disagreement or reopened fixed cluster. Field-level equality is a manual check that ignores `secs`. Not in CI.
3. The oracle and scenarios are never edited to make results pass. `evaluation/benchmark/build.py` (`--check`) fails if a label disagrees with the oracle. Rule source: `.claude/skills/benchmark-audit/SKILL.md`.
4. Tests never change committed or personal data. Enforced by `tests/conftest.py::_guard_committed_recipe_data` and `tests/conftest.py::_guard_personal_profile`.
5. The OpenAPI snapshot matches the code, and changes are additive. Guarded by CI's `--check` and `.claude/hooks/check_contract.py`.
6. The planner stays deterministic. Guarded by `.claude/hooks/check_determinism.py` (static) and the hash-seed rerun in `.claude/hooks/verify_stop.py::_run_backend_gates`.
7. LLM output schemas carry no nutrition numbers (`PlannerTargets` and `PlannerConstraints` exempt). Enforced by `.claude/hooks/check_llm_lane.py`.

## Depends on / used by
`evaluation/harness/run_benchmark.py` imports `src.api.server`, `src.planning.planner`, the converters, the meal-prep repository and `src.llm.tag_repository`. `evaluation/harness/compare.py` imports the tag repository, `src/planning/phase4_scoring.py::MEAL_ROLE_SLUGS` and oracle helpers. The oracle, build and library modules use only the standard library. The data-track and LLM-overhaul harnesses import `src/`. Hooks import only `.claude/hooks/_common.py` and shell out to .venv/bin/python.

## Known gaps and traps
- CI pins Python 3.11 while `.python-version` says 3.12.
- CI runs neither the benchmark nor Flutter. Flutter is checked only by the Stop hook, and only when `flutter` is on PATH. `flutter test` can rewrite `frontend/pubspec.lock` (restore it).
- The committed results embed a pydantic docs URL (errors.pydantic.dev/2.13) in MB-108's `detail`. A different pydantic version gives a non-timing diff in `results.json` that `evaluation/harness/diff_results.py` does not flag, because it compares verdicts only.
- `evaluation/benchmark/library.py` and `evaluation/benchmark/build.py` read the gitignored .cache/ingredients folder, so a fresh clone cannot rebuild the library (KeyError). Running, comparing and diffing work from committed files.
