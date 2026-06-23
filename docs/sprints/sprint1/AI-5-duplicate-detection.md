# AI-5 — Duplicate detection

**Status:** done  ·  **Complexity:** S  ·  **Depends on:** AI-2

## Summary

Before saving a generated recipe, fuzzy-match its name against the existing recipe bank and short-circuit to the duplicate if similarity ≥ 0.85.

## Context

LLM generation is non-deterministic and users will frequently query variations that collide. Avoid polluting the bank and surface the pre-existing recipe instead.

## Acceptance criteria

- [x] `src/llm/duplicate_check.py` exposing `find_duplicate(name: str, recipes: List[Recipe]) -> Optional[Recipe]`.
- [x] Similarity = `rapidfuzz.fuzz.token_sort_ratio(name_a, name_b) / 100.0`, threshold 0.85, compared after lowercasing both sides.
- [x] Called from the current pipeline equivalent (`generate_validate_persist_recipes`) right before persistence. `generate(suggestion_id)` is not present yet from AI-2.
- [x] On duplicate hit: do not save the new recipe; return the existing recipe id with `warning: "duplicate_of: <id>"`.
- [x] Tests:
  - `"Chicken Rice Bowl"` vs existing `"chicken and rice bowl"` → duplicate (`ratio >= 0.85`).
  - `"Shrimp Pasta"` vs existing `"Chicken Pasta"` → not a duplicate.

## Implementation notes

- Add `rapidfuzz` to `requirements.txt` if not present.
- Prefer `token_sort_ratio` over plain `ratio` because ingredient ordering in names is meaningless (`"Rice Bowl Chicken"` ≈ `"Chicken Rice Bowl"`).
- Keep the threshold tunable via an env var for easy adjustment without a redeploy.

## Out of scope

- Ingredient-level duplicate detection.
- Merging metadata from the duplicate into the new recipe.

---

## 🔒 IMPLEMENTATION CONTRACT

**Files to inspect before writing any code:**
- `src/llm/pipeline.py` — `generate(suggestion_id)` (AI-2 output); `find_duplicate()` is called here, right before `RecipeDB.save()` — do not call it earlier or later in the pipeline
- `src/data_layer/models.py` — `Recipe` dataclass; `find_duplicate` receives `List[Recipe]` and returns `Optional[Recipe]`
- `requirements.txt` — add `rapidfuzz` if not present; check before adding to avoid duplicate entries

**Entities to reuse:**
- `Recipe` from `src/data_layer/models.py` — input type for the recipe list parameter
- `generate()` in `src/llm/pipeline.py` — the single call site for `find_duplicate`

**Do NOT create:**
- A duplicate-detection call anywhere other than `generate()` (before persistence)
- A second similarity algorithm beyond `rapidfuzz.fuzz.token_sort_ratio`

**Threshold tuning:** Threshold must be readable from an env var (`DUPLICATE_THRESHOLD`, default `0.85`) — not hardcoded, not in a config class for Sprint 1.

---

## 🧠 PRE-IMPLEMENTATION ANALYSIS

Before writing any code, perform the following in order:

1. **Read `src/llm/pipeline.py` (AI-2 output).** Find `generate(suggestion_id)` and identify the exact line before `RecipeDB.save()` where `find_duplicate` should be inserted.
2. **Read `src/data_layer/models.py`.** Confirm the `Recipe` fields accessible for name comparison — specifically the `name` field type.
3. **Check `requirements.txt` for `rapidfuzz`** — add it only if absent.
4. **Confirm `src/llm/duplicate_check.py` does not already exist** before creating it.
5. State the full `find_duplicate` signature and the env-var name for the threshold before writing code.

---

## ✅ POST-IMPLEMENTATION VALIDATION

After implementation, verify each of the following:

- [x] `src/llm/duplicate_check.py` exposes `find_duplicate(name: str, recipes: List[Recipe]) -> Optional[Recipe]`
- [x] Similarity uses `rapidfuzz.fuzz.token_sort_ratio(a.lower(), b.lower()) / 100.0`; threshold read from `DUPLICATE_THRESHOLD` env var (default `0.85`)
- [x] Called from the current `src/llm/pipeline.py` generation path right before `append_validated_recipes()` — not before validation, not after save
- [x] On duplicate hit: new recipe is NOT saved; response includes `warning: "duplicate_of: <id>"` with the existing recipe id
- [x] `rapidfuzz` added to `requirements.txt` (no duplicates)
- [x] Tests pass: `"Chicken Rice Bowl"` vs `"chicken and rice bowl"` → duplicate; `"Shrimp Pasta"` vs `"Chicken Pasta"` → not a duplicate
