# CURRENT_ARCHITECTURE.md — Macrova LLM layer, as it actually executes

**Phase:** 0 (baseline and system map). No code was changed.
**Date:** 2026-09-18. **Branch:** `llm-overhaul` at `779af36`. Working tree clean before this file.
**Method:** read every module under `src/llm/`, `src/planning/orchestrator.py`, `src/api/server.py`, `src/cli.py`, the ingestion/provider layer, the tag repository, the tests that cover them, and the four prior audit reports under `evaluation/`. Every claim below is traced to a file and function; where a prior report already established a fact it is cited rather than re-derived. Where a claim is new, it is marked **[new]**.

Referenced documents that do not exist in this checkout: `MEALPLAN_SPECIFICATION_v1.md` (ten source files cite it; the live spec is `docs/planner/mealplan-specification-v3.md`), `NEXT_STEPS.md` / `docs/roadmap/next-steps.md` (cited by the spec and roadmap), and `docs/roadmap/open-questions.md` is an empty heading. The spec v3, `docs/planner/reasoning-logic.md`, `docs/llm/roadmap.md`, and `docs/tagging/tag-semantics-contract.md` were used instead.

---

## 0. Baseline recorded for this mission

| Check | Result |
|---|---|
| `python3 scripts/run_pytest.py` | 1074 passed, 2 third-party warnings, 1.95 s |
| `python3 scripts/run_export_openapi.py --check` | snapshot matches |
| `data/recipes/recipes.json` (gitignored, local) | 32 recipes; 14 have `llm_` ids |
| `llm_` recipes by dish name | 3 dish names ("Oatmeal with Fruits" ×6, "Grilled Chicken with Vegetables" ×5, "Quinoa Salad" ×3); 14 distinct content fingerprints, so dedupe never fired |
| `llm_` recipes with a core ingredient demoted to "to taste" | 2 (`llm_59834f6218eb974e`: rolled oats and water; `llm_0415c122c1511957`: cherry tomatoes) |
| `llm_` recipe cooking times | only 20 or 25 minutes (5 × instruction count) |
| `data/recipes/recipe_tags.json` (tracked) | registry of 8 system tags; `tags_by_id` is `{}` |
| `data/llm/feedback_cache.json` (**tracked in git**) | 30 cache keys, 77 cached drafts; 6 drafts are the unit-test fixture ("Generated" / "chicken breast" / "Cook it.") **[new]** |
| `.cache/ingredients/` (gitignored) | 83 entries; the ingredients used by `llm_` recipes resolve to: `bell pepper` → "TACO BELL, Nachos", `chicken breast` → "Chicken breast, roll, oven-roasted", `oats` → "Oil, oat", `banana` → "Bananas, dehydrated, or banana powder", `cherry tomatoes` → "Cherries, raw", `quinoa` → Branded "QUINOA", `milk` → Branded "MILK" |
| `.env` | present; defines `USDA_API_KEY`, `LLM_API_KEY`, `LLM_MODEL` (values not read) |

The tribunal's data findings (A1–A6) and the benchmark analysis (C1–C6) are taken as established. This document does not re-audit them; it maps where the LLM layer sits relative to them.

---

## 1. Entry points that can invoke the LLM

| Surface | Route / flag | LLM feature reached | Gate |
|---|---|---|---|
| API | `POST /api/v1/plan` with `planning_mode` ∈ {assisted, assisted_cached, assisted_live} | feedback loop (`plan_with_llm_feedback`) | `load_llm_settings().enabled`, else `LLM_DISABLED` 422 |
| API | `POST /api/v1/plan-from-text` | NL → config (`parse_nl_config`) in assisted modes; feedback loop in assisted modes | same; deterministic mode requires the prompt to be literal `PlannerConfigJson` JSON and calls no LLM |
| API | `POST /api/v1/recipes/generate-validated` | `generate_validate_persist_recipes` | none beyond settings |
| API | `POST /api/v1/recipes/tags/generate` | `tag_recipes` → `upsert_recipe_tags` | `llm_enabled: true` in body |
| API | `POST /api/v1/ingredients/match` | `match_ingredient_queries` + `validate_matches` | none |
| CLI | `--planning-mode assisted*` | feedback loop | settings |
| CLI | `--llm-generate-validated --count N --context-json ...` | generate/validate/persist; optional `--llm-generate-and-plan` | settings |
| CLI | `--tag-recipes --allow-llm-tagging` | `tag_recipes` → `upsert_recipe_tags` | flag |
| Flutter | Agent pane (`features/agent/agent_pane_screen.dart`) | `plan-from-text` with `planning_mode: "assisted"`, `ingredients/match`, `recipes/generate-validated` | `LlmConfigProvider.llmReady` (checks `/api/v1/llm/status`) |
| Flutter | Planner card | `/api/v1/plan` with `planning_mode` from `MealPlanProvider` (default `deterministic`) | assisted gated by `llmReady` |

Endpoints that touch USDA but **never** call the LLM: `/ingredients/search`, `/ingredients/resolve`, `/nutrition/summary`, `/recipes/sync`, `/recipes` CRUD, the `/tags` router.

Dead in production **[new]**: `ConstrainedIngredientFdcDisambiguator` (`src/llm/ingredient_disambiguator.py`) is only reachable when `CachedIngredientLookup` is built with `resolution_mode="assisted"` and an `llm_disambiguator`. No caller in `src/` does that; every production `APIIngredientProvider` is constructed with the default `deterministic` mode. The only tests of it inject the disambiguator directly.

---

## 2. The chain, boundary by boundary

Notation: **SoT** = source of truth for the output; **LLM?** = whether the LLM can influence the output; **Det?** = deterministic given the same inputs; **Rev?** = reversible; **Contam?** = can contaminate future planning runs beyond this request.

### B1. Natural language → `PlannerConfigJson`

`src/llm/constraint_parser.py::parse_nl_config` → `LLMClient.generate_json` → `parse_llm_json(PlannerConfigJson, raw)`.

| | |
|---|---|
| Input | free-text prompt; system prompt embeds the compact JSON schema |
| Output | `PlannerConfigJson{days 1–7, meals_per_day 1–8, targets{calories, protein}, preferences{cuisine[], budget∈{cheap,standard,premium}}, schedule_days?}` |
| SoT | the LLM's JSON, constrained only by the Pydantic schema (`extra="forbid"`) |
| Validation | syntactic only. No check that the config reflects the prompt |
| Failure modes | `PlannerConfigParsingError` → HTTP 422 `SCHEMA_VALIDATION_ERROR`; transport errors → 502/504/429 |
| Side effects | none |
| Det? | no (temperature 0 is requested, not guaranteed) |
| LLM? | total |
| Rev? | n/a (request-scoped) |
| Contam? | no direct persistence; but see B2/B3 for how the config becomes a hard pool filter |

Facts about the representation, all verified in `src/llm/schemas.py`:
- There is **no field** for allergies, disliked foods, excluded ingredients, fat range, calorie ceiling, micronutrient goals, τ, required or preferred tag slugs, or liked foods. (Tribunal D5 for allergies/dislikes/micros; the rest is **[new]**.)
- The system prompt instructs the model: *"If the user does not specify days, calories, protein, cuisine, or budget, choose sensible defaults: days=1, ... 2000 calories, 120g protein ..."*. The output does not record which values were user-stated and which were defaults. **[new]**
- `PlannerTargets` and `PlannerConfigJson` use `strict=False` so floats coerce to ints; `preferences.cuisine` is a free-string list.

### B2. `PlannerConfigJson` → `UserProfile`

`src/data_layer/user_profile.py::user_profile_from_planner_config`. Deterministic.

- `preferences.budget` (an economic preference) selects the **fat ratio bounds** used to derive the fat range and carbs (`_default_fat_ratio_bounds`: cheap 25–30 %, standard 28–35 %, premium 30–40 % of post-protein calories). The budget therefore silently becomes a hard macro constraint. **[new]**
- `meals_per_day` without `schedule_days` → every slot gets `busyness_level=4` (no cooking-time constraint).
- `preferences.cuisine` → `liked_foods` (scoring only) **and**, in assisted `plan-from-text`, also → the tag-filter `cuisine` preference (see B3).
- `allergies=[]`, `disliked_foods=[]`, `daily_micronutrient_targets=None`, `max_daily_calories=None`, τ=1.0 — always.
- Rejects only negative derived carbs (`PlannerConfigMappingError`).

### B3. Pre-planner pool filtering by tags

`server.py::_apply_recipe_tag_filter_pre_convert` → `tag_filtering_service.apply_tag_filtering` → `tag_filter.filter_recipe_ids_by_preferences`.

- In assisted `plan-from-text`, `final_cuisines = request.cuisine or cfg.preferences.cuisine` and `final_cost_level = request.cost_level or cfg.preferences.budget`. So the LLM's guessed cuisine/budget becomes a **hard** filter of the recipe pool. With the repository's `tags_by_id = {}`, any non-empty preference yields an **empty pool** (the service returns `[]` by design; the API adds a `tag_filtering` warning, the CLI does not). The planner then fails with FM-4 (if micronutrient targets are set) or FM-1, and in assisted mode that failure is *eligible* for recipe generation (B5). **[new]** chain: LLM-guessed cuisine → empty pool → LLM generates recipes → they are untagged → still filtered out next request.
- Deterministic `plan-from-text` never infers filters from the prompt.

### B4. `UserProfile` → `PlanningUserProfile` → `plan_meals`

`converters.convert_profile` (deterministic; demographic hard-coded `adult_male`; pins from persisted profile; batch locks from `MealPrepBatchRepository.list_active()`) → `planner.plan_meals` → `phase7_search.run_meal_plan_search`. No LLM. No network. Returns `MealPlanResult{success, termination_code, failure_mode, plan, report, stats, warning, plan_incomplete_reason}`.

Failure codes emitted in code (`phase7_search.py`): FM-3 (schedule length mismatch, pin pre-validation), FM-4 (structural pre-check at line 629 with no gating on D; FC-4 dead end; weekly validation), FM-5 (attempt limit), FM-TAG-EMPTY (only when the tag filter is what emptied the slot *and* the dead end occurs at that slot), FM-1 ("Empty candidate set or FC-5" for every other empty candidate set), FM-2 (candidate list exhausted, or daily validation failed with no backtrack target; report carries an `FM-MACRO-INFEASIBLE` failure object with `failure_mode="FM-2"`), FM-BATCH-CONFLICT (`planner.py`). Benchmark analysis C2a/C2b established that the code reported is often the last event, not the cause.

**Tag attachment differs by entry point [new]:** the API attaches `canonical_tag_slugs` and `hard_eligible_tag_slugs` to every `PlanningRecipe` (`_attach_canonical_recipe_tags`); the CLI calls `convert_recipes(all_recipes, calculator)` with no tag map, so on the CLI every recipe has an empty tag set and any slot with `required_tag_slugs` is unsatisfiable. `_matches_slot_required_tags` falls back to `canonical_tag_slugs` (including proposed LLM tags) whenever `hard_eligible_tag_slugs is None`, which is the state of every recipe the orchestrator builds (B11).

### B5. Failure → recovery eligibility

`orchestrator.plan_with_llm_feedback`:

```
result = plan_meals(...)
if result.success: return
if result.failure_mode not in {"FM-1","FM-2","FM-4","FM-5"}: return
```

- FM-3, FM-TAG-EMPTY, FM-BATCH-CONFLICT: returned untouched (correct: recipes cannot fix a pin or lock).
- FM-1 / FM-2 / FM-4 / FM-5: recovery runs regardless of *why*. Given C2a (macro-infeasible days reported as FM-1) and the FM-2 "exhaustion" path, recipe generation is triggered for conflicts no recipe can resolve (e.g. targets whose derived carbs are negative or a ceiling below the tolerance window) and for a *feasible* instance that merely hit the attempt cap (FM-5). There is no "can more recipes help?" test.
- Only after the first failure does the orchestrator build the LLM client and USDA provider (`_default_llm_client`, `_default_usda_provider`) when not injected; `assert_usda_capable_provider` is enforced.

### B6. Failure report → LLM context

`planner_assistant.build_feedback_context` (deterministic). Output keys: `failure_type`, `nutrient_deficits` (from `report.deficient_nutrients`, FM-4 only), `macro_violations` (from `report.failed_days`, present only for the daily-validation FM-2 path; the "exhaustion" FM-2 path emits `failed_days=[]`, so the context is empty), `days`, `meals_per_day` (day 0 only), `busyness_by_day`, `workout_gaps_by_day`.

**Withheld from the LLM [new]:** excluded ingredients / allergies, liked foods, calorie and protein targets, fat range, calorie ceiling, the existing pool (names or nutrition), which slot or day failed for FM-1, required tag slugs, cuisine/budget preferences, pins. The generator therefore cannot avoid allergens or target a slot; `_compute_macro_deficit_amounts` supplies deficits only when `failed_days` is populated.

### B7. LLM → `RecipeDraft[]`

`planner_assistant.suggest_targeted_recipe_drafts` → `recipe_generator.generate_recipe_drafts`.

| | |
|---|---|
| Input | `count` (default `min(3, meals_per_day)`), context JSON from B6 |
| Output | exactly `count` `RecipeDraft{name, ingredients[{name, quantity, unit∈SUPPORTED_UNITS}], instructions[], tags?}` after alias normalization (`title`→`name`, `amount`→`quantity`, drop `servings/prep_time/cook_time`) |
| Validation | strict schema; envelope must be exactly `{"drafts": [...]}` with `len == count` |
| Failure modes | any envelope/schema problem raises `RecipeGenerationError`; LLM transport raises `LLMClientError`. **Neither is caught by the orchestrator.** In the API these map to 422 / 502 / 504, replacing the planner's failure report with an HTTP error, even though a deterministic `MealPlanResult` already existed. **[new]** |
| Det? | no |
| LLM? | total (ingredient names, quantities, units, instructions) |
| Contam? | not yet; see B9–B10 |

`RecipeDraft.tags` (a `RecipeTagsJson`) is accepted from the LLM here but never read by the validator or repository; it is dropped.

### B8. Feedback cache

`feedback_cache.py`. Key = sha256(`cache_schema_version`, `failure_signature` = sha256(failure_mode, termination_code, whole `report`), `feedback_context`, `count`, `model_version`). Value = raw drafts (re-validated on read). Written atomically on every live generation unless `assisted_live`.

- `assisted_cached` raises `DeterministicCacheMissError` (HTTP 500 `DETERMINISTIC_CACHE_MISS`) on a miss. Because the key includes the full report (attempt counts, closest-plan snapshot), any change in pool or profile is a miss.
- `data/llm/feedback_cache.json` is committed to git and contains unit-test fixtures (4 test modules exercise orchestrator paths without redirecting `LLM_FEEDBACK_CACHE_PATH`). The cache is therefore shared, unversioned state that test runs mutate. **[new]**
- Cached drafts are replayed as if fresh: the same failed candidates are re-proposed whenever the signature repeats.

### B9. Draft validation

`recipe_validator.validate_recipe_draft(draft, provider)`; the mandatory `assert_usda_capable_provider` is a duck-typed attribute check (`usda_capable=True`).

Order actually executed:
1. `IngredientValidator.validate` per ingredient: unit alias → canonical; `cup/tsp/tbsp` → ml, `oz/lb` → g; `IngredientNormalizer` strips descriptors (`large`, `raw`, `boneless`, …) to form the provider lookup key. Rejects with `INVALID_UNIT` / `INVALID_QUANTITY` / `INVALID_INGREDIENT_INPUT`.
2. `provider.resolve_all(measurable names)` in a loop: on `IngredientResolutionError` for name X, X is **converted to "to taste"** and resolution retried (tribunal D2). `get_ingredient_info(name) is None` → also demoted. Reject only when nothing measurable remains (`EMPTY_RECIPE`).
3. `NutritionCalculator.calculate_ingredient_nutrition` must not raise for each measurable ingredient (`NUTRITION_COMPUTATION_FAILED`). The computed values are discarded; only "did not raise" is checked.
4. `Recipe(id="", name, ingredients, cooking_time_minutes=min(120, 5×len(instructions)), instructions)`.

Not checked: the resolved USDA description vs. the requested name; macro plausibility; allergens against any profile; serving size (`default_servings` is 1 on write); duplicates against the pool by name or near-content; that the draft addresses the failure that triggered it; volume→gram conversion for `ml` units (the calculator treats ml as g regardless of density, tribunal A5).

| | |
|---|---|
| SoT | provider resolution result (USDA record chosen by `ingredient_ranker`) |
| LLM? | names/quantities/units are LLM-authored; nutrition is provider-derived; cooking time is fabricated by code |
| Det? | yes given provider state; but provider state (the disk cache) is mutated by this very step |
| Side effect | `resolve_all` writes new `.cache/ingredients/*.json` entries for every LLM-authored name that resolves, including wrong resolutions. Not reverted when the draft is rejected. **[new]** |

### B10. Persistence

`repository.append_validated_recipes(path, [ValidatedRecipeForPersistence])`.

- Fingerprint = sha256(sorted measurable `{name, quantity(6dp), unit}` + sha256(normalized instructions)); exact-match dedupe against all existing recipes. Quantity or unit variants (`2 tbsp` vs `29.58 ml`) are distinct — the 14 persisted duplicates are the evidence.
- ID = `llm_` + fingerprint[:16]; atomic `os.replace`.
- Written into **the same `recipes.json` as user recipes** with **no provenance**: no `source`, `created_at`, `model`, failure signature, resolved `fdc_id`s, or validation record. `default_servings=1`. **[new]**
- Nothing is written to `recipe_tags.json`; generated recipes are untagged forever unless a separate tagging run happens.
- Rollback: none. The only removal path is `DELETE /api/v1/recipes/{id}`.

| | |
|---|---|
| Det? | yes |
| Rev? | manual only |
| Contam? | **yes, permanently**: every future deterministic plan (CLI, API, benchmark with real data) sees these recipes |

### B11. Pool update inside the loop

`_append_new_recipes_to_pool`: reloads `RecipeDB`, resolves the new ingredients, `convert_recipes(new_recipes, calculator)` **without a tag map**, appends, sorts by id. On any exception the fallback `_rebuild_recipe_pool` reloads **all** recipes from disk and converts them without tags.

Consequences **[new]**:
- New recipes enter with `canonical_tag_slugs=∅`, `hard_eligible_tag_slugs=None`.
- The fallback rebuild discards the request's `recipe_ids` subset, the tag-filter result, protected batch recipes, and the `hard_eligible_tag_slugs` attributes on every recipe — the retry then plans over a different pool than the request specified. Only a stderr JSON line records that the fallback fired.

### B12. Retry and termination

```
for attempt in 1..max_feedback_retries(=3):
    drafts = cache or LLM; dedupe against persisted fingerprints
    accepted, _ = validate; persisted_ids = append
    pool = pool + new
    result = plan_meals(profile, pool, days)
    if success: return
    if failure_mode not eligible: return
    if signature(result) == previous signature and not persisted_ids: return   # "abort"
```

- Bound: 4 planner runs, 3 LLM generation calls, each LLM call with up to `LLM_MAX_RETRIES` (default 3) transport retries.
- Termination conditions actually distinguished: success; ineligible failure; same signature with nothing persisted; loop exhaustion. All four failure exits return the **last planner result** with the same shape; the history is appended to `result.stats["llm_feedback_attempts"]` and `report["llm_feedback"] = {"max_feedback_retries": 3}`.
- Not distinguished: infeasible-by-construction, validation produced nothing, LLM/data-source error (raised instead), no useful recovery.
- "Progress" = a new recipe was persisted, not that the failure got closer to feasible. If the signature changes for an unrelated reason (attempt count, closest plan) the loop continues even when nothing was persisted.
- The retry re-runs `plan_meals` with the same `profile` object (pins/locks preserved) but a pool whose tag attributes differ from the first attempt (B11).

### B13. Result to caller

`output/formatters.format_result_json` builds the API/CLI JSON from `plan`, `report`, `warning`, `daily_trackers`, `plan_incomplete_reason`. It never reads `result.stats` (0 occurrences), so `llm_feedback_attempts` — the only record of what the loop did, which recipes it persisted, and why it stopped — **never reaches the API response or CLI JSON**. The response carries only `report.llm_feedback.max_feedback_retries`. **[new]**

The API then reloads the whole recipe store to build `recipe_by_id` for formatting, so a plan that used a generated recipe can be rendered.

---

## 3. The other LLM paths

### Standalone generation (`generate_validate_persist_recipes`)
B7 → B9 → B10 with a caller-supplied free-form `context` dict (the API accepts any JSON object). Same persistence and contamination properties; no planner involvement. CLI `--llm-generate-and-plan` then runs a deterministic plan over the augmented pool.

### Ingredient matching (`/ingredients/match`)
`match_ingredient_queries`: LLM returns `{matches:[{query, normalized_name, confidence}]}` in order; the code overwrites `query` with the input string. `validate_matches`: drop if `confidence < 0.7` (self-reported by the model); otherwise `provider.resolve_all([normalized_name])` and accept if `get_ingredient_info` returns a dict. `canonical_name` is set from `info["name"]`, which `APIIngredientProvider._entry_to_dict` sets to the **lookup key itself**, so `canonical_name == normalized_name` and the USDA description is never surfaced to the caller. **[new]** Side effect: disk cache entries for every LLM-normalized name.

### Tagging (`tag_recipes` → `upsert_recipe_tags`)
- One LLM call per recipe; strict `RecipeTagsJson{cuisine: free string, cost_level: enum, prep_time_bucket: enum, dietary_flags: enum[]}`; invalid outputs are dropped silently.
- The LLM never emits `tag_slugs_by_type`, `tag_metadata`, or `aliases`, so **no canonical slug from the registry is ever produced by LLM tagging**, and the DM-6 `proposed → approved` lifecycle has no producer (tribunal D8). `prep_time_bucket` is an LLM guess even though `cooking_time_minutes` is known and `time_bucket()` exists.
- `upsert_recipe_tags(path, tags_by_id)` **replaces `tags_by_id` wholesale** with the dict passed in (`_write_tags_payload(tags_by_id=tags_by_id, ...)`). Both LLM tagging callers (`server.py:1348`, `cli.py:312`) pass only the LLM output, so a tagging run **deletes every user-curated `tag_slugs_by_type` / `tag_metadata` entry** and every recipe the LLM failed to tag. `recipe_sync.py` merges before calling upsert and is safe. **[new]**
- `cuisine` is a `StrictStr`, not an enum: the LLM can emit any value, and that value is used by the hard pool filter (B3).

### Tag registry
`tag_repository.create/rename_display/add_alias/merge` are user/system paths via `/api/v1/tags`; `create` hard-codes `source="user"`. Nothing in `src/` creates a registry entry with `source="llm"`, so `enrich_tag_meta`'s `eligibility="proposed"` defaulting and `is_planner_hard_eligible`'s LLM branch are exercised only by tests and by the benchmark fixture.

### FoodData Central resolution (shared by all paths)
`CachedIngredientLookup.lookup(canonical_name)`:
1. disk cache hit by sanitized filename → return (no version, no timestamp, no query provenance, no ranking rationale stored);
2. miss → `search_candidates(top 8, all four data types)` → `rank_candidates` (data-type priority ×1000, prefix match, comma/length penalties, raw-like reward) → optional LLM tie-break (never wired, §1) → `get_food_details` → `NutrientMapper` → write cache entry `{canonical_name, fdc_id, description, data_type, nutrition}`.

`APIIngredientProvider.resolve_all` is fail-fast in the planner path but its failures are swallowed in the validator path (B9). The provider's output dict is `{"name": <lookup key>, "per_100g": {...}}` — the `fdc_id` and description do not travel past the provider boundary, so nothing downstream (recipes, planner, API responses) can state which USDA record a number came from.

Category conflation, as stored today:

| Category | Where it lives | Distinguishable? |
|---|---|---|
| Authoritative (USDA per-100 g) | `.cache/ingredients/*.json` `nutrition` | only inside the cache file; mixed with mapper-derived unit conversions (vitamin D ×40) and mapper errors (tribunal A3) |
| Derived (scaled, summed, unit-converted) | `PlanningRecipe.nutrition`, API `per_100g` payloads | not labelled |
| Generated (LLM recipes, fabricated cook time, LLM tags, LLM-normalized names) | `recipes.json`, `recipe_tags.json`, cache filenames | only by the `llm_` id prefix on recipes; tags and cache entries carry no marker |

---

## 4. Every place the LLM layer changes system state

| # | Mutation | Owner | Trigger | Transactional? | Reversible? | Provenance recorded? |
|---|---|---|---|---|---|---|
| S1 | append recipes to `data/recipes/recipes.json` | `repository.append_validated_recipes` | feedback loop, `/recipes/generate-validated`, CLI generate | atomic file write; **not** coordinated with S2/S3 | manual delete only | no |
| S2 | write `.cache/ingredients/<name>.json` | `CachedIngredientLookup.lookup` | any `resolve_all` on LLM-authored names (validator, matcher) | per-file, not atomic (`open(...,'w')`) | manual delete | no |
| S3 | replace `tags_by_id` in `data/recipes/recipe_tags.json` | `tag_repository.upsert_recipe_tags` | LLM tagging (API/CLI) | atomic; **destructive** of prior entries | no (no backup) | no (`source` lives only on registry entries, never on per-recipe tags) |
| S4 | upsert `data/llm/feedback_cache.json` | `feedback_cache.upsert_cached_drafts` | every live generation with cache enabled | atomic | manual; file is git-tracked | key only |
| S5 | in-memory planner pool for the retry | `orchestrator._append_new_recipes_to_pool` / `_rebuild_recipe_pool` | after S1 | n/a | n/a | fallback logged to stderr only |
| S6 | in-memory `UserProfile` from NL | `user_profile_from_planner_config` | plan-from-text | n/a | n/a | which fields were defaulted is not recorded |

The LLM cannot directly write to the planner's constraints (`PlanningUserProfile` is built from the profile, not from LLM output, except via S6), pins, batches, the tag registry, or the reference tables. It can influence the *pool* (S1, S5), the *filters* (S3, and B3 through S6's cuisine/budget), and the *nutrition numbers* the planner sees (S2 via names it invents).

---

## 5. What the existing tests establish about this chain

Coverage present (all with mocked LLM and fake providers): strict schema rejection for every `src/llm` module; envelope/count checks; orchestrator retry-then-succeed, abort on repeated signature, cache hit/miss/model-change, within-attempt and cross-attempt dedupe; USDA-capability assertion; repository dedupe by fingerprint and instruction hash; routing of `planning_mode` to `plan_meals` vs orchestrator in API and CLI; deterministic `plan-from-text` never building an LLM client; tag repository normalization/alias/merge and DM-6 eligibility booleans; ingredient-cache mode gating.

Coverage absent (relevant to this mission):
- `test_llm_recipe_validator.py` asserts the to-taste demotion as **correct** behaviour (`test_validate_recipe_draft_to_taste_fallback_*`), so the AGENTS.md rule is contradicted by a passing test.
- No test checks that a resolved USDA description matches the requested ingredient, that generated recipes respect excluded ingredients, that a retry improved feasibility, that `llm_feedback_attempts` is visible to a caller, that LLM tagging preserves existing `tags_by_id`, that the orchestrator survives a `RecipeGenerationError`, that the fallback rebuild preserves tags or `recipe_ids`, or that NL parsing preserves a stated allergy.
- `test_planner_regression_with_llm_disabled.py` is the only golden-output guard, and only for the LLM-disabled path.

---

## 6. Discrepancies with the prior reports that affect this investigation

1. **Tribunal D8 understated the tagging risk.** It reported that the lifecycle has no data flowing through it. The additional fact is that the LLM tagging write path is destructive to curated tags (S3), so populating `tags_by_id` by hand and then running LLM tagging would erase the curation.
2. **Tribunal D7 ("assisted planning mutates the recipe store")** is confirmed, and the mutation is invisible to the caller because `stats` is not serialized (B13).
3. **Architecture.json** says `plan-from-text` "uses deterministic JSON parse path or assisted LLM parse path" — accurate — but nowhere documents that assisted mode turns the parsed cuisine/budget into a hard pool filter (B3).
4. **`docs/llm/roadmap.md`** Phase 5 lists "reject if unmatched ingredients exist" as a mandatory validation step and Phase 6 lists "prevent duplicate recipe generation using recipe fingerprint set"; the code demotes instead of rejecting, and the fingerprint is exact-quantity. The roadmap's "Implementation status: completed" line is therefore inaccurate for those two invariants.
5. **AGENTS.md** "Do not persist generated recipes unless nutrition validation and ingredient resolution pass" is not what `validate_recipe_draft` does (tribunal D2, confirmed).
6. **The benchmark harness (`evaluation/harness/run_benchmark.py`)** measures the deterministic planner only; none of the 150 scenarios exercise B1–B13. There is currently no machine-checkable evidence about the LLM layer at all.

---

## 7. Summary map

```
NL prompt ──(B1 LLM, schema-only check)──▶ PlannerConfigJson  [no allergy/fat/micro/tag fields; defaults invented]
   └─(B2 deterministic)──▶ UserProfile  [budget ⇒ fat range; allergies=[]]
        └─(B3 tag filter; LLM cuisine/budget become HARD filters; tags_by_id={} ⇒ empty pool)
             └─(B4 deterministic planner)──▶ MealPlanResult{failure_mode}
                  └─(B5 eligibility = code ∈ {FM-1,FM-2,FM-4,FM-5}; no "would recipes help?" test)
                       └─(B6 context: deficits only; allergens/targets/pool withheld)
                            └─(B7 LLM drafts; any schema/transport error escapes as HTTP error)
                                 ├─(B8 cache: git-tracked, test-contaminated, replay of failed drafts)
                                 └─(B9 validate: resolve-or-demote; no plausibility; cache writes as side effect)
                                      └─(B10 persist into shared recipes.json; no provenance; exact-dedupe)
                                           └─(B11 pool += untagged recipes; fallback rebuild drops tags & subset)
                                                └─(B12 retry ≤3; stop on same-signature-and-nothing-persisted)
                                                     └─(B13 result; loop history dropped at serialization)
```
