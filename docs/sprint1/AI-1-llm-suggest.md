# AI-1 — LLM.suggest_recipes(query, k)

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** —

## Summary

New LLM pipeline stage that returns a shortlist of 3–5 recipe candidates for a user query, as structured JSON, **without** generating the full recipe.

## Context

F4 / G4: the notes explicitly asked that the user see a lightweight preview ("simple text list or an image") before paying for full generation. This is Stage A of the two-stage flow.

Unblocks: AI-2, FE-6.

## Acceptance criteria

- [ ] New module `src/llm/suggester.py` exposing `suggest_recipes(query: str, k: int = 5, seed: Optional[int] = None) -> List[RecipeSuggestion]`.
- [ ] `RecipeSuggestion` Pydantic model in `src/llm/schemas.py`:
  ```python
  class RecipeSuggestion(BaseModel):
      suggestion_id: str        # uuid
      name: str
      one_liner: str            # <= 140 chars
      est_macros: EstMacros     # calories, protein_g, fat_g, carbs_g — all floats
      reason_match: str         # why it matches the query
      hero_ingredients: List[str]   # 2–5 items, plain strings
  ```
- [ ] Endpoint `POST /api/v1/llm/suggest` with body `{query, k, seed?}` returns `{suggestions: [...]}`.
- [ ] `suggestion_id` is a ULID/UUID; suggestions are cached by `hash((query, seed, model))` in `FeedbackCache` (reuse `src/llm/feedback_cache.py`).
- [ ] End-to-end test: `"high-protein shrimp under 20 min"` returns 3–5 schema-valid suggestions within 10 s (mocked LLM for CI, real LLM for a local smoke script).
- [ ] Malformed LLM output → single retry with `response_format=json_object`; second failure raises `LLMSchemaError`.

## Implementation notes

- Use the existing LLM client in `src/llm/client.py`; do not introduce a second SDK path.
- Prompt template lives next to the module as `src/llm/prompts/suggest.md` (or a constant), referencing `SPRINT_1.md` §4.1 semantics. Constrain the model to NOT emit ingredients, nutrition, or instructions at this stage.
- `est_macros` are best-effort (for preview only); they are labeled as such in the UI and are NOT persisted with the recipe.
- `temperature = 0.2`, `seed` passed through if the backend supports it; otherwise cache by `(query, model)`.

## Out of scope

- Full generation (AI-2).
- Thumbnail/image generation (may carry a URL if the model provides one, but we don't synthesize).
- Refinement / chat loop.
