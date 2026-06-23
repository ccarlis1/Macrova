# AI-2 — Two-stage generation wiring

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** AI-1, AI-3, AI-4, AI-5

## Summary

Split the existing end-to-end recipe generation into Stage A (`suggest`) and Stage B (`generate`). Stage B is keyed off a `suggestion_id` returned by Stage A so the user's approved candidate is exactly what gets built.

## Context

Today `src/llm/pipeline.py` couples suggestion + generation. Decoupling lets the UI insert a human approval step and avoids wasted USDA calls on rejected candidates.
This task is on the Week 1 critical path and is blocked only by AI-1.

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

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/llm/pipeline.py` — the primary refactor target; `validated_recipe_generation_via_llm` feature is implemented here; split into `suggest()` and `generate()` in-place; do not create a parallel pipeline module
- `src/llm/feedback_cache.py` — `FeedbackCache` for suggestion TTL (30 min); `generate()` resolves suggestions from here; 404 on miss/expired
- `src/llm/ingredient_matcher.py` — `IngredientMatcher`; called from `generate()` to resolve every ingredient; unresolved → 422 `INGREDIENT_UNRESOLVED`
- `src/nutrition/aggregator.py` — called post-ingredient-resolution; all nutrition computed here; LLM nutrition never trusted (see AI-4)
- `src/api/server.py` — mount `POST /api/v1/llm/generate`; confirm the existing `POST /api/v1/recipes/generate-validated` endpoint and its deprecation plan
- `src/llm/schemas.py` — `GenerateRecipeOutput` must have no nutrition fields (AI-4)

**Entities to reuse:**
- `IngredientMatcher` from `src/llm/ingredient_matcher.py`
- `FeedbackCache` from `src/llm/feedback_cache.py`
- `src/nutrition/aggregator.py` — sole source of nutrition values

**Do NOT create:**
- A parallel pipeline module
- Any nutrition fields on the LLM output model (AI-4 governs this)

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/llm/pipeline.py` in full.** Map the current single-shot flow: where suggestion happens, where generation happens, where validation occurs, where ingredients are resolved.
2. **Read `src/llm/feedback_cache.py`.** Confirm TTL configuration mechanism and the `get`/`set` interface.
3. **Read `src/llm/ingredient_matcher.py`.** Confirm the interface for resolving a single ingredient and what it returns on failure.
4. **Read `src/nutrition/aggregator.py`.** Confirm the interface for computing nutrition from resolved ingredients.
5. **Read `src/api/server.py`.** Find `POST /api/v1/recipes/generate-validated` — this is the endpoint to keep as a deprecated thin wrapper around `suggest` → auto-pick first → `generate`.
6. State the exact refactored `suggest()` and `generate()` signatures and the `generate` idempotency mechanism before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `src/llm/pipeline.py` is refactored into `suggest()` and `generate()` — no new parallel pipeline module
- [ ] `POST /api/v1/llm/generate` resolves suggestion from `FeedbackCache`; returns 404 if unknown or expired (> 30 min)
- [ ] `generate()` is idempotent per `suggestion_id`: calling twice returns the same recipe id
- [ ] Unresolved ingredient → 422 `INGREDIENT_UNRESOLVED` with the offending name; no partial save
- [ ] Final `Recipe.nutrition` comes exclusively from `src/nutrition/aggregator.py` — no LLM nutrition values stored
- [ ] `POST /api/v1/recipes/generate-validated` still works as a deprecated thin wrapper
- [ ] E2E test: suggest → pick → generate → recipe appears in `GET /api/v1/recipes` with computed nutrition and typed tags
- [ ] Stderr log emitted per stage: `{stage, suggestion_id, elapsed_ms, outcome}`
