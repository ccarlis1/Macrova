# AI-4 — Nutrition hallucination guardrail

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** AI-2

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
