# BE-4 — Soft scoring: preferred tags + variety

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** BE-3

## Summary

Add soft scoring contributions for preferred-tag matches and last-N-days variety to `phase4_scoring`. Keep macro and time-fit scoring intact.

## Context

Hard constraints (BE-3) prune to a pool; BE-4 picks the best from it. Preferred tags let slots express "prefer but don't require" without inflating hard constraints. Variety penalty prevents the planner from picking the same recipe Mon/Tue/Wed when better variety exists.

## Acceptance criteria

- [ ] `phase4_scoring.py` gains two contributions, behind weights in a small `ScoringConfig`:
  - `preferred_tag_bonus`: `+w_pref * |slot.preferred_tags ∩ recipe.tag_slugs|`.
  - `variety_penalty`: `-w_var` if `recipe.id` appeared in any of the last 3 days' planned meals (meal-prep source exempt).
- [ ] Deficit-aware nutrition preference is supported as a soft signal: when profile/tracker indicates a micronutrient deficit, matching curated nutrition slugs (for example `high-omega-3`, `high-fiber`, `high-calcium`) increase score via preferred-tag bonus.
- [ ] Default weights: `w_pref = 1.0`, `w_var = 2.0`. Tuned via tests and adjustable in `ScoringConfig`.
- [ ] Tie-break order on equal score: `(higher preferred match count, lower recipe.id lexicographic, seeded RNG)`. Documented in a top-of-file comment in `phase4_scoring.py`.
- [ ] Tests in `tests/planning/test_scoring.py`:
  - Preferred-tag match actually changes selection when hard pool has 2+ candidates.
  - Variety penalty causes a different pick on day 2 when day 1 used a candidate.
  - Meal-prep batch in day 1 does NOT trigger variety penalty for the same recipe being planned on day 2 by non-batch path (it's allowed).
  - Micronutrient deficit scenario prefers matching `high-*` nutrition tags when candidates are otherwise similar.
- [ ] Regression: with preferred tags, the chosen recipe carries them > 80 % of the time across a 7-day fixture test.

## Implementation notes

- Use the existing `rng` passed through the orchestrator; never instantiate a new `random.Random()`.
- Pull "last 3 days' planned meals" from the plan state already built; don't re-scan the recipe pool.
- Keep the scoring function pure and unit-testable; no I/O.

## Out of scope

- Preferred tags on day-level (only slot-level).
- Dynamic weight learning from user feedback (future).
- Any UI.
- Hard-requiring micronutrient tags for all plans.

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/planning/planner.py` — identify whether `phase4_scoring.py` is imported here or whether scoring logic lives inline; **the architecture snapshot does not confirm `phase4_scoring.py` as a separate file — verify at implementation time**
- `src/planning/phase0_models.py` — `PlanningUserProfile` (has `schedule -> List[List[MealSlot]]` with `preferred_tag_slugs` from DM-4) and `PlanningRecipe`; these are the input types to scoring
- `src/models/schedule.py` — `MealSlot.preferred_tag_slugs` (DM-4 output); the scoring function reads this field

**Entities to reuse:**
- The existing `rng` instance threaded through the orchestrator/planner — do not instantiate a new `random.Random()`
- "Last N days' planned meals" from the plan state already built — do not re-scan the recipe pool

**Do NOT create:**
- A new `random.Random()` instance anywhere in this task
- I/O inside the scoring function — keep it pure and unit-testable

**Verification required:** Confirm whether `phase4_scoring.py` exists as a separate file before creating it. If scoring is inline in `planner.py`, extend it there; if a separate file exists, extend that.

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/planning/planner.py` in full.** Identify where recipe scoring/selection happens. Determine if it delegates to a separate module or if scoring is inline.
2. **Search for `phase4_scoring`** in the codebase to confirm whether this file exists.
3. **Read `src/planning/phase0_models.py`.** Confirm `PlanningUserProfile` and `PlanningRecipe` field names relevant to scoring (preferred tags, recipe id).
4. **Identify how `rng` is currently threaded** through the planner — find its type and where it's initialized.
5. **Identify how "previous days' meals" are tracked** in the current plan state to implement the variety penalty without a re-scan.
6. State the file to extend (or create if `phase4_scoring.py` truly doesn't exist), the `ScoringConfig` dataclass fields, and the two scoring contribution formulas before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `ScoringConfig` with `w_pref = 1.0` and `w_var = 2.0` exists and is the sole source of weight values
- [ ] `preferred_tag_bonus = w_pref * |slot.preferred_tags ∩ recipe.tag_slugs|` — verify with a unit test
- [ ] `variety_penalty = w_var` if `recipe.id` appeared in any of the last 3 planned days — **meal-prep-sourced assignments are exempt**
- [ ] Scoring function has no I/O — pure function, all inputs passed as parameters
- [ ] The existing `rng` is reused; no `random.Random()` instantiation in this task
- [ ] Tests pass: preferred-tag match changes selection, variety penalty causes different day-2 pick, meal-prep exemption, micronutrient deficit scenario
- [ ] Regression: with preferred tags, chosen recipe matches > 80% of the time on a 7-day fixture
- [ ] Tie-break order documented in a top-of-file comment in the scoring module
