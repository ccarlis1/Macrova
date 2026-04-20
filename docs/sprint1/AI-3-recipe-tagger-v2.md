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
