# BE-2 — Meal-prep batch locks in planner path

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-3, DM-4

## Summary

Wire **`MealPrepBatch`** assignments as **locked `(day_index, slot_index) → recipe_id`** into the **existing** deterministic planner pipeline (`PlanningUserProfile` / `plan_meals` / `phase7_search`), at the **same addressing scheme** as **`pinned_assignments`**.

## Context

Batches must not pre-fill via a shadow `plan()` helper. Locks integrate with orchestrator + `MealPlanResult` reporting (architecture-aligned).

Unblocks: BE-5, FE-3, FE-7.

## Acceptance criteria

- [ ] Active batches loaded server-side and passed into the planning entrypoint (exact parameter: **REQUIRES_VERIFICATION** against `planner.plan_meals` signature at implementation time).
- [ ] Batch assignment addressing is canonical `SlotAddress = (day_index, slot_index)` end-to-end (no `date`/`slot_id` writes in planner contracts).
- [ ] Batch lock **precedence** vs pins vs required tags matches `docs/SPRINT_1.md` §3.5.
- [ ] Two batches targeting same `(day_index, slot_index)` → `FM-BATCH-CONFLICT` in extended `MealPlanResult.report`.
- [ ] Locked slots skipped by free search; nutrition totals include locked meals.
- [ ] Tests: 3-day batch spread; conflict; tag mismatch → warning in report (not hard fail).

## Implementation notes

- Prefer reusing `pinned_assignments` merge semantics internally (implementation detail) **or** a dedicated `batch_locks` dict merged with explicit precedence — document choice in code comment.
- Determinism: sort batch ids and assignments before merge.
- This task only injects/merges locks and conflict reporting; slot-level required-tag enforcement belongs to BE-8.
- Do **not** name-drop phase files not confirmed in `architecture.json`; hook at **`planner.py` / `phase0_models.py`** level unless repo audit adds phase modules to the snapshot.

## Out of scope

- Creating batches inside planner.
- Auto-placement of batch servings without user-selected slots.

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/planning/planner.py` — `plan_meals(profile, recipe_pool, days, ...)` function signature; this is the integration point; read its full signature before deciding how to pass batch locks
- `src/planning/phase0_models.py` — `PlanningUserProfile` has `pinned_assignments` field; batch locks integrate at this level using the same addressing scheme `(day_index, slot_index) → recipe_id`
- `src/planning/orchestrator.py` — `plan_with_llm_feedback(...)` wraps `plan_meals`; confirm whether batch locks are passed here or at the `plan_meals` level
- `src/data_layer/meal_prep.py` — `MealPrepBatchRepository` (DM-3 output); `list_active()` is called to load active batches before building the plan request

**Entities to reuse:**
- `PlanningUserProfile.pinned_assignments` addressing scheme from `src/planning/phase0_models.py` — batch locks use the same `(day_index, slot_index)` addressing
- `MealPlanResult` (referenced in `orchestrator.py`) — `report` field must include `FM-BATCH-CONFLICT` entries

**Do NOT create:**
- A shadow `plan()` helper separate from the existing planner pipeline
- A new planning phase file not confirmed in `architecture.json` — integrate at the `planner.py` / `phase0_models.py` level

**Verification required:** The acceptance criteria explicitly note the `plan_meals` parameter for batch locks is **REQUIRES_VERIFICATION** — read `planner.py` signature at implementation time and document the chosen parameter in a code comment.

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/planning/planner.py` in full.** Record the exact signature of `plan_meals`. Identify where `pinned_assignments` is consumed — this is where batch locks will be merged.
2. **Read `src/planning/phase0_models.py` in full.** Confirm `PlanningUserProfile.pinned_assignments` type, format, and how the planner reads it.
3. **Read `src/planning/orchestrator.py`.** Determine if batch locks should be injected at the `plan_meals` level or the `orchestrator` level; note `MealPlanResult.report` structure.
4. **Read `src/data_layer/meal_prep.py` (DM-3 output).** Confirm `list_active()` return type.
5. **Determine conflict detection point:** where in the planning pipeline a `(day_index, slot_index)` with two competing batch lock assignments should be caught and emit `FM-BATCH-CONFLICT`.
6. State the chosen integration point (exact function + parameter name) before writing any code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] Active batches are loaded via `MealPrepBatchRepository.list_active()` before `plan_meals` is called — not inside the planner itself
- [ ] Batch locks use the same `(day_index, slot_index)` addressing as `pinned_assignments` — no new addressing scheme
- [ ] Precedence matches `docs/SPRINT_1.md §3.5`: batch locks take specified precedence vs. pins vs. required tags
- [ ] Two batches targeting the same `(day_index, slot_index)` produce `FM-BATCH-CONFLICT` in `MealPlanResult.report` — not a hard exception
- [ ] Locked slots are skipped by free recipe search; their nutrition is included in daily totals
- [ ] Tests pass: 3-day batch spread, conflict detection, tag-mismatch warning (not hard fail)
- [ ] No new phase files were created that are not referenced in `architecture.json`
