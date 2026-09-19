# FAILURE_TAXONOMY.md — Threat model of Macrova's LLM layer

**Phase:** 1. No code changed. Builds on `CURRENT_ARCHITECTURE.md` (boundaries B1–B13, state mutations S1–S6) and on ten read-only probes (P1–P10, logged in `LLM_LAYER_DIAGNOSTIC.md` §3).

## 0. Threat model

The LLM is treated as an **untrusted, non-deterministic function** that can return any JSON. Its outputs are dangerous in proportion to how far they travel before a deterministic check that is *semantic* (does this mean what it claims?) rather than *syntactic* (is this well-formed?). Today every LLM output passes a syntactic gate (`parse_llm_json`, strict Pydantic) and almost none pass a semantic one.

Trust boundaries, from most to least protected:

| Asset | Can the LLM reach it? | Through |
|---|---|---|
| Planner search, hard-constraint predicates, precedence rules | No | — |
| Pins, batch locks, tag registry, reference tables (ULs, carb sources) | No | — |
| Planner **constraints** (targets, fat range, exclusions, filters) | Yes, per request | B1/B2 (targets and fat range from NL + budget), B3 (cuisine/budget become hard pool filters) |
| Planner **candidate pool** | Yes, permanently | S1 (recipes.json), S5 (in-loop pool) |
| **Nutrition numbers** the planner sees | Yes, permanently | S2 (cache entries written for LLM-authored names via a lossy resolver) |
| **Per-recipe tags** used for hard filtering | Yes, destructively | S3 (wholesale replace of `tags_by_id`; free-string cuisine) |
| What the user is told | Yes | fabricated cook times, silently demoted ingredients, defaults presented as user intent, loop history dropped (B13) |

Severity scale used below: **S0** safety (user could eat an excluded ingredient); **S1** correctness (the planner or user is given a false fact and acts on it); **S2** integrity (persistent contamination of shared state); **S3** quality (worse but not wrong); **S4** observability (the failure cannot be seen or attributed).

Evidence codes: **[obs]** observed in local data; **[probe Pn]** reproduced by probe; **[audit X]** established by a prior report; **[code]** direct from source, not yet exercised; **[theory]** plausible, not reproduced.

## 1. Intent failures (natural language → structured request)

| ID | Failure | Mechanism today | Severity | Evidence | Current defense |
|---|---|---|---|---|---|
| IN-1 | Omitted constraint: the user states a constraint the schema cannot hold (allergy, dislike, exclusion, fat range, calorie ceiling, micronutrient goal, τ, required tag, liked food) | `PlannerConfigJson` has no field; `user_profile_from_planner_config` hard-codes `allergies=[]`, `disliked_foods=[]`, `daily_micronutrient_targets=None`, `max_daily_calories=None` | **S0** (allergy) / S1 | [probe P7] extra key `allergies` → `LLM_SCHEMA_VALIDATION_ERROR`; [audit D5] | none; a well-behaved model that *tries* to encode the allergy is rejected, a model that drops it passes |
| IN-2 | Invented constraint: values the user never stated appear as targets | system prompt: "choose sensible defaults: days=1 … 2000 calories, 120g protein"; output carries no provenance | S1 | [code] `constraint_parser.py` | none; defaults indistinguishable from user values |
| IN-3 | Hard/soft misclassification | `cuisine` → `liked_foods` (soft) **and** in assisted mode → tag-filter `cuisine` (hard, B3); `budget` → hard fat-ratio bounds (B2) | S1 | [code] `server.py` plan-from-text, `user_profile.py::_default_fat_ratio_bounds` | none; the schema has no hard/soft marker |
| IN-4 | Ambiguity resolved silently ("light dinner", "low carb", "around 2000") | temperature 0 + schema; no confidence, no clarification channel, no echo of interpretation | S3 | [code] | none |
| IN-5 | Schedule misinterpretation: wrong `days`, wrong `meals_per_day`, workouts placed in wrong gap, `schedule_days` template replicated when days differ | `_expand_schedule_days` replicates or slices; `meals_per_day` ignored when `schedule_days` present | S1 | [code] `converters._expand_schedule_days`; [theory] for LLM side | `validate_day_schedule` catches only structural invalidity |
| IN-6 | Meal-slot mapping: every slot `busyness_level=4` when no `schedule_days`; meal types by position | `_schedule_dict_from_meals_per_day` | S3 | [code] | none |
| IN-7 | Nutritional target misinterpretation: protein in wrong unit, calories vs kcal, fat/carb ratios; **fat range derived from budget** | `PlannerTargets` only calories+protein; fat from budget | S1 | [code] | negative-carb rejection only |
| IN-8 | Tag interpretation: user names a tag ("vegan", "quick") → becomes `cuisine` string or is dropped; no path to `required_tag_slugs` unless the model emits `schedule_days` with slugs, which must already exist in the registry | `MealSlot._validate_tag_slugs` rejects unknown slugs; nothing maps NL to slugs | S1 | [code] | unknown slug → 422 |
| IN-9 | Invalid configuration accepted: `days` mismatched to `schedule_days` length; contradictory targets that pass the negative-carb check | schema range checks only | S1 | [theory] | partial |

## 2. Recipe-generation failures

| ID | Failure | Mechanism today | Severity | Evidence | Current defense |
|---|---|---|---|---|---|
| RG-1 | Invented ingredient that nevertheless *resolves* to some USDA record | `validate_recipe_draft` accepts any name the resolver maps to any record; resolver picks "Oil, oat" for `oats`, "TACO BELL, Nachos" for `bell pepper` | **S1** | [obs] cache; [audit A2, D1] | none semantic |
| RG-2 | Invented ingredient that does not resolve → silently demoted to "to taste" and recipe persisted | `validate_recipe_draft` resolution loop | S1 | [probe P5] `unicorn meat` → to taste, recipe accepted; [obs] 2 persisted recipes; [audit D2] | rejects only when *nothing* measurable remains |
| RG-3 | Invented nutrition | `RecipeDraft` has no nutrition fields; nutrition recomputed | — (defended) | [code] | schema forbids |
| RG-4 | Impossible/implausible recipe (1 kg salt, 100 g oil as base, zero-calorie meal) | no macro/mass plausibility check; ml treated as g | S1 | [obs] "Oatmeal with Fruits" persisted at 1474 kcal/107 g fat (audit D1) | none |
| RG-5 | Duplicate recipe under quantity/unit variation | fingerprint uses exact quantities and units; `2 tbsp` ≠ `29.58 ml` | S2/S3 | [obs] 14 fingerprints for 3 dishes | exact-match only |
| RG-6 | Recipe incompatible with constraints (contains excluded ingredient, exceeds slot cook time, wrong tag) | LLM never told exclusions (B6); cook time fabricated; no tags written | **S0** (allergen in pool; caught by HC-1 only on exact name) | [probe P5] `peanuts` accepted; [code] B6 | HC-1 exact-match at plan time |
| RG-7 | Recipe that looks valid but rests on unsupported assumptions (fabricated `cooking_time_minutes = 5×steps`, `default_servings=1`) | validator | S1 (drives HC-3) | [obs] all LLM recipes 20/25 min; [probe P5] 8 steps → 40 min | none |
| RG-8 | Repeatedly the same failed candidates | feedback cache replays identical drafts for identical signature; cross-attempt dedupe only within one call; nothing remembers *rejected* drafts across calls | S3 | [obs] cache holds 24 near-identical "Quinoa Salad" drafts | within-call fingerprint set |
| RG-9 | Generation for the wrong problem (context empty or wrong code) | FM-1/FM-2 exhaustion contexts carry no deficits (B6) | S3 | [probe P1] context = `{failure_type, days, meals_per_day, busyness}` only | none |
| RG-10 | Generation attempted when no recipe can help | eligibility by code only | S3 → S2 (contaminating writes for nothing) | [probe P2] negative-carb profile → FM-1 eligible; [probe P10] 5 oracle pin/tag failures eligible; MB-068/071 feasible-but-FM-5 eligible | none |
| RG-11 | LLM/transport error turns a planner failure into an HTTP error | exceptions not caught in orchestrator | S4 | [probe P4] `LLM_WRONG_DRAFT_COUNT` propagates | none |

## 3. FoodData Central failures

| ID | Failure | Mechanism today | Severity | Evidence | Current defense |
|---|---|---|---|---|---|
| FDC-1 | Wrong search match / wrong candidate among several | `ingredient_ranker` string heuristics over top-8 across all data types | S1 | [obs] 12 wrong resolutions in cache (audit A2) | compound-keyword filter only |
| FDC-2 | Branded vs generic confusion | Branded is lowest priority but still eligible; `milk`, `quinoa` resolved Branded | S1 | [obs] | data-type priority |
| FDC-3 | Serving/unit conversion error | `NutritionCalculator` treats ml, cup, tbsp as grams; `NutritionScaler` (strict) unused on planning path | S1 | [audit A5] | none on planning path |
| FDC-4 | Nutrient-field mapping error | vitamin D IDs swapped; Foundation energy (2047/2048) unmapped; omega-3 = DHA only | S1 | [audit A3] | none |
| FDC-5 | Missing nutrient values read as zero | mapper defaults to 0.0; provider cannot express "unknown" | S1 | [code] `nutrient_mapper.py` | none |
| FDC-6 | Duplicate ingredients under name variants (`banana`/`bananas`, `chicken breast`/`chicken breast boneless`) | cache keyed by sanitized canonical name after descriptor stripping; no alias table | S2 | [obs] `banana.json` and `bananas.json` both exist | descriptor stripping only |
| FDC-7 | Stale/incomplete cache; entries from superseded mapper versions | no version/timestamp in `CacheEntry`; "no silent invalidation" by design | S2 | [audit A4] | none |
| FDC-8 | LLM-generated data treated as USDA-equivalent | validator accepts a recipe if names resolve; provider dict drops `fdc_id`/description; no provenance past the provider | S1/S2 | [code] `api_provider._entry_to_dict` | none |
| FDC-9 | LLM-driven cache pollution | validator and matcher call `resolve_all` on LLM-authored names, writing cache files even for rejected drafts | S2 | [code] B9 | none |
| FDC-10 | Silent zero for unresolved ingredient in local mode | `calculate_recipe_nutrition` `continue`s on `IngredientNotFoundError` | S1 | [audit A1] | none; a test asserts it |

## 4. Tagging failures

| ID | Failure | Mechanism today | Severity | Evidence | Current defense |
|---|---|---|---|---|---|
| TG-1 | Invented tag slug | LLM tagger cannot emit slugs (only 4 legacy fields), so **no** slug invention today; but `cuisine` is a free string used as a hard filter key | S1 | [probe P6] `cuisine="martian"` accepted | enum for cost/prep/diet only |
| TG-2 | Incorrect tag (LLM guesses `prep_time_bucket` although `cooking_time_minutes` is known; guesses dietary flags from names) | tagger prompt gives ingredients + instructions + cook time, no rules | S1 (dietary flag drives hard filter) | [code] | none |
| TG-3 | Missing required tag → recipe invisible to a required-tag slot | generated recipes never tagged; CLI attaches no tags at all | S1 | [code] B10, B4 | none |
| TG-4 | Over-tagging / contradictory tags (vegan + contains chicken) | no cross-check against ingredients | S1 | [theory] | none |
| TG-5 | Duplicate tags / alias drift | registry normalizes and dedupes | — (defended) | [code] `tag_repository` | alias map, merge |
| TG-6 | Inconsistent tagging across equivalent recipes | one independent LLM call per recipe | S3 | [theory] | none |
| TG-7 | Tags derived from LLM assumptions treated as user/system tags | LLM tagger writes `RecipeTagsJson` with no `source`; per-recipe `tag_metadata` never set; the `proposed` quarantine applies only to registry entries with `source="llm"`, which nothing creates | S1 | [code] B-tagging | lifecycle exists but has no producer |
| TG-8 | **Destructive write**: tagging run replaces `tags_by_id`, deleting curated slugs and untagged recipes | `upsert_recipe_tags` | **S2** | [probe P6] | none |
| TG-9 | Tag/planner compatibility: `dietary_flags`/`cuisine` (filter layer) and `tag_slugs_by_type` (HC-9 layer) are two uncoordinated encodings; HC-1 names are a third | design | S1 | [audit Q10] | none |

## 5. Feedback-loop failures

| ID | Failure | Mechanism today | Severity | Evidence | Current defense |
|---|---|---|---|---|---|
| FL-1 | Retry without state change | abort only if signature identical **and** nothing persisted; cache replays same drafts | S3 | [code] B12 | signature check |
| FL-2 | Retry that changes the problem rather than solving it | fallback `_rebuild_recipe_pool` drops `recipe_ids` subset, tag filter, tags, `hard_eligible` attributes | S1 | [probe P9] rebuilt recipe has no tags | none; stderr line only |
| FL-3 | Unbounded retries | bounded: 3 feedback attempts, LLM HTTP retries ≤ `LLM_MAX_RETRIES`; USDA lookups per new name unbounded by policy but finite | — (defended) | [code] | `max_feedback_retries` |
| FL-4 | Pool contamination by every attempt | persist-before-retry; no rollback on failure of the overall request | S2 | [obs] 14 residue recipes | none |
| FL-5 | Low-quality candidates added | acceptance = resolves + computes; no fitness test against the failure that triggered generation | S2 | [obs] | none |
| FL-6 | Repeated similar candidates | RG-5 + RG-8 | S3 | [obs] | exact fingerprint |
| FL-7 | Inventory shortage mistaken for optimization failure, and vice versa | FM-1 for macro-infeasible days (C2a); FM-5 for feasible instances (C4) | S1 | [probe P1], [probe P10] | none |
| FL-8 | Recovery feasible but violates intent (recipe with allergen "fixes" a slot only because HC-1 is exact-match; cuisine ignored; cook time fabricated under the slot cap) | B6 withholds intent; HC-1 exact | **S0** | [probe P8] `peanuts` excluded, `peanut butter` planned | HC-1 exact-match |
| FL-9 | No success criterion | "progress" = something persisted | S4 | [probe P3] signature changes whenever `eligible_recipe_count` changes, so the abort rule reduces to "nothing persisted" | none |
| FL-10 | Data-source or model outage handled as system error | exceptions escape | S4 | [probe P4] | none |
| FL-11 | Deterministic-strict mode unusable in practice | cache key includes the full report → any pool or profile change is a miss → HTTP 500 | S4 | [code] B8 | — |

## 6. State failures

| ID | Failure | Mechanism today | Severity | Evidence | Current defense |
|---|---|---|---|---|---|
| ST-1 | Mutation that cannot be rolled back | S1 recipes, S2 cache, S3 tags have no undo, no backup (except `merge`) | S2 | [code] | atomic writes only |
| ST-2 | Generated data persisting when it should not (rejected drafts' cache entries; recipes from a request that ultimately failed; test fixtures in the committed feedback cache) | B9 side effect; persist-before-retry; tests not redirecting cache path | S2 | [obs] 6 fixture drafts in `data/llm/feedback_cache.json` | none |
| ST-3 | Failed candidates entering the permanent pool | accepted ≠ useful; recipes persisted even when the retry still fails | S2 | [obs] | none |
| ST-4 | Inconsistent cache/db state: recipe references a name whose cache entry is later deleted/changed; tags file and recipes file updated in separate non-transactional writes; feedback cache keyed on a report shape that changes with code | design | S2 | [code] | none |
| ST-5 | Duplicate recipes/ingredients | RG-5, FDC-6 | S2 | [obs] | partial |
| ST-6 | Non-idempotent operations: `/recipes/tags/generate` twice with different LLM answers overwrites; `plan` in assisted mode mutates the store, so two identical requests differ | design | S2 | [code] | — |
| ST-7 | No provenance on any persisted artifact (recipe, tag, cache entry) | data shapes | S4 (blocks every audit) | [code] | `llm_` id prefix only |

## 7. Cross-cutting summary

| Class | Count | S0 | S1 | S2 | S3 | S4 | Defended today |
|---|---|---|---|---|---|---|---|
| Intent | 9 | 1 | 6 | 0 | 2 | 0 | 0 |
| Recipe generation | 11 | 2 | 5 | 2 | 3 | 1 | 1 (RG-3) |
| FoodData Central | 10 | 0 | 7 | 4 | 0 | 0 | 0 |
| Tagging | 9 | 0 | 6 | 1 | 1 | 0 | 1 (TG-5) |
| Feedback loop | 11 | 1 | 3 | 2 | 3 | 3 | 1 (FL-3) |
| State | 7 | 0 | 0 | 6 | 0 | 1 | 0 |

(Some rows carry two severities; the primary is counted.)

The three root causes that generate most rows:

1. **Syntactic validation only.** Every gate answers "is it well-formed?"; none answers "is it true / safe / useful?" (IN-1..3, RG-1..7, TG-1..4, FL-5).
2. **No provenance and no ownership of mutations.** Generated, derived, and authoritative data share files and shapes with no marker; writes are side effects of reads and validation (FDC-8/9, TG-7/8, ST-1..7).
3. **Failure codes are not diagnoses.** Recovery is keyed on a code that names the last event, so the loop cannot know whether recipes can help or what property they need (RG-9/10, FL-7/9).

These three drive the evaluation design in Phase 3.
