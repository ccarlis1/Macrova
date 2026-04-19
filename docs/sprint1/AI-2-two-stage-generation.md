# AI-2 — Two-stage generation wiring

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** AI-1, AI-3, AI-4, AI-5

## Summary

Split the existing end-to-end recipe generation into Stage A (`suggest`) and Stage B (`generate`). Stage B is keyed off a `suggestion_id` returned by Stage A so the user's approved candidate is exactly what gets built.

## Context

Today `src/llm/pipeline.py` couples suggestion + generation. Decoupling lets the UI insert a human approval step and avoids wasted USDA calls on rejected candidates.

## Acceptance criteria

- [ ] Refactor `src/llm/pipeline.py` into:
  - `suggest(query, k, seed)` (delegates to AI-1).
  - `generate(suggestion_id)` — resumes from the cached suggestion and produces a `Recipe`.
- [ ] `POST /api/v1/llm/generate` with body `{suggestion_id}`:
  - Resolves suggestion via `FeedbackCache`; 404 if unknown/expired.
  - Runs: LLM drafts ingredients + instructions (no nutrition, per AI-4) → `IngredientMatcher` resolves every ingredient → `RecipeValidator` → `RecipeTagger` v2 (AI-3) → duplicate check (AI-5) → persist.
  - Returns `{recipe, warnings: [...], duplicate_of?: recipe_id}`.
- [ ] Unresolved ingredient → 422 `INGREDIENT_UNRESOLVED` with the offending name; no partial save.
- [ ] Cache TTL for suggestions: 30 minutes. Beyond that, user must re-suggest.
- [ ] E2E test: suggest → pick one → generate → recipe appears in `GET /api/v1/recipes` with computed nutrition and typed tags.
- [ ] Regression: no existing CLI or Flutter call path silently breaks. If the old single-shot endpoint was public, keep it as a thin wrapper (`suggest` → auto-pick first → `generate`) and mark it deprecated.

## Implementation notes

- All nutrition is recomputed via `src/nutrition/aggregator.py` from the resolved USDA ingredients. LLM nutrition is never trusted (AI-4).
- `generate` must be idempotent per `suggestion_id`: calling it twice returns the same recipe id (or the detected duplicate).
- Log to stderr: `{stage, suggestion_id, elapsed_ms, outcome}` for parity debugging.

## Out of scope

- Refinement / rewrite loops.
- Image generation for the recipe.
- Bulk import.
