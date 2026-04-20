# BE-7 — Failure-code surfacing

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** BE-2, BE-3

## Summary

Finalize the error JSON shape for planner failures so Flutter can render actionable recovery surfaces (see FE-9).

## Context

Planner failures today are opaque. Sprint 1 ships three user-actionable modes: `FM-TAG-EMPTY`, `FM-BATCH-CONFLICT`, `FM-MACRO-INFEASIBLE`. Each needs enough context in the response for the UI to render a one-line fix.

Unblocks: FE-9.

## Acceptance criteria

- [ ] Planner `report` includes a `failures: List[Failure]` list even on success (empty list). Each `Failure`:
  ```json
  {
    "code": "FM-TAG-EMPTY",
    "slot_id": "workout.meal_3",
    "date": "2026-04-20",
    "details": { "missing_tag": "pre-workout", "recipe_count": 0 },
    "fix_hint": "No recipes match tag `pre-workout`. Add one or relax constraints."
  }
  ```
- [ ] `FM-BATCH-CONFLICT` details: `{batch_ids: [..], date, slot_id}`.
- [ ] `FM-MACRO-INFEASIBLE` details: `{date, deltas: {calories: -300, protein_g: -25, ...}}`.
- [ ] Codes registered in `src/api/error_mapping.py` and in the OpenAPI component schemas.
- [ ] Documented in `docs/DEBUG_PLANNER_PARITY.md` (append a "Failure modes" section).
- [ ] Tests:
  - Each failure mode is reachable from a crafted input and returns the exact shape.
  - `fix_hint` strings are stable (snapshot test) so UI copy doesn't drift silently.

## Implementation notes

- Keep `fix_hint` server-side so copy lives in one place and is testable. Flutter can override for i18n later.
- Do not mix partial-success and failure: a plan that succeeds with warnings is `termination_code="OK"` + `report.warnings`; only a plan the user must act on is a failure.

## Out of scope

- LLM-driven auto-recovery (Week 2+).
- i18n of fix hints.

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/planning/planner.py` — `plan_meals` return type (`MealPlanResult`); identify the `report` field structure and where `termination_code` is set
- `src/planning/orchestrator.py` — `plan_with_llm_feedback` return type; confirm it propagates `MealPlanResult.report` unchanged to the HTTP response
- `src/api/server.py` — `POST /api/v1/plan` response formatter; this is where `failures` appears in the JSON response
- `src/api/error_mapping.py` — register `FM-TAG-EMPTY`, `FM-BATCH-CONFLICT`, `FM-MACRO-INFEASIBLE` codes here
- `docs/DEBUG_PLANNER_PARITY.md` — append a "Failure modes" section

**Entities to reuse:**
- `MealPlanResult.report` from `src/planning/planner.py` — extend it with `failures: List[Failure]`; do not create a separate response envelope
- Existing `termination_code` field — `"OK"` + non-empty `warnings` is distinct from a `failures` entry; keep this distinction

**Do NOT create:**
- A separate failure-response model outside `MealPlanResult.report`
- LLM-driven recovery logic

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/planning/planner.py` in full.** Find `MealPlanResult` definition. Note the current `report` structure and `termination_code` usage.
2. **Read `src/planning/orchestrator.py`.** Confirm `MealPlanResult` flows to the HTTP handler without transformation.
3. **Read `src/api/server.py`.** Find `format_result_json(...)` (or equivalent) to understand how the plan result is serialized to the HTTP response body.
4. **Read `src/api/error_mapping.py`.** Confirm none of the three new failure codes already exist.
5. **Read `docs/DEBUG_PLANNER_PARITY.md`.** Find the right place to append the "Failure modes" section.
6. State the exact `Failure` dataclass/Pydantic model field names and the three failure code payloads before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `MealPlanResult.report` has a `failures: List[Failure]` field; it is `[]` on a fully successful plan
- [ ] `Failure` has `code`, `slot_id`, `date`, `details`, `fix_hint` fields matching the JSON shape in the acceptance criteria
- [ ] `FM-TAG-EMPTY` details include `{missing_tag, recipe_count}`; `FM-BATCH-CONFLICT` includes `{batch_ids, date, slot_id}`; `FM-MACRO-INFEASIBLE` includes `{date, deltas}`
- [ ] All three codes are registered in `src/api/error_mapping.py` and appear in OpenAPI component schemas
- [ ] A plan with `termination_code="OK"` and warnings has `failures: []` — the two lists are not conflated
- [ ] `docs/DEBUG_PLANNER_PARITY.md` has a new "Failure modes" section
- [ ] Tests pass: each failure mode is reachable from a crafted input; `fix_hint` strings are snapshot-tested
