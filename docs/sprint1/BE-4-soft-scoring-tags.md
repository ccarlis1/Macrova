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
