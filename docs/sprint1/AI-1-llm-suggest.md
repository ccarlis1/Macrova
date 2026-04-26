# AI-1 — LLM.suggest_recipes(query, k)

**Status:** todo  ·  **Complexity:** M  ·  **Depends on:** —

## Summary

New LLM pipeline stage that returns a shortlist of 3–5 recipe candidates for a user query, as structured JSON, **without** generating the full recipe.

## Context

F4 / G4: the notes explicitly asked that the user see a lightweight preview ("simple text list or an image") before paying for full generation. This is Stage A of the two-stage flow.
This task is on the Week 1 critical path and must ship with AI-2/FE-6 (not deferred to Week 2).

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

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/llm/client.py` — the existing LLM client; use this for all model calls; **do not instantiate a second SDK client or import the Anthropic/OpenAI SDK directly in the new module**
- `src/llm/schemas.py` — add `RecipeSuggestion` and `EstMacros` Pydantic models here; do not create a separate schema file
- `src/llm/feedback_cache.py` — `FeedbackCache` cache-by-hash interface; reuse for caching suggestions by `hash((query, seed, model))`
- `src/api/server.py` — mount the new `POST /api/v1/llm/suggest` endpoint here; check the existing LLM-related routes for naming conventions

**Entities to reuse:**
- `FeedbackCache` from `src/llm/feedback_cache.py` — same caching mechanism used for pipeline feedback
- LLM client from `src/llm/client.py` — single SDK path

**Do NOT create:**
- A second LLM SDK path or direct `anthropic`/`openai` import in `src/llm/suggester.py`
- A standalone schema file for `RecipeSuggestion` — add to `src/llm/schemas.py`

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/llm/client.py` in full.** Note the call interface — how are prompts submitted, what parameters does it accept (`temperature`, `seed`, `response_format`), what does it return.
2. **Read `src/llm/feedback_cache.py`.** Note the cache key/value interface and TTL configuration — confirm it supports caching by `hash((query, seed, model))`.
3. **Read `src/llm/schemas.py`.** Identify existing Pydantic models; add `EstMacros` and `RecipeSuggestion` without conflicting with existing names.
4. **Read `src/api/server.py`.** Find the existing LLM-related routes (e.g., `GET /api/v1/llm/status`) for naming and mounting conventions.
5. **Confirm `src/llm/suggester.py` does not already exist** before creating it.
6. State the prompt template location, the retry logic (`response_format=json_object` on second attempt), and the `LLMSchemaError` class location before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `src/llm/suggester.py` uses only `src/llm/client.py` for LLM calls — no direct SDK imports
- [ ] `RecipeSuggestion` and `EstMacros` are in `src/llm/schemas.py`; no new schema file created
- [ ] `suggestion_id` is a UUID/ULID; `est_macros` fields are all `float`; `hero_ingredients` has 2–5 items; `one_liner` ≤ 140 chars — validated by Pydantic
- [ ] Suggestions are cached in `FeedbackCache` by `hash((query, seed, model))`; a second call with the same inputs returns the cached result without a new LLM call
- [ ] Malformed LLM output triggers exactly one retry with `response_format=json_object`; second failure raises `LLMSchemaError`
- [ ] `POST /api/v1/llm/suggest` is mounted in `server.py` and returns `{suggestions: [...]}`
- [ ] End-to-end test: mocked LLM returns 3–5 schema-valid suggestions within 10 s
