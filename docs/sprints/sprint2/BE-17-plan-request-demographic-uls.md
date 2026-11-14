# BE-17 — Optional `demographic` on PlanRequest enforces daily ULs

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** P0 (Flutter DTO part only)

## Summary

Add an optional `demographic` to `PlanRequest`. When set, resolve daily upper limits with the same loader and reference file the MCP server uses, and pass them to `plan_meals(..., resolved_ul=...)`. Make the CLI do the same from the profile YAML's `demographic`. Have Flutter send the Profile screen's demographic, restricted to the demographics the reference data has.

## Context

Follow-ups 8 and 6. AGENTS.md says "Daily upper limits (ULs) are enforced per-day", but on 2026-11-14 only the MCP server passes `resolved_ul`:

- **HTTP API:** `/api/v1/plan` calls `plan_meals(planning_profile, recipe_pool, days)` with no ULs (`src/api/server.py` ~line 1282; also ~1486 for plan-from-text).
- **CLI:** `src/cli.py` ~line 434 builds `resolved_ul` for a hard-coded `adult_male`, then calls `plan_meals(planning_profile, recipe_pool, args.days)` without it. The variable is dead. The YAML `demographic:` key is never read (`grep demographic src/data_layer/user_profile.py` finds nothing).
- **MCP:** `src/mcp_server/tools.py` ~line 519: `upper_limits(targets.demographic)` → `resolve_upper_limits(UpperLimitsLoader(UL_PATH), demographic=...)`.
- **Flutter:** `UserProfile.demographicGroup` is saved locally and never sent. The Profile picker offers `adult_male`, `adult_female`, `teen_male`, `teen_female`, `child`, `pregnancy`, `lactation`, but `ul_by_demographic.json` and `rdi_by_demographic.json` contain only **`adult_male`, `adult_female`, `pregnancy`, `lactation`**.

## Acceptance criteria

- [ ] `PlanRequest.demographic: Optional[Literal["adult_male","adult_female","pregnancy","lactation"]] = None` (or the MCP `Demographic` type, moved somewhere both can import; see notes). Additive.
- [ ] When `demographic` is set, `/api/v1/plan` and `/api/v1/plan-from-text` pass `resolved_ul` for it into every `plan_meals` / `plan_with_llm_feedback` call. Test in `tests/api/`: a fixture pool where the only calorie-feasible plan exceeds the sodium UL. With `demographic: "adult_male"` the plan fails (UL failure code); without it, it succeeds. Fails before the change.
- [ ] When `demographic` is unset, behavior is byte-identical to today: the existing plan contract tests stay green with no fixture changes.
- [ ] Unknown demographic → 400 `INVALID_REQUEST` (Pydantic literal). Test.
- [ ] `demographic` does **not** set `micronutrient_goals` in this task. RDIs-from-demographic is D-A/BE-20's call. Test: the request with only `demographic` has no weekly micronutrient floors in the planning profile.
- [ ] CLI: `UserProfileLoader` reads the YAML `demographic` (optional). The CLI passes `resolved_ul` for it in both deterministic and assisted paths; no demographic means no ULs (today's actual behavior). Remove the hard-coded `adult_male` and the dead variable. Test in `tests/test_cli.py` (or the existing CLI test module), asserting `plan_meals` receives `resolved_ul` when the YAML sets a demographic.
- [ ] `build_plan_request_from_profile` carries `demographic`, so BE-16's parity test also covers ULs. If BE-16 has merged, extend its parity test with a demographic.
- [ ] One UL resolution path: the API, CLI and MCP all call one helper. Move `daily_rdis`/`upper_limits` and the reference paths from `src/mcp_server/nutrients.py` to `src/data_layer/upper_limits.py` (or a sibling in `data_layer`), and make `mcp_server/nutrients.py` re-export or import them. Test: the existing `tests/mcp_server` tests still pass unchanged.
- [ ] OpenAPI regenerated (`python3 scripts/run_export_openapi.py`), `--check` green, `tests/test_api_v1_and_openapi.py` asserts `demographic` is in the `PlanRequest` schema.
- [ ] Flutter (after P0):
  - `PlanRequest` DTO (`frontend/lib/models/models.dart` ~line 182) gains `demographic` and serializes it only when non-empty.
  - `planner_config_screen.dart` (~line 345) passes `profile.demographicGroup`.
  - The Profile picker offers only the 4 supported values, plus "Not set". A saved unsupported value (`teen_*`, `child`) loads as "Not set" and isn't sent.
  - Tests: `test/plan_request_tag_contract_test.dart` (or a new `plan_request_demographic_test.dart`) for serialization, and `test/screens/profile_screen_test.dart` for the picker options.
- [ ] `benchmark-audit`: 153/153, 0 regressions. The harness should not set a demographic; if it does, stop and report.
- [ ] `cd frontend && flutter analyze && flutter test` green.

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `src/api/server.py` (`PlanRequest` ~line 148, `_build_user_profile` ~line 900, plan endpoints ~1205 and ~1368), `src/cli.py` (~355–470), `src/data_layer/upper_limits.py`, `src/data_layer/user_profile.py` (`UserProfileLoader.load`), `src/mcp_server/nutrients.py`, `src/mcp_server/models.py` (`Demographic`), `src/planning/planner.py` (`plan_meals` signature), `src/planning/orchestrator.py` (`plan_with_llm_feedback` — `REQUIRES_VERIFICATION`: does it accept `resolved_ul`? It calls `plan_meals(profile, recipe_pool, days)` at ~lines 452 and 628 with none. If not, thread it through as an optional parameter).
- Entities to reuse: `UpperLimitsLoader`, `resolve_upper_limits`, the MCP `Demographic` literal.
- Do NOT create: a second UL loader, or a demographic enum that duplicates the MCP one.

### 🧠 Pre-implementation analysis
1. Confirm which UL failure code the planner emits when ULs bind (FM-? / `FC-3` incremental UL in `phase9_carb_scaling.py`, `phase6_candidates.py`). Use it in the test.
2. Find a fixture pool small enough that sodium (or another UL) is the binding constraint. Write it inline in the test.
3. `REQUIRES_VERIFICATION`: whether `UserProfile` (data layer) has a field for demographic, or needs one added (optional, default `None`).

### ✅ Post-implementation validation
- `python3 scripts/run_pytest.py`; `python3 scripts/run_export_openapi.py --check`
- `benchmark-audit`: 153/153, 0 regressions
- `cd frontend && flutter analyze && flutter test`

## Out of scope

- Setting RDIs from demographic over HTTP (D-A / BE-20).
- Adding teen/child demographics to the reference data (needs human-reviewed DRI values).
- UL overrides per user.
