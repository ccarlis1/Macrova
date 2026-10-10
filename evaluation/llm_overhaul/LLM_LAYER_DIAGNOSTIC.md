# LLM_LAYER_DIAGNOSTIC.md — What the recovery loop actually does

**Phase 2 content.** Later phases append evaluation results and the overhaul verdict. No code changed. Companion documents: `CURRENT_ARCHITECTURE.md` (boundary map), `FAILURE_TAXONOMY.md` (threat model).

## 1. The loop as executed

Source: `src/planning/orchestrator.py::plan_with_llm_feedback`, `src/llm/planner_assistant.py`, `src/llm/recipe_generator.py`, `src/llm/recipe_validator.py`, `src/llm/repository.py`, `src/llm/feedback_cache.py`. Line references are to the current tree.

```
result ← plan_meals(profile, pool, days)                                  # deterministic
if result.success → return result
if result.failure_mode ∉ {FM-1, FM-2, FM-4, FM-5} → return result          # FM-3, FM-TAG-EMPTY, FM-BATCH-CONFLICT
client ← injected or LLMClient(load_llm_settings()); provider ← injected or APIIngredientProvider(USDA cache)
assert provider.usda_capable
count ← min(3, len(schedule[0]))
history ← []; seen_fps ← ∅; prev_sig ← sha256(failure_mode, termination_code, report)
cache ← load(LLM_FEEDBACK_CACHE_PATH) unless assisted_live
for attempt in 1..3:
    ctx ← build_feedback_context(result, profile)        # deficits, macro_violations, days, meals, busyness, workouts
    key ← sha256(schema_ver, sig(result), ctx, count, model)
    drafts ← cache[key]  or  (raise DETERMINISTIC_CACHE_MISS if strict)  or  LLM(ctx, count) → cache[key] ← drafts
    drafts ← [d for d in drafts if fingerprint(d) ∉ seen_fps]   (dedupe within attempt too)
    accepted, rejected ← validate_recipe_drafts(drafts, provider)   # may raise → LLMFeedbackOrchestratorError
    seen_fps ∪= fingerprints(accepted)
    persisted_ids ← append_validated_recipes(recipes.json, accepted)  # disk write
    history.append({attempt, status: "duplicate_only"|"fail", accepted, persisted_ids})
    if persisted_ids: pool ← pool + convert(new recipes)  (fallback: rebuild whole pool from disk without tags)
    result ← plan_meals(profile, pool, days)
    if result.success → attach history to result.stats; return
    if result.failure_mode ∉ eligible → attach; return
    if sig(result) == prev_sig and not persisted_ids → history[-1].status = "abort"; attach; return
    prev_sig ← sig(result)
attach history; return result
```

What is **not** in the loop: any use of the rejected list beyond counting; any test that the accepted recipes address the failure; any tag assignment for new recipes; any rollback; any structured stop reason other than the last planner result.

## 2. The sixteen questions

**Q1. What exactly constitutes planner failure?**
`MealPlanResult.success == False`. Termination codes: TC-2 (search exhausted, or pre-checks: structural micronutrient FM-4, FC-4 dead end, FM-TAG-EMPTY, FM-1, FM-2), TC-3 (attempt cap FM-5; pin/batch pre-validation FM-3/FM-BATCH-CONFLICT). `failure_mode` is the only field the orchestrator reads. The report may carry `failures[]` with a different code than `failure_mode` (the FM-2 path emits an `FM-MACRO-INFEASIBLE` failure object under `failure_mode="FM-2"`). "Success with warnings" (`termination_code="OK"`-style soft deficits, sodium advisory) is not failure and never triggers the loop.

**Q2. Are failure codes specific enough to determine recovery?**
No. Evidence:
- Probe P1: a pool of three recipes that cannot hit the macro window is reported as **FM-1** ("Empty candidate set or FC-5") with `eligible_recipe_count=0` and no `failed_days`; benchmark C2a found 0 of 17 macro-infeasible scenarios reported as FM-2.
- Probe P2: a profile with negative derived carbs (infeasible by construction) is reported FM-1 and is recovery-eligible.
- Probe P10: benchmark scenarios whose oracle cause is a pin (MB-098, MB-147, MB-148) or a required tag on a later slot (MB-107, MB-114) come back with eligible codes; MB-068 and MB-071 are oracle-feasible but return FM-5 (search-order defect C4) and would trigger generation.
- FM-1 conflates: pool too small; HC-1 removed everything; HC-3 cook-time; HC-8 cross-day repetition; FC-1/FC-2 macro pruning; FC-5 look-ahead; tag-empties not at the first slot. FM-4 conflates structural pre-check (no combination could reach τ·RDI·D), FC-4 dead end, final weekly check, and an empty pool with micronutrient targets set (tribunal B4). FM-5 conflates "feasible but search order failed" with "infeasible but not proven".
The report payloads are sometimes richer than the code (`deficient_nutrients[].classification ∈ {marginal, structural}`, `unfillable_slots[].blocking_constraints`), but `blocking_constraints` is the constant string "Empty candidate set or FC-5" and `classification` uses a one-day bound that does not distinguish "pool lacks the nutrient" from "pool has it but combinations fail".

**Q3. Which failures should trigger recipe discovery?**
Only those where the binding constraint is a *property of the pool* and a recipe with a stated, checkable property would change the outcome:
- A slot whose candidate set is empty after HC-1/HC-3/HC-9/HC-8 filtering, when the constraint is satisfiable in principle (a recipe without the excluded ingredient, under the cook-time cap, carrying an approved tag, distinct from yesterday's). The discovery request must name the property.
- A micronutrient floor where the target is reachable from food and the pool's per-slot maximum for that nutrient is the binding term.
- A daily macro window where the target vector is physically reachable (positive carbs, protein·4 ≤ kcal, fat range consistent) and the pool's subset-sums miss it; the request must name the macro vector a new recipe should have.
- FM-5 only after the search has been shown to fail for pool reasons rather than order (today it cannot be shown; the benchmark says the opposite for MB-068/071).
In every case discovery should be preceded by a deterministic gap analysis that outputs a **target specification** for the new recipe, and followed by a check that the accepted recipe meets that specification *before* it enters the pool.

**Q4. Which failures should NEVER trigger recipe discovery?**
FM-3 and FM-BATCH-CONFLICT (already excluded). FM-TAG-EMPTY (excluded, but only when detected at the first slot; otherwise it arrives as FM-1). Infeasible-by-construction targets: negative derived carbs, calorie ceiling below the tolerance window, protein calories exceeding total, fat range inconsistent with the remaining budget, UL below RDI for a tracked nutrient. An empty pool caused by the tag filter (B3) — the fix is the filter or the tags, not new recipes. Schedule/slot-count problems and invalid requests. FM-5 on instances that a bounded exhaustive check proves feasible. Any failure when the LLM or USDA is unavailable — the deterministic result must be returned, not an HTTP error (probe P4).

**Q5. What information is passed to the LLM?**
`failure_type` (the code); `nutrient_deficits[{nutrient, achieved, required, deficit, classification}]` (FM-4 reports only); `macro_violations[{day, violations[{macro, direction, amount}]}]` (only the FM-2 daily-validation path; empty for exhaustion and for FM-1/FM-4/FM-5); `days`; `meals_per_day` (day 0 only); `busyness_by_day`; `workout_gaps_by_day`; `count`. Plus the fixed system prompt describing the `RecipeDraft` contract and unit tokens.

**Q6. What information is withheld?**
Excluded ingredients and allergies; liked foods; calorie, protein, fat and carb targets; calorie ceiling; τ; the existing pool (names, ingredients, nutrition); which slot or day failed and why (for FM-1); required/preferred tag slugs; cuisine/budget; pins and batch locks; the rejected drafts and rejection reasons from previous attempts; the USDA vocabulary the resolver can actually match. The model therefore cannot avoid allergens, cannot target a slot, cannot avoid re-proposing rejected content, and cannot choose names the resolver handles well.

**Q7. How are generated recipes validated?**
Per draft, in order: strict schema (envelope must be exactly `{"drafts": [...]}` with the requested count, or the whole attempt raises); `IngredientValidator` (unit in the supported set, quantity > 0 unless "to taste", descriptor-stripped canonical name); `provider.resolve_all` with **demotion** of any unresolvable name to "to taste" and retry until it succeeds or nothing measurable remains; `get_ingredient_info` non-None or demotion; `NutritionCalculator.calculate_ingredient_nutrition` must not raise (its value is discarded). Then `Recipe(cooking_time_minutes = min(120, 5·len(instructions)), default_servings=1)`. Probe P5: a draft containing `peanuts`, `oats` (→ oat oil) and `unicorn meat` is accepted with unicorn meat demoted and a 40-minute cook time. Not validated: resolved-record plausibility, allergens, macro plausibility, slot fit, duplicate-by-name, tags, servings, volume units.

**Q8. How are ingredients resolved?**
Name → `IngredientNormalizer` (lowercase, commas→spaces, strip ~45 descriptors) → cache key → `IngredientCache.read` by sanitized filename → on miss `USDAClient.search_candidates(top 8, SR Legacy + Foundation + Survey + Branded)` → `rank_candidates` (data-type priority ×1000, prefix match ×10, comma and length penalties, raw-like reward) → `get_food_details(fdc_id)` → `NutrientMapper` → `CacheEntry` written. The optional LLM tie-break is never wired. `APIIngredientProvider` exposes `{"name": key, "per_100g": {...}}`; `fdc_id` and description stop at the provider. In the planner path a resolution failure is fatal (exit 3 / 500); in the validator path it is demoted.

**Q9. How is FoodData Central used?**
Search + details endpoints only, per name, on cache miss; all data types; no portion data used (`foodPortions` ignored); mapper table with known errors (tribunal A3); cache with no version. USDA data is the only nutrition source in assisted modes (validator requires `usda_capable`); the local JSON provider is used for deterministic planning and would silently zero unknown names.

**Q10. How are tags assigned?**
Inside the loop: **never**. New recipes have no entry in `recipe_tags.json` and enter the in-memory pool with `canonical_tag_slugs=∅`, `hard_eligible_tag_slugs=None`. Outside the loop: (a) LLM tagging (`tag_recipes`) emits `cuisine` (free string), `cost_level`, `prep_time_bucket` (guessed, not from `cooking_time_minutes`), `dietary_flags`; never a registry slug; and the write replaces `tags_by_id` wholesale (probe P6). (b) Client sync (`/recipes/sync`) writes canonical `tag_slugs_by_type` resolved against the registry, merged with existing entries. (c) The registry is seeded with 8 system tags plus whatever `/tags` creates with `source="user"`. Nothing creates `source="llm"` registry entries, so the `proposed` quarantine has no producer.

**Q11. When does new data enter the planner's candidate pool?**
Twice. In-loop: immediately after `append_validated_recipes` returns ids, via `_append_new_recipes_to_pool` (before the retry). Permanently: every subsequent `RecipeDB` load — every deterministic plan, every CLI run, the API recipe list, and the formatter — sees the recipe with no marker except the `llm_` prefix.

**Q12. Is the mutation transactional?**
No. Four stores are written by different functions at different times with no coordination: `.cache/ingredients/*.json` (during validation, before acceptance, non-atomic `open('w')`); `data/recipes/recipes.json` (atomic per call, before the retry); `data/llm/feedback_cache.json` (atomic, before validation); `recipe_tags.json` (never, in-loop). A request that ends in failure or exception leaves all of them changed.

**Q13. What happens if validation fails halfway through?**
Per-draft rejection continues the batch; rejected drafts are counted but their reasons are not fed back. Within a draft, unresolvable ingredients are demoted rather than failing. If `validate_recipe_drafts` raises, the orchestrator records `status="error"` in a history that is then discarded and raises `LLMFeedbackOrchestratorError` (HTTP 500 `VALIDATION_EXCEPTION`); recipes persisted in earlier attempts remain. Cache entries written during the failed validation remain.

**Q14. How many retries are possible?**
3 feedback attempts (4 planner runs) per request. Per attempt: 1 LLM generation call with up to `LLM_MAX_RETRIES` (default 3) transport retries with exponential backoff and a 1 QPS limiter; `count = min(3, meals_per_day)` drafts; up to 2 USDA HTTP calls per new ingredient name. Cache hits skip the LLM but not validation. Nothing limits total wall time.

**Q15. What causes termination?**
Success; an ineligible failure mode after a retry; identical failure signature *and* nothing persisted; three attempts exhausted; or an exception (`RecipeGenerationError`, `LLMClientError` family, `DeterministicCacheMissError`, `LLMFeedbackOrchestratorError`, `IngredientResolutionError` from the fallback rebuild). The four non-exception exits all return the last `MealPlanResult` unchanged except for `stats.llm_feedback_attempts` (dropped by the formatter) and `report.llm_feedback.max_feedback_retries`. The caller cannot distinguish "gave up: infeasible", "gave up: LLM produced nothing usable", and "gave up: limit" from the response.

**Q16. How does the system determine that recovery actually improved the situation?**
It does not. The only progress test is `persisted_ids` non-empty, combined with a signature comparison. Probe P3 shows the signature changes whenever `eligible_recipe_count` changes, which it does whenever a recipe was added, so the abort rule reduces to "stop if nothing was persisted". No distance-to-feasibility, no per-slot candidate delta, no nutrient-gap delta is computed before or after a retry. A retry that made the failure worse (fallback rebuild dropped the tags, FL-2) is indistinguishable from one that helped.

## 3. Probe log (read-only, no LLM, no network)

Script: session scratchpad `probes_p2.py`; run with `PYTHONPATH=. .venv/bin/python`. All temporary paths; `LLM_FEEDBACK_CACHE_PATH` redirected.

| Probe | What was done | Observed |
|---|---|---|
| P1 | 3-recipe pool that cannot hit a 2-slot macro window; `plan_meals` then `build_feedback_context` | `failure_mode=FM-1`, eligible; `failed_days` absent; context contains only `failure_type, days, meals_per_day, busyness_by_day` |
| P2 | Profile with `daily_carbs_g=-10` | `FM-1`, eligible |
| P3 | Same report twice; then `unfillable_slots[0].eligible_recipe_count += 1` | identical → same signature; count change → different signature; `stats.attempts` not part of the signature |
| P4 | Orchestrator with a client returning `{"drafts": []}` for `count=2` | `RecipeGenerationError LLM_WRONG_DRAFT_COUNT` escapes the orchestrator |
| P5 | Draft with `peanuts`, `oats`, `unicorn meat` (unresolvable), 8 instructions, against a USDA-capable fake | accepted; `unicorn meat` → `to taste`; `cooking_time_minutes=40` |
| P6 | `tags_by_id={"user_recipe": …tag_slugs_by_type…}` then `upsert_recipe_tags(path, {"llm_recipe": cuisine="martian"})` | `user_recipe` gone; `martian` stored |
| P7 | `PlannerConfigJson` with an extra `allergies` key | `LLM_SCHEMA_VALIDATION_ERROR` |
| P8 | `excluded_ingredients=["peanuts","egg"]`; pool: recipe with `peanut butter`, recipe with `eggs` | success; plan = both recipes |
| P9 | `_rebuild_recipe_pool` on a one-recipe file | `canonical_tag_slugs=set()`, `hard_eligible_tag_slugs=None` |
| P10 | Cross-reference `evaluation/harness/results/results.json` with oracle labels | MB-068, MB-071 oracle-feasible but FM-5 (eligible); MB-098/147/148 (oracle FM-3) and MB-107/114 (oracle FM-TAG-EMPTY) return eligible codes |

## 4. Where the LLM can change system state

See `CURRENT_ARCHITECTURE.md` §4 (S1–S6). In one line each: recipes.json (append, no provenance, no rollback); USDA cache (written as a side effect of validating or matching LLM-authored names); recipe_tags.json (wholesale replace by LLM tagging); feedback_cache.json (git-tracked, mutated by tests); the in-loop pool (untagged additions; fallback drops tags and subset); the request's profile (targets, fat range via budget, and hard cuisine/budget filters from NL).

## 5. Phase 2 conclusion

The current loop is a **bounded generate-and-hope** cycle: it is correctly bounded and correctly refuses to run on pin/batch failures, and its persistence is atomic per file. But it has no diagnosis step (it cannot say what recipe would help), no fitness step (it cannot say whether an accepted recipe helps), no intent step (it never tells the model what to avoid), no provenance step (it cannot say afterward what it did), and its writes are side effects that outlive the request. The evaluation suite in Phase 3 must be able to distinguish, for every failure class in `FAILURE_TAXONOMY.md`, whether a proposed design fixes the mechanism or only the symptom.
