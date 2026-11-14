# BE-16 — Profile → PlanRequest keeps workout slots (CLI/API parity)

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** —

## Summary

`build_plan_request_from_profile` drops the profile's workout slots, so the "same" plan request gives FM-1 in the CLI and FM-4 over HTTP. Emit canonical `schedule_days` (workouts included) instead of the legacy `schedule` dict.

## Context

Follow-up 9 said: "CLI and API disagree on the committed profile (CLI FM-1, API FM-4). Find the cause before planning a fix." Root cause, found on 2026-11-14:

- `config/user_profile.yaml` has a legacy flat schedule with `"08:00": 0` (a workout). `config/user_profile.yaml.example` has the same settings (checked 2026-11-14), and under W7 it is the profile this task targets.
- `UserProfileLoader.load()` turns it into:
  - `schedule = {"07:00": 4, "12:00": 4, "18:00": 4}`, with the workout dropped;
  - `schedule_days[0].workouts = [WorkoutSlot(after_meal_index=1, type="AM")]`, with the workout kept.
- The CLI plans from `schedule_days` (via `convert_profile`), so the workout is in.
- `src/planning/orchestrator.py::build_plan_request_from_profile` (line ~143) writes `"schedule": dict(profile.schedule)`, so the workout is gone. That payload is what `scripts/export_planner_debug_artifacts.py` writes as `cli_plan_request.json` and what the parity procedure tells you to POST to the API.

Probe, committed profile, 1 day, deterministic (`TestClient` against `/api/v1/plan`):

| Request | Result |
|---|---|
| CLI | `TC-2`, FM-1 at slot 2 (`Empty candidate set or FC-5`) |
| `build_plan_request_from_profile` payload | `TC-2`, **FM-4** (`cause: nutrient_gap`) |
| same payload with `"08:00": 0` added back | `TC-2`, **FM-1 at slot 2** (`cause: macro_gap`), matching the CLI |
| same payload with `liked_foods: []` | FM-4: `liked_foods` is **not** the cause |

Reproduce with `.venv/bin/python docs/sprints/sprint2/probes/parity_probe.py 1 as_is` (and `workout`, `no_liked`). The `workout` variant edits the legacy `schedule` key, so after this fix it needs updating to the `schedule_days` form.

ULs are **not** the cause either: neither the CLI nor the API passes `resolved_ul` today (see BE-17).

Why the existing parity test misses it: `tests/integration/test_cli_flutter_parity.py` calls `build_plan_request_from_profile` for both the "HTTP" and "CLI" payloads, so it compares the function with itself.

## Acceptance criteria

- [ ] `build_plan_request_from_profile` emits `schedule_days` (the `DaySchedule` JSON shape `PlanRequest` accepts: meals and workouts), built from `profile.schedule_days`, and no longer emits `schedule`. Test: `tests/test_orchestrator.py` (or the existing orchestrator test module) asserts that a profile with a workout produces `schedule_days[0]["workouts"] == [{"after_meal_index": 1, ...}]`. This fails today because the key is absent.
- [ ] The payload is a valid `PlanRequest`: `PlanRequest.model_validate(payload)` succeeds, including `days` / `schedule_days` length agreement for 1 and 3 days.
- [ ] New parity test in `tests/integration/test_cli_flutter_parity.py` runs the CLI planning path (`convert_profile` + `plan_meals`) and `POST /api/v1/plan` with the builder's payload against the same fixture profile (with a workout) and fixture pool. It asserts the same `termination_code` and the same list of `(code, day_index, slot_index)` failures. This fails before the fix (FM-1 vs FM-4 shape).
- [ ] `scripts/export_planner_debug_artifacts.py` output still loads, and `cli_plan_request.json` now contains `schedule_days`.
- [ ] `benchmark-audit`: 153/153, 0 regressions (`diff_results.py --base main` exits 0).

## Implementation notes

### 🔒 Implementation contract
- Files to inspect: `src/planning/orchestrator.py` (`build_plan_request_from_profile`); `src/cli.py` (~lines 355–450); `src/api/server.py` (`_build_user_profile`, ~line 900, and the `/api/v1/plan` endpoint, ~line 1205, which also calls the builder at ~1262 for debug logging); `src/models/legacy_schedule_migration.py`; `scripts/export_planner_debug_artifacts.py`; `tests/integration/test_cli_flutter_parity.py`.
- Entities to reuse: `DaySchedule`, `MealSlot`, `WorkoutSlot` and their existing serialization. Do not hand-build dicts if a `model_dump` exists.
- Do NOT create: a new request-builder function, or a second schedule conversion helper.

### 🧠 Pre-implementation analysis
1. Confirm `profile.schedule_days` is always populated by `UserProfileLoader.load()` for both legacy and canonical YAML. `REQUIRES_VERIFICATION`: run `UserProfileLoader("config/user_profile.yaml.example").load().schedule_days`.
2. For `days > 1`, decide how the one-day template expands. The CLI's `convert_profile(user_profile, days)` replicates it; mirror whatever it does, and record that in the test.
3. Check every caller of the builder (4 call sites plus tests) for a reader of `payload["schedule"]`.

### ✅ Post-implementation validation
- `python3 scripts/run_pytest.py`
- `python3 scripts/run_export_openapi.py --check` (no API shape change expected)
- `benchmark-audit` skill: 153/153, 0 regressions
- Re-run the probe: CLI and API agree on `config/user_profile.yaml.example` for 1 and 3 days.

## Out of scope

- Changing either profile file. BE-20 applies the D-A default to the `.example` and untracks `config/user_profile.yaml` (W7). Run BE-16 before BE-20, so the example still has the legacy schedule with the workout. If BE-20 lands first, put a workout fixture in the test instead of relying on the example.
- UL enforcement (BE-17).
- Why the committed profile fails at all (D-A / BE-20).
