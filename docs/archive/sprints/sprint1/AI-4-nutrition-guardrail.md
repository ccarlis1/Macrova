# AI-4 — Nutrition hallucination guardrail

**Status:** parked  ·  **Complexity:** S  ·  **Depends on:** AI-2

Sprint 2 close-out (DOC-1, 2026-11-14): Parked: LLM features are optional and not on the demo path. Before reviving, check whether the plausibility gates in `src/llm/recipe_validator.py` already cover it.

## Summary

Structurally prevent LLM-generated nutrition values from ever reaching storage or the planner. Nutrition is always recomputed from USDA-resolved ingredients.

## Context

G4 is a hard success metric. The cheapest and most reliable enforcement is schema-level: the LLM output model simply has no nutrition fields. Plus a defense-in-depth check in `RecipeValidator`.

## Acceptance criteria

- [ ] `GenerateRecipeOutput` Pydantic model in `src/llm/schemas.py` has no `calories`, no `protein_g`, no `fat_g`, no `carbs_g`, no `nutrition` block.
- [ ] Prompt templates for `generate` explicitly forbid nutrition fields.
- [ ] `RecipeValidator` gains `reject_llm_nutrition(raw_json)` that 422s if any of those keys appear at the top level or under `nutrition`.
- [ ] Final `Recipe.nutrition` (or `NutritionProfile`) is populated exclusively by `src/nutrition/aggregator.py` post-ingredient-resolution.
- [ ] Any nutrition tags that depend on nutrient thresholds (for example `high-omega-3`, `high-fiber`, `high-calcium`) are validated from computed nutrition only; LLM-declared nutrient claims cannot directly set these tags.
- [ ] Regression test (`tests/llm/test_nutrition_guardrail.py`):
  - Feed the validator a crafted payload with a `nutrition` block → 422 with code `LLM_NUTRITION_FORBIDDEN`.
  - Feed a clean payload → passes; resulting `Recipe` has nutrition computed from ingredients, not echoed from LLM.
  - Feed a payload that implies micronutrient-rich wording without computed support → tag is not persisted until computed nutrition confirms threshold.

## Implementation notes

- Keep the guardrail pre-ingredient-resolution so we fail fast (don't pay for USDA lookups on rejected drafts).
- Error code `LLM_NUTRITION_FORBIDDEN` lives in `src/api/error_mapping.py`.

## Out of scope

- Cross-checking: if USDA-computed macros differ wildly from `est_macros` returned in AI-1, should we warn? (Yes, but that's a separate polish item — log-only for now.)

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/llm/schemas.py` — `GenerateRecipeOutput` model (or equivalent LLM output model used in `pipeline.py`); remove nutrition fields here — do not leave them as Optional
- `src/llm/pipeline.py` — `RecipeValidator` class or function; add `reject_llm_nutrition(raw_json)` check here
- `src/api/error_mapping.py` — add error code `LLM_NUTRITION_FORBIDDEN` here; do not define it inline
- `src/nutrition/aggregator.py` — confirm its interface; `Recipe.nutrition` is populated only from here after ingredient resolution

**Entities to reuse:**
- `RecipeValidator` in `src/llm/pipeline.py` — extend with the new check; do not create a parallel validator
- `src/nutrition/aggregator.py` — sole source of nutrition values; the guardrail enforces this contract

**Do NOT create:**
- Optional nutrition fields in `GenerateRecipeOutput` — they must be absent entirely (not `Optional[None]`)
- A parallel validator module

**Guard ordering:** The `reject_llm_nutrition` check runs **before** ingredient resolution (fail fast; do not pay for USDA lookups on rejected drafts).

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/llm/schemas.py`.** Find the model used for LLM `generate` output. List every field; confirm which ones are nutrition-related (`calories`, `protein_g`, `fat_g`, `carbs_g`, any `nutrition` block).
2. **Read `src/llm/pipeline.py`.** Find `RecipeValidator` and its existing checks. Identify where in the pipeline the guardrail check should be inserted relative to ingredient resolution.
3. **Read `src/api/error_mapping.py`.** Confirm `LLM_NUTRITION_FORBIDDEN` does not already exist.
4. **Read `src/nutrition/aggregator.py`.** Confirm its input/output interface — this is the only trusted nutrition source post-guardrail.
5. State the exact fields being removed from `GenerateRecipeOutput`, the check logic for `reject_llm_nutrition`, and the pipeline insertion point before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [ ] `GenerateRecipeOutput` in `src/llm/schemas.py` has **no** `calories`, `protein_g`, `fat_g`, `carbs_g`, or `nutrition` fields — not even Optional
- [ ] Prompt templates for `generate` explicitly state no nutrition fields are to be emitted
- [ ] `reject_llm_nutrition(raw_json)` returns 422 with `LLM_NUTRITION_FORBIDDEN` when `nutrition`, `calories`, `protein_g`, `fat_g`, or `carbs_g` appear at any level in the raw payload
- [ ] The check runs **before** ingredient resolution (`IngredientMatcher`) — confirmed by test ordering
- [ ] `Recipe.nutrition` in the final persisted record comes from `src/nutrition/aggregator.py` — verifiable by tracing the pipeline in tests
- [ ] `LLM_NUTRITION_FORBIDDEN` is in `src/api/error_mapping.py`
- [ ] All three regression test cases pass: dirty payload → 422; clean payload → nutrition from aggregator; micronutrient-wording payload without computed support → tag not persisted
