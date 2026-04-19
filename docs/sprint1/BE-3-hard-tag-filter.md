# BE-3 — Hard tag-constraint filter

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-2, DM-4, DM-5

## Summary

Replace the current ad-hoc tag filter in the planner with a typed hard-constraint filter: a recipe is a candidate for a slot iff it carries **all** of the slot's `required_tags`.

## Context

Sprint 1's planner contract (see `SPRINT_1.md` §3.4) says `required_tags` are hard. Today, `src/llm/tag_filter.py` / `tag_filtering_service.py` work at the LLM layer and are not authoritative for the planner. BE-3 promotes typed tag filtering into the planner core.

Unblocks: BE-4, BE-7.

## Acceptance criteria

- [ ] `src/planning/phase3_feasibility.py` (or a new `phase3_tag_filter.py` helper) computes, per slot:
  - `candidates = [r for r in recipe_pool if required_tag_slugs(slot).issubset(r.tag_slugs)]`
  - Applies existing allergen/constraint filters after.
- [ ] A slot with no candidates terminates the plan with `FM-TAG-EMPTY`, carrying `{slot_id, missing_tag, recipe_count_by_tag}` in the report for the UI (see BE-7).
- [ ] A slot whose required tag has exactly one matching recipe deterministically selects that recipe (the "forced recipe" behavior).
- [ ] The existing LLM tag filtering service (`src/llm/tag_filtering_service.py`) is either (a) deleted if no longer used, or (b) explicitly scoped to pre-planning recipe retrieval (not selection). Decision and pointer recorded in the file header.
- [ ] Tests in `tests/planning/test_tag_filter.py`:
  - Multi-tag intersection behavior.
  - `FM-TAG-EMPTY` fires for a bad config.
  - Single-recipe tag acts as a forced selection.
  - Preferred tags are **not** applied here (they live in BE-4's scorer).

## Implementation notes

- Work off `recipe.tag_slugs` (cached property: `{t.slug for t in recipe.tags}`) to keep the hot loop cheap.
- Keep slot-side as pure slugs (`required_tags: List[str]`); never pass `Tag` objects into the scorer.
- Do **not** call the LLM anywhere in this path. The planner is LLM-free (R3).

## Out of scope

- Scoring (BE-4).
- Preferred tags (BE-4).
- Error surfacing shape (BE-7 finalizes the JSON payload).
