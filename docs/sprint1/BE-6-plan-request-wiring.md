# BE-6 — Planner request wiring

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** BE-2, BE-3, BE-5

## Summary

Populate `PlanRequest.active_batches` server-side from the batch repository so CLI and Flutter produce identical plans without the client needing to know about batches.

## Context

Parity (G7) requires both entry paths (CLI via `plan_meals.py`, Flutter via `POST /api/v1/plan`) to feed the same input into the planner. The simplest way to achieve that is: the server always hydrates `active_batches` from the repository; the CLI path calls the same orchestrator entry point.

## Acceptance criteria

- [ ] `POST /api/v1/plan` handler fetches `active_batches = repo.list_active()` before calling the orchestrator.
- [ ] CLI `plan_meals.py` and `scripts/export_planner_debug_artifacts.py` do the same via a shared helper (e.g. `src/planning/orchestrator.py::build_plan_request_from_profile`).
- [ ] `cli_plan_request.json` emitted by the export script includes `active_batches` explicitly (empty list is valid).
- [ ] `DEBUG_PLANNER_PARITY.md` updated with one paragraph + a row in the artifacts table about `active_batches`.
- [ ] Parity test `tests/integration/test_cli_flutter_parity.py`:
  - Same profile, same `recipes.json`, same batch fixture, same `seed` → identical `recipe_ids_sha256` AND identical sequence of planned meals.

## Implementation notes

- The helper should take `(profile, recipes, batches, seed)` and return a fully built `PlanRequest`. Keep the CLI and HTTP handler thin.
- Do not accept `active_batches` from the Flutter client — server-populated only (trust boundary + avoids drift). If a client sends them, log a warning and ignore.
- `seed` default remains `hash((profile_version, week_start_date))`.

## Out of scope

- Changing the Flutter `ApiService.plan` body shape visibly (still works with whatever it sends today, minus any batch fields).

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/api/server.py` — `POST /api/v1/plan` handler; this is where `repo.list_active()` is called and the result is injected before passing to the orchestrator
- `src/planning/orchestrator.py` — `plan_with_llm_feedback(profile, recipe_pool, days, ...)` signature; confirms how `active_batches` is passed in
- `src/planning/planner.py` — `plan_meals(...)` signature; confirm if `active_batches` flows here or stays at the orchestrator level
- `src/data_layer/meal_prep.py` — `MealPrepBatchRepository.list_active()` (DM-3 / BE-5 output)
- `scripts/export_planner_debug_artifacts.py` — must be updated to emit `active_batches` in `cli_plan_request.json`
- `docs/DEBUG_PLANNER_PARITY.md` — append one paragraph + artifacts table row

**Entities to reuse:**
- `plan_with_llm_feedback` or `plan_meals` entry point — the shared helper `build_plan_request_from_profile` wraps these; do not create a second planning entry point

**Do NOT:**
- Accept `active_batches` from the Flutter client — server-populated only; if a client sends them, log a warning and ignore
- Change the visible shape of `frontend/lib/services/api_service.dart` plan request body

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/api/server.py`.** Find the `POST /api/v1/plan` handler in full. Identify the exact call chain from HTTP handler → orchestrator → planner.
2. **Read `src/planning/orchestrator.py`.** Confirm the `plan_with_llm_feedback` signature and where `active_batches` should be injected.
3. **Check whether `scripts/export_planner_debug_artifacts.py` exists** and read it — this script must be updated to emit `active_batches`.
4. **Check whether `src/planning/orchestrator.py::build_plan_request_from_profile` already exists** or must be created.
5. **Read `docs/DEBUG_PLANNER_PARITY.md`.** Identify the artifacts table to append the `active_batches` row.
6. State the shared helper signature and each call site before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `POST /api/v1/plan` fetches `active_batches = repo.list_active()` before calling the orchestrator — not after
- [ ] CLI and Flutter paths share the same `build_plan_request_from_profile` (or equivalent) helper — no duplicated orchestration logic
- [ ] `cli_plan_request.json` emitted by the export script includes `active_batches` (can be `[]`)
- [ ] If Flutter client sends `active_batches` in its payload, server logs a warning and ignores it
- [ ] `docs/DEBUG_PLANNER_PARITY.md` has a new "active_batches" row in the artifacts table
- [ ] Parity test passes: same profile + same `recipes.json` + same batch fixture + same `seed` → identical `recipe_ids_sha256` and meal sequence
