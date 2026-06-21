# AI-3 — RecipeTagger v2 (typed tags)

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** DM-1, BE-1

## Summary

Upgrade `src/llm/recipe_tagger.py` to emit typed tags grouped by `{context, time, nutrition, constraint}`, normalized and registered through `TagService`.

## Context

The current tagger emits free-form strings. Sprint 1 requires typed, normalized tags; otherwise the planner filter has nothing to bite on.

Unblocks: AI-2 (uses the new output), consistent corpus for BE-3.

## Acceptance criteria

- [ ] Tagger output Pydantic model:
  ```python
  class RecipeTagSet(BaseModel):
      context: List[str]       # 1–2 slugs
      time: List[str]          # exactly 1 slug
      nutrition: List[str]     # 0–4 slugs
      constraint: List[str]    # 0–3 slugs
  ```
- [ ] On generation:
  1. LLM proposes `RecipeTagSet`.
  2. Each slug is normalized and resolved via `TagService.resolve()`.
  3. Unknown slugs are created with `source="llm"` (quarantined; confirmed later via FE-5), **except nutrition slugs**, which must come from the curated nutrition registry set.
  4. `time` tag is overridden by the deterministic bucket computed from `cooking_time_minutes` (DM-5 bucket function). If the LLM's `time` tag disagrees, log a warning and prefer the computed value.
- [ ] Nutrition-tag behavior:
  - Micronutrient recovery tags such as `high-omega-3`, `high-fiber`, and `high-calcium` are allowed as optional `nutrition` tags.
  - If a nutrition tag depends on nutrient thresholds, it must be validated from USDA-computed nutrition in the post-validation pipeline before persistence.
- [ ] Tag count caps enforced server-side; over-cap output is truncated (stable by confidence order) with a warning.
- [ ] Tagger test corpus (`tests/llm/fixtures/tagger_corpus.json`, ~20 recipes):
  - ≥ 95 % get ≥ 1 `context` tag.
  - 100 % get exactly 1 `time` tag.
  - 0 invalid tag types escape to storage.

## Implementation notes

- Import the `time-*` bucket helper from DM-5; do not duplicate the logic.
- Do NOT let the tagger touch nutrition-related values (AI-4).
- Keep micronutrient tag vocabulary small and curated in DM-1; avoid open-ended nutrition tag creation by LLM output.
- Prompt template constrains the output schema; invalid JSON → one retry → hard fail.
- Keep the tagger pure given its input (recipe draft + registry snapshot); no network calls beyond the LLM itself.

## Out of scope

- UI review of quarantined tags (FE-5 settings).
- Large-scale reverse-direction tagging from nutrition numbers (beyond curated micronutrient checks in pipeline) remains future work.

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/llm/recipe_tagger.py` — primary upgrade target; the existing tagger logic lives here; upgrade in-place, do not create a parallel tagger
- `src/llm/schemas.py` — add `RecipeTagSet` Pydantic model here (alongside existing `RecipeTagsJson`); do not create a new schema file
- `src/llm/tag_repository.py` — `TagService.resolve()` (DM-1 / BE-1 output); each slug is normalized and resolved through this; unknown non-nutrition slugs → `create(source="llm")`
- `src/llm/client.py` — the only LLM client; no new SDK paths
- `src/llm/time_bucket.py` (or wherever the bucket helper landed from DM-5) — **import** the `time_bucket` function; do not duplicate the bucket logic

**Entities to reuse:**
- `TagService.resolve()` from `src/llm/tag_repository.py`
- Time-bucket function from DM-5 (confirm import path at implementation time)
- Feature `tag_generation_and_persistence` (implemented) — the tagger upgrade replaces the inner logic, not the outer persistence flow

**Do NOT create:**
- A parallel tagger module
- Duplicate bucket logic (import from DM-5's helper)
- Any nutrition resolution (that belongs to AI-4 / `src/nutrition/aggregator.py`)

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/llm/recipe_tagger.py` in full.** Map the current flow: how the tagger is called, what it returns, how results are persisted.
2. **Read `src/llm/schemas.py`.** Note all existing models; add `RecipeTagSet` without conflicting with `RecipeTagsJson`.
3. **Read `src/llm/tag_repository.py` (DM-1 / BE-1 output).** Confirm `TagService.resolve()` and `TagService.create(source=...)` interfaces.
4. **Locate the time-bucket helper from DM-5** (check `src/llm/time_bucket.py` or wherever it was placed). Confirm its importable function name and signature.
5. **Confirm `tests/llm/fixtures/tagger_corpus.json`** does not exist yet — create it as a ~20 recipe fixture.
6. State the new `tag_recipe(recipe_draft, registry_snapshot)` signature, the override logic for `time` tags, and the quota-cap truncation approach before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `src/llm/recipe_tagger.py` is upgraded in-place; no parallel tagger module created
- [ ] `RecipeTagSet` is in `src/llm/schemas.py`; `RecipeTagsJson` is unchanged
- [ ] `time` tag is always overridden by the deterministic bucket from DM-5's helper — LLM value logged and discarded if it disagrees
- [ ] Unknown non-nutrition slugs are created with `source="llm"` via `TagService.create()`; nutrition slugs not in the curated set are rejected (not stored)
- [ ] Tag count caps are enforced server-side; over-cap output is truncated (stable by confidence order) with a warning log
- [ ] Tagger has no network calls beyond the LLM client — pure given input + registry snapshot
- [ ] Corpus test: ≥ 95% of ~20 fixture recipes get ≥ 1 `context` tag; 100% get exactly 1 `time` tag; 0 invalid tag types escape to storage
