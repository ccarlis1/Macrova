# AI-5 — Duplicate detection

**Status:** todo  ·  **Complexity:** S  ·  **Depends on:** AI-2

## Summary

Before saving a generated recipe, fuzzy-match its name against the existing recipe bank and short-circuit to the duplicate if similarity ≥ 0.85.

## Context

LLM generation is non-deterministic and users will frequently query variations that collide. Avoid polluting the bank and surface the pre-existing recipe instead.

## Acceptance criteria

- [ ] `src/llm/duplicate_check.py` exposing `find_duplicate(name: str, recipes: List[Recipe]) -> Optional[Recipe]`.
- [ ] Similarity = `rapidfuzz.fuzz.token_sort_ratio(name_a, name_b) / 100.0`, threshold 0.85, compared after lowercasing both sides.
- [ ] Called from `generate(suggestion_id)` (AI-2) right before persistence.
- [ ] On duplicate hit: do not save the new recipe; return the existing recipe id with `warning: "duplicate_of: <id>"`.
- [ ] Tests:
  - `"Chicken Rice Bowl"` vs existing `"chicken and rice bowl"` → duplicate (`ratio >= 0.85`).
  - `"Shrimp Pasta"` vs existing `"Chicken Pasta"` → not a duplicate.

## Implementation notes

- Add `rapidfuzz` to `requirements.txt` if not present.
- Prefer `token_sort_ratio` over plain `ratio` because ingredient ordering in names is meaningless (`"Rice Bowl Chicken"` ≈ `"Chicken Rice Bowl"`).
- Keep the threshold tunable via an env var for easy adjustment without a redeploy.

## Out of scope

- Ingredient-level duplicate detection.
- Merging metadata from the duplicate into the new recipe.
