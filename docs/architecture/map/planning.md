# Planning — deterministic backtracking meal planner with structured failure attribution

Status: implemented · Code: `src/planning/` · Facts: [generated/planning.md](generated/planning.md)

## Purpose
Turns a planning profile (targets, 1–7 day schedule, pins, batch locks) and a pre-computed recipe pool into one result object: a full plan, or a structured failure with an FM-* code and fix hint. Search is depth-first over (day, slot) in fixed order with chronological backtracking; no LLM, network or wall clock affects the outcome. An optional outer loop asks an LLM for recipes after a failure, but the planner stays the authority.

## Entry points
- `src/planning/planner.py::plan_meals` — public API. Callers: `src/api/server.py::plan_meals_endpoint` (POST /api/v1/plan) and `src/api/server.py::plan_from_text_endpoint` in deterministic mode, `src/cli.py::main`, `src/mcp_server/tools.py::plan_meals`, `evaluation/harness/run_benchmark.py::run`, `scripts/export_planner_debug_artifacts.py`. Returns `src/planning/phase10_reporting.py::MealPlanResult`; raises ValueError on bad horizon or schedule length.
- `src/planning/orchestrator.py::plan_with_llm_feedback` — assisted modes in the same API routes and CLI. Runs `plan_meals` first; returns that result unchanged on success or on a non-recoverable code (`src/planning/orchestrator.py::_ELIGIBLE_FAILURE_MODES`).
- `src/planning/phase7_search.py::run_meal_plan_search` — raw search without lock merge; only `scripts/benchmark_meal_plan_search.py` and tests call it.
- `src/planning/converters.py::convert_profile` / `src/planning/converters.py::convert_recipes` — input builders, normally reached via `src/api/server.py::build_plan_inputs` (API and MCP) or the CLI.

## How it works
1. **Inputs** (`src/planning/converters.py`): the provider resolves ingredients *before* conversion. `convert_recipes` precomputes nutrition, drops recipes with unresolved ingredients, sorts by id. `convert_profile` expands allergies (`src/planning/allergens.py::expand_allergy_terms`), adds dislikes and dietary-flag exclusions, replicates the schedule to D days, keys pins as (day_1based, slot). Callers attach tag sets and batch locks.
2. **Batch merge** (`src/planning/planner.py::_merge_batch_locks_into_pins`): two locks on one slot → FM-BATCH-CONFLICT; locks overwrite pins; a lock missing a slot's required tags is only a `BATCH_TAG_MISMATCH` warning.
3. **Pin pre-validation** (`src/planning/phase1_state.py::validate_pinned_assignments`): HC-1/2/3/5/6/8 → FM-3 (direct).
4. **Static precheck** (`src/planning/phase7_search.py::_static_slot_precheck` → `src/planning/phase6_candidates.py::check_slot_statically`): a free slot with no HC-1/HC-3 recipe → FM-1; none with its required tags → FM-TAG-EMPTY.
5. **Initial state** (`src/planning/phase1_state.py::build_initial_state`); a fully pinned day failing daily validation → FM-3 (downstream).
6. **Feasibility precompute** (`src/planning/phase3_feasibility.py`): macro bounds, micronutrient floor bounds (tight when per-day enumeration fits its budget), structural check → FM-4 pre-search.
7. **Search loop**: FC-4 at each day start; pinned slots apply directly (variant 0); free slots get `src/planning/phase6_candidates.py::generate_candidates` (required tags, HC-1/2/3/5/8, FC-1/2/3, optional carb variants, FC-5 look-ahead), `src/planning/phase4_scoring.py::composite_score`, `src/planning/phase5_ordering.py::ordering_key`, floor pruning, then a cached ordered list with a pointer.
8. **Day completion**: `src/planning/failure_attribution.py::daily_validation` (±10% kcal/protein/carbs, fat range, calorie ceiling, per-day ULs); fail → backtrack.
9. **Plan completion**: `src/planning/phase7_search.py::_weekly_validation` against τ-scaled floors, plus sodium advisory.
10. **Exit**: success → TC-4 (D=1) or TC-1; attempt limit → FM-5/TC-3; exhaustion → `src/planning/phase7_search.py::_attributed_exhaustion_result` (diagnosis, else last-event code).
11. **Reporting** (`src/planning/phase10_reporting.py`): builders; `src/planning/phase10_reporting.py::normalize_planner_report` guarantees `failures[]`; `src/output/formatters.py::format_result_json` derives `plan_status`.

## Modules
| Module | Role | Status |
|---|---|---|
| `src/planning/planner.py` | Public API, horizon check, lock → pin merge | implemented |
| `src/planning/phase0_models.py` | Dataclasses, schedule/horizon validators | implemented |
| `src/planning/phase1_state.py` | Pin validation, initial state, adjusted and per-meal targets | implemented |
| `src/planning/phase2_constraints.py` | HC predicates | implemented; HC-4/HC-6 predicates are test-only |
| `src/planning/phase3_feasibility.py` | FC-1…FC-4, macro/micro bounds | implemented |
| `src/planning/phase4_scoring.py` | Five weighted components, tag/meal-type bonus, variety penalty | implemented |
| `src/planning/phase5_ordering.py` | Tie-break sort key | partial: spec rules 1–3 not wired |
| `src/planning/phase6_candidates.py` | Candidate set C(d,s), static slot check, FC-5 | implemented |
| `src/planning/phase7_search.py` | Search loop, backtracking, exit assembly | implemented |
| `src/planning/phase9_carb_scaling.py` | Scaled rice/potato variants | experimental: no production caller enables it |
| `src/planning/phase10_reporting.py` | Result type, failure builders, fix hints, warnings | implemented |
| `src/planning/failure_attribution.py` | Daily validation, post-exhaustion diagnosis | implemented |
| `src/planning/orchestrator.py` | LLM recovery loop, pin/batch/parity hydration | implemented (does I/O and network) |
| `src/planning/converters.py` | Data-layer → planning models | implemented |
| `src/planning/allergens.py` | Allergen classes, dietary-flag exclusions | implemented |
| `src/planning/micronutrient_policy.py` | τ-scaled floor helpers | implemented |
| `src/planning/slot_attributes.py` | Cook-time cap, workout context, satiety | implemented |

## Key types
- `src/planning/phase10_reporting.py::MealPlanResult` — sole result: success, termination_code, failure_mode, plan, trackers, warning, report, stats, plan_incomplete_reason.
- `src/planning/phase0_models.py::PlanningUserProfile` — targets, schedule, exclusions, pins, locks, τ.
- `src/planning/phase0_models.py::PlanningRecipe` — precomputed nutrition plus canonical and hard-eligible tag sets.
- `src/planning/phase0_models.py::MealSlot` — time, busyness, meal type, required/preferred tags.
- `src/planning/phase0_models.py::Assignment` — 0-based (day, slot, recipe_id, variant_index).
- `src/planning/phase0_models.py::PlanningBatchLock` — meal-prep lock, 0-based day.
- `src/planning/phase0_models.py::DailyTracker` / `src/planning/phase0_models.py::WeeklyTracker` — running totals, carryover.
- `src/planning/phase10_reporting.py::Failure` — `failures[]` entry shape.
- `src/planning/failure_attribution.py::Attribution` — diagnosis outcome (attributed / inconclusive).
- `src/planning/phase7_search.py::SearchStats` — opt-in instrumentation.

## Invariants
1. **Determinism.** Fixed decision order; candidate sets sorted before scoring; key = (−score, −preferred matches, recipe id, RNG seeded by the string "phase7-search-seed:{day}:{recipe_id}") in `src/planning/phase5_ordering.py::ordering_key`; diagnosis bounded by node counts, not time. Wall clock appears only in `SearchStats` paths. Guards: `.claude/hooks/check_determinism.py` (new clock/RNG/unordered-iteration sites vs baseline), `.claude/hooks/verify_stop.py` (suite rerun under another `PYTHONHASHSEED`), `tests/test_phase7_search.py`, `tests/planning/test_slot_constraints.py::test_equal_seed_deterministic_outcome`, benchmark.
2. **No network during planning.** Non-orchestrator modules import only `src/data_layer`, `src/models` and `src/nutrition`; nutrition arrives precomputed. They read local reference JSON only: `data/reference/allergen_classes.json` and, with carb scaling, `data/reference/scalable_carb_sources.json`. Only `src/planning/orchestrator.py` calls LLM/USDA, after `plan_meals` fails. Guard: import structure only; no dedicated test.
3. **Precedence: batch lock → pin → required tags → preferred scoring.** Locks overwrite pins in the merge. Pinned slots skip candidate generation, so required tags never reject a pin. Required tags filter hard via `src/planning/phase6_candidates.py::_matches_slot_required_tags` (hard-eligible set when present). Preferred tags only add score. Tests: `tests/planning/test_slot_constraints.py::test_lock_beats_pin_deterministically`, `tests/planning/test_slot_constraints.py::test_pin_beats_required_tags`, `tests/planning/test_batch_locks.py`.
4. **Success-with-warnings ≠ failure.** Success: success=True, TC-1/TC-4, empty `failures[]`. Advisories go in the result's warning dict (sodium, soft micronutrient deficit when τ<1); lock tag mismatches go in `report["warnings"]`. Failure: failure_mode set, `failures[]` non-empty. A failure that keeps a best-effort plan formats as plan_status "partial". Tests: `tests/test_phase10_reporting.py::test_success_merges_sodium_and_soft_deficit`, `tests/planning/test_batch_locks.py::test_batch_tag_mismatch_is_warning_not_failure`.
5. **FM-* codes.** Fix hints: `src/planning/phase10_reporting.py::_FIX_HINTS`. API contract: the code Literal on `src/api/server.py::PlanFailure` (FM-1…FM-5, FM-TAG-EMPTY, FM-BATCH-CONFLICT, FM-MACRO-INFEASIBLE), with prose in `src/api/failure_explanations.py`. `src/api/error_mapping.py` lists every code except FM-2 for its exception mapping, but no code raises them. FM-2 is a failure_mode value only; its `failures[]` entry is FM-MACRO-INFEASIBLE. Tests: `tests/test_phase10_reporting.py`, `tests/api/test_plan_contract.py`.
6. **Per-day ULs, never averaged.** Checked incrementally (`src/planning/phase3_feasibility.py::check_fc3_incremental_ul`) and at day completion (`src/planning/failure_attribution.py::daily_validation`). τ scales only RDI floors (`src/planning/micronutrient_policy.py::weekly_minimum_total`). Tests: `tests/test_phase3_feasibility.py`, `tests/test_phase7_search.py`.
7. **Horizon 1–7.** `src/planning/planner.py::plan_meals` raises outside 1–7 or when the schedule length differs from the day count; `src/api/server.py::PlanRequest` bounds days too. Test: `tests/test_planner_integration.py`.
8. **Failure attribution.** Step 1 runs before search (static FM-1 / FM-TAG-EMPTY). On exhaustion (never on the attempt limit), `src/planning/failure_attribution.py::diagnose_exhausted_search` finds the first infeasible day: FM-3 if it becomes feasible without its pins, else FM-2. When every day works alone, HC-8 sequencing gives FM-1 and weekly floors give FM-4. Node budget or carb scaling → inconclusive, last-event code kept. A diagnosis block is always added to the report. Test: `tests/test_failure_attribution.py`.

## Depends on / used by
Uses `src/data_layer` (models, UL validation), `src/models/schedule.py` and `src/nutrition`. The orchestrator also uses `src/llm`, `src/providers` and `src/ingestion`. Used by `src/api/server.py`, `src/cli.py`, `src/mcp_server`, `src/llm/recovery_diagnosis.py`, `src/output/formatters.py`, `evaluation/harness` and `evaluation/benchmark`. Full graph: [generated/index.md](generated/index.md).

## Known gaps and traps
- **Spec §7.1 vs code.** `docs/planner/mealplan-specification-v3.md` §7.1 orders ties by gap-fill, then deficit reduction, liked foods, preferred tags and recipe id, with no RNG. `src/planning/phase5_ordering.py::ordering_key` uses only preferred-tag count, recipe id and seeded RNG. `src/planning/phase5_ordering.py::gap_fill_count`, `src/planning/phase5_ordering.py::deficit_reduction` and `src/planning/phase5_ordering.py::liked_foods_count` exist but nothing calls them, so liked foods never affect plans. Recipe ids are unique, so the RNG only compares carb variants of one recipe (and ties there). No request carries a seed. This is an open spec question.
- **Mixed indexing.** Pin and pin-provenance keys use (day_1based, slot); assignments, locks and `failures[]` day_index are 0-based; "day-N" dates are 1-based labels.
- **Duplicated hard filters.** `src/planning/phase6_candidates.py::check_slot_statically`, the candidate filter in the same module, `src/planning/phase1_state.py::validate_pinned_assignments`, `src/llm/recovery_diagnosis.py` and `evaluation/benchmark/oracle.py::Oracle` each apply HC checks and must stay in sync.
- **Pool-level tag filters** (cuisine, cost, prep time, dietary flags) live outside this package in `src/api/server.py::_apply_recipe_tag_filter_pre_convert`.
- **Carb scaling is dormant.** `convert_profile` hard-codes the flag off and `convert_recipes` never sets a primary carb contribution, so `src/planning/phase9_carb_scaling.py::is_recipe_scalable` is always false in production.
- **Two warning channels** (result warning vs `report["warnings"]`) and two FM-2 names (failure_mode FM-2 vs `failures[]` FM-MACRO-INFEASIBLE).
