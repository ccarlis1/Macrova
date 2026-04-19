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
