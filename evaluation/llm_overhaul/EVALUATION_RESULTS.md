# EVALUATION_RESULTS.md — Baseline measurements (Phases 4–8)

**Snapshot:** branch `llm-overhaul` at `779af36`, no `src/` changes. **Model:** `gpt-4o-mini` via the repo's `LLMClient` (temperature 0). **Date:** 2026-09-18.
**Harness:** `evaluation/llm_overhaul/harness/` — `run_nl_benchmark.py` (live, 84 calls), `run_recovery.py` (offline scripted LLM + 5 live calls), `fdc_audit.py` (offline), `tag_eval.py` (offline + 12 live calls). Raw outputs in `evaluation/llm_overhaul/results/`. All writes went to temporary directories; repository data is unchanged.

---

## Phase 4 — Natural-language interpretation (42 prompts, 2 runs)

### Headline

| Metric | Result |
|---|---|
| Numeric field accuracy (representable fields) | days 36/37, meals_per_day 35/35, calories 34/35, protein 34/34, cuisine 3/3, budget 3/3, workouts 3/3, busyness 2/2, per-day meal counts 1/1, required tag 1/1 |
| Model omission rate (field exists, value missing) | 0/42 |
| **Structural omission rate** (schema has no field) | **11/42 cases, 15 constraints dropped** — every allergy (NL-03, 04, 40), every dislike (NL-04, 38), the calorie ceiling (NL-13), micronutrient goals (NL-14), fat range (NL-15, 16), diet restrictions (NL-16, 21, 22), τ (NL-37) |
| Misplacement | NL-21 "vegan" → `cuisine=["vegan"]`; NL-22 → `cuisine=["gluten-free","dairy-free"]` (in assisted plan-from-text these become hard pool filters against a taxonomy that has no such cuisine) |
| Documented defaults filled in | 35/42 cases carry at least one defaulted value; nothing marks them as defaults |
| **Invented non-default constraints** | **14/42 cases** emitted `schedule_days` that the user never described; 36 of the 39 invented slots carry `busyness_level=3`, i.e. a ≤30-minute cook-time cap the user never asked for (the documented default without `schedule_days` is level 4, no cap) |
| Hard/soft misclassification (system level) | 7: soft cuisine → hard filter (NL-05, NL-40); budget → fat-range bound (NL-07, 08, 40); stated fat range replaced by budget-derived range (NL-15, 16) |
| Invalid configurations | expected and correctly rejected: NL-27 (10 meals), NL-29 (8 days), NL-42 (protein > calories, mapping error). **Silently modified:** NL-28 "0 days" → `days=1`. **Unexpected rejection:** NL-24 ("I love salmon and eggs") — the model encoded the likes as `required_tag_slugs=["eggs"]` / `preferred_tag_slugs=["salmon"]`, the registry rejects unknown slugs, and the whole request fails with a schema error |
| Unit handling | NL-09 (0.8 g/lb × 180 lb) ✓ 144; NL-10 (1.6 g/kg × 80 kg) ✓ 128; NL-34 (30 % of 2000 kcal) ✓ 150; **NL-33 8400 kJ → `calories=8400`** (not converted); NL-41 "150 lbs of protein" → 150 g |
| Ambiguity handling | NL-13 "stay under 1500" → `calories=1500` (a ceiling became a centre target with ±10 % window, i.e. up to 1650 allowed); NL-25 "around 2000, decent protein" → 2000/120 with no marker; NL-31 contradiction resolved to 2 meals silently |
| Determinism (run 1 vs run 2) | **38/42**; NL-03 emitted `schedule_days` in one run and not the other; NL-18 gave breakfast busyness 4 vs 1; NL-40 and NL-42 differed in invented busyness levels |

### What the mapping layer did with the dropped constraints

| Case | User said | `UserProfile` after mapping |
|---|---|---|
| NL-03 | allergic to peanuts | `allergies=[]` |
| NL-04 | shellfish allergy, hates mushrooms | `allergies=[]`, `disliked_foods=[]` |
| NL-13 | stay under 1500 kcal | `daily_calories=1500`, `max_daily_calories=None` |
| NL-15 | fat 50–70 g | `daily_fat_g=(49.8, 62.2)` from `budget=standard` |
| NL-16 | keto, 75 % fat | `daily_fat_g=(43.6, 54.4)`, `daily_carbs_g=239.75` |
| NL-21 | vegan | `liked_foods=["vegan"]`; assisted mode adds hard filter `cuisine=vegan` |

### Interpretation

The model is a good numeric extractor and a poor place to put trust: nothing it drops is visible downstream, and what it invents (`schedule_days` with a 30-minute cap) is indistinguishable from a user constraint. The two failures that matter most are architectural, not model errors: the schema cannot carry safety constraints (IN-1), and the pipeline treats defaults, guesses and statements identically (IN-2/IN-3). Determinism at 90 % means `assisted_cached` replay is not a correctness guarantee.

---

## Phase 5 — Recipe discovery / recovery (15 scripted cases + 5 live probes)

Real `plan_with_llm_feedback`, real validator and repository, real cache-only USDA provider (no network), scripted LLM drafts built from the benchmark library so that feasibility is known by construction. Each case starts with a sandboxed `recipes.json` and its own feedback cache.

| Case | Situation | Recipes could help? | Initial → final code | Terminal (observed) | LLM calls | Persisted | Intent-violation flags |
|---|---|---|---|---|---|---|---|
| R-01 | fitting pool | n/a | OK | SUCCESS | 0 | 0 | — |
| R-02 | one recipe missing, LLM supplies it | yes | FM-1 → OK | SUCCESS | 1 | 1 | tags lost on retry pool |
| R-03 | LLM names unresolvable ingredients | yes | FM-1 → FM-1 | NO_USEFUL_RECOVERY | 1 | **1 (2 ingredients demoted to "to taste")** | demoted recipe persisted; residue after failure |
| R-04 | one recipe, three slots (HC-2) | yes | FM-1 → OK | SUCCESS | 1 | 2 | tags lost |
| R-05 | negative derived carbs | **no** | FM-1 → FM-1 | NO_USEFUL_RECOVERY | **1** | **1** | residue after failure |
| R-06 | pool emptied by user's tag filter | no (bypass) | FM-1 → OK | SUCCESS | 1 | 3 | **success bypassed the filter** |
| R-07 | required tag on slot 1 unheld | no (tag gap) | FM-1 → FM-1 | RECOVERY_LIMIT_REACHED | **3** | **3** | residue; tags lost |
| R-08 | iron structural gap (FM-4) | yes | FM-4 → OK | SUCCESS | 1 | 1 | tags lost |
| R-09 | 5-minute slot, LLM draft with one instruction | only with a real quick recipe | FM-1 → OK | SUCCESS | 1 | 1 | **relies on fabricated cook time** |
| R-10 | batch lock exceeds slot cap | no | FM-3 | UNRECOVERABLE (code) | 0 | 0 | — |
| R-11 | feasible instance at attempt cap (FM-5) | no (search) | FM-5 → FM-5 | NO_USEFUL_RECOVERY | **1** | **1** | residue |
| R-12 | LLM returns wrong count | n/a | FM-1 → exception | DATA_SOURCE_FAILURE | 1 | 0 | **planner result lost** |
| R-13 | "peanuts" excluded, draft has peanut butter | yes (safe recipe) | FM-1 → OK | SUCCESS | 1 | 1 | **plan contains excluded-class ingredient** |
| R-14 | same non-fitting draft repeated | no | FM-1 → FM-1 | NO_USEFUL_RECOVERY | 1 | 1 | residue |
| R-15 | incremental update fails → rebuild | yes | FM-1 → OK | SUCCESS | 1 | 1 | **retry pool grew 6 → 64; 0 recipes with hard-eligible attrs** |

Aggregates: positive cases (R-02, R-04, R-08) all recovered — **the mechanism works when handed a fitting, resolvable draft**. Of the six cases where recipes cannot help (R-05, R-06, R-07, R-10, R-11, R-14), the loop refused only R-10; it called the LLM in the other five and persisted **7 recipes across 5 failed requests**. Every case where the loop added a recipe lost hard-eligibility attributes on the retry pool (11/15). `cache_files_written` was 0 in every case only because the provider was cache-only; with a live USDA client B9 writes on every new name.

### Live sub-experiment (real model, real feedback contexts)

| Context sent | Drafts returned | Offline-resolvable names | Notes |
|---|---|---|---|
| R-02 (FM-1, empty context) | Quinoa Salad; Grilled Chicken with Veggies; Oatmeal with Fruits | 12/12 | |
| R-05 (FM-1, empty context) | Quinoa Salad; Grilled Chicken with Vegetables; Oatmeal with Fruits | 12/12 | identical dish set |
| R-07 (FM-1, empty context) | same three | 12/12 | identical |
| R-13 (FM-1, empty; `peanuts` excluded but not sent) | same three | 12/12 | no peanut by luck, not by design |
| R-08 (FM-4, iron deficit sent) | Iron-Rich Spinach Salad; Beef and Broccoli Stir-Fry; Lentil and Quinoa Bowl | **5/11** | targeted, but `beef sirloin`, `broccoli`, `lentils`, `ginger`, `vegetable broth`, `cumin`… are not in the cache → demotion or (online) arbitrary resolution |

Four different failures with the same empty context produced the same three generic recipes — the same three dishes that make up the 14 `llm_*` residue recipes in the local `recipes.json` and 71 of the 77 drafts in the committed feedback cache. The loop is not "discovering" recipes; it is re-deriving one fixed answer to an uninformative prompt.

A run before per-case cache isolation also showed **cross-request replay**: R-13 received R-02's cached drafts with zero LLM calls because the failure signature and context were identical, although R-13's profile excluded peanuts. The cache key contains the failure, not the user.

### Distinguishing "more recipes would help" from "nothing can help"

Today the loop makes this distinction in exactly one way: the failure code is FM-3/FM-TAG-EMPTY/FM-BATCH-CONFLICT or it is not. R-05 (impossible targets), R-06 (filter), R-07 (tag), R-11 (search cap) all pass that test and consume LLM calls and disk writes. Nothing in the loop inspects targets, filters, tags, or search exhaustiveness.

---

## Phase 6 — FoodData Central pipeline (83 cached resolutions)

### Adjudication of resolution correctness

| Class | Count | Entries |
|---|---|---|
| Correct food and usable form | 65 | (remainder) |
| **Wrong food** (different identity) | **9** | `bell pepper`→TACO BELL Nachos; `cherry tomatoes`→Cherries, raw; `chicken breast`→deli roll; `eggs`→Bread, egg; `milk 1% fat lowfat`→cottage cheese; `oats`→Oil, oat; `banana`→dehydrated powder; `acai berry`→fortified drink; `tortillas corn`→flour tortillas |
| Right food, materially wrong form | 5 | `black beans`→raw dry seeds (341 kcal/100 g vs ~130 cooked); `feta cheese reduced fat`→full-fat; `tomato`→crushed canned; `mushrooms`→shiitake; `jasmine rice in unsalted water`→short-grain |
| Branded label data | 4 | `milk`, `quinoa`, `rolled oats`, `salami genoa` |

Identity error rate **11 %**; identity-or-form error **17 %**. The deterministic ranker has no notion of food identity; it prefers SR Legacy, prefix matches and short descriptions, which is exactly how "Oil, oat" beats "Oats" and "Cherries, raw" beats "Tomatoes, cherry".

### Mapping and cache integrity (automated flags)

| Flag | Count | Meaning |
|---|---|---|
| zero kcal with non-zero macros | 5 (all Foundation: kiwi, mushrooms, spaghetti squash, sweet potato, tomato) | energy nutrient IDs 2047/2048 unmapped (FDC-4) |
| vitamin D > 500 IU/100 g | 11 (egg yolk, "eggs"=bread, feta, parmesan ×2, cheddar, pecorino, salmon, tilapia, tuna, milk) | IU/µg IDs swapped (FDC-4) |
| duplicate identities under name variants | 4 (`banana`/`bananas` resolve to **different** foods; `black beans`/`black beans drained`; two greek yogurts; two milks) | FDC-6 |
| cache entry version/timestamp | none stored | FDC-7 |

### Provenance

`APIIngredientProvider.get_ingredient_info` returns `['name', 'per_100g']`; `fdc_id`, description, data type and ranking rationale do not cross the provider boundary. A persisted recipe therefore cannot be traced to the USDA records that produced its numbers. 27 ingredient lines in the local `recipes.json` use `ml`/`cup`/`tbsp`/`tsp` and are scaled as grams on the planning path (FDC-3).

An additional normalization defect surfaced while building R-08: the validator runs `IngredientNormalizer` on LLM names, stripping `raw`, so a draft naming the cached ingredient `avocados raw all commercial varieties` produced the key `avocados all commercial varieties`, failed to resolve, and was demoted to "to taste". Names that are already canonical cache keys are re-normalized into non-keys (G-01).

### Category conflation and the smallest change that fixes it

Authoritative (USDA per-100 g), derived (mapped, converted, scaled, summed) and generated (LLM names, fabricated cook times, LLM tags) data currently share the same shapes with no marker. The smallest change that gives every persisted number an explainable origin:

1. A `ResolutionRecord` stored with each cache entry: `{query, cache_key, fdc_id, description, data_type, mapper_version, resolved_at, method ∈ {deterministic, llm_tiebreak, user_pick}, rank_confidence, margin}`.
2. The provider dict gains a `provenance` sub-object carrying that record (additive; `NutritionCalculator` ignores unknown keys).
3. `Recipe.ingredients[]` gains an optional `fdc_id` written at validation time; `Recipe` gains `provenance {source ∈ {user, sync, llm_generate, llm_feedback}, created_at, model, failure_signature?, validation_version}`.
4. `NutritionProfile` produced by the calculator carries `derived_from: [fdc_id…]` and `unit_conversions_applied: [...]`.
5. `RecipeTagsJson` per-recipe entries gain `source` and `eligibility` (the registry already has them; the per-recipe payload does not).

No planner code changes; all fields are additive and optional, so the deterministic path is unaffected.

---

## Phase 7 — Tagging

### Offline gates

| Test | Result |
|---|---|
| T-01 unknown slug in `required_tag_slugs` rejected | pass |
| T-02 proposed LLM tags (4 in the benchmark fixture) excluded from hard eligibility | pass (0 leaked) |
| T-03 alias `batch-cook` → `meal-prep` | pass |
| **T-04 LLM-tagging write preserves curated `tags_by_id`** | **fail: 64 entries → 1; and `upsert_recipe_tags(path, {})` → 0 entries** |
| Schema accepts free-string cuisine | `"martian fusion 2000"` accepted |

### Live tagging (6 recipes × 2 runs)

| Metric | Result |
|---|---|
| Valid `RecipeTagsJson` objects returned | **0/6 in both runs** |
| Why | the tagger's prompt names the schema but never includes it; the model returned `{"recipe_name", "cooking_time", "ingredients", "instructions", "tags": ["vegetarian","quick","healthy","main dish"]}`, which fails `extra="forbid"` and lacks all four required fields |
| Consequence today | `POST /api/v1/recipes/tags/generate` reports `tagged_recipe_count: 0` **and replaces `tags_by_id` with `{}`**, deleting every curated per-recipe tag (T-04 + upsert-with-empty) |
| T-05 prep bucket vs deterministic bucket, T-06 contradictions, T-07 cuisine vocabulary, T-08 determinism | not measurable: no valid output |

The constraint parser embeds its JSON schema in the prompt and validated 41/42 prompts; the tagger does not and validated 0/6. Same client, same model.

### Decision: deterministic, LLM-assisted, or hybrid?

Per semantic class (from `docs/tagging/tag-semantics-contract.md`):

| Class | Evidence required | Producer | Rationale |
|---|---|---|---|
| effort_system (`time-*`) | `cooking_time_minutes` | **deterministic** (`time_bucket()` already exists) | the fact is known; guessing it is TG-2 |
| exclusion (`no-shellfish`, dietary flags) | ingredient list vs a curated allergen/diet taxonomy | **deterministic** where the taxonomy covers the ingredient; LLM may *propose* for uncovered ingredients, quarantined | safety-relevant (S0); must not depend on a model's reading of "tortillas corn" |
| nutrition_claim (`high-protein`, `high-fiber`) | computed nutrition vs thresholds | **deterministic** | derivable |
| meal_role (`breakfast`, `dinner`) | convention | LLM-proposed from a closed slug list, quarantined until approved | no deterministic source; soft use only until approved |
| capability (`portable`, `reheats-well`, `meal-prep`) | judgement | LLM-proposed from a closed slug list, quarantined | same |
| identity_hint (cuisine) | judgement | LLM-proposed from a **closed vocabulary**; display/soft only | never a hard filter |

So: **hybrid**, with the split decided by whether the evidence is computable. Three non-negotiable mechanics regardless of split: the prompt must embed the registry's slug list and the schema; the write must merge, never replace; every LLM-produced entry carries `source="llm"`, `eligibility="proposed"`.

---

## Phase 8 — The recovery loop as a control loop

### Model

```
S0: (profile P, pool R, filters F, stores D={recipes, cache, tags, feedback})
  ─plan──▶ result r ∈ {OK, FM-1, FM-2, FM-3, FM-4, FM-5, FM-TAG-EMPTY, FM-BATCH-CONFLICT}
  ─classify(r)──▶ {recoverable?, gap spec}          ← today: code ∈ {FM-1,2,4,5}; gap spec absent
  ─act──▶ drafts (LLM or cache) → validate → persist(D.recipes, D.cache, D.feedback)   ← irreversible
  ─mutate──▶ R' = R ∪ new (untagged) | rebuild(D) (loses F, tags)
  ─plan(P, R')──▶ r'
  ─terminate?──▶ SUCCESS | ineligible | no-progress | limit | exception
```

### Transition properties, as measured

| Transition | Justified | Observable | Bounded | Reversible | Idempotent | Testable |
|---|---|---|---|---|---|---|
| plan → classify | **no**: 5/6 unrecoverable cases classified recoverable (R-05, 06, 07, 11, 14) | code only; no gap spec | yes | n/a | yes | yes |
| classify → act (LLM/cache) | no: context empty for FM-1/FM-2 (P1, live probes) | context is deterministic but not surfaced to caller | 3 calls | n/a | cache makes it replayable, but cross-request (R-13 replay) | yes |
| act → validate | partially: syntactic + resolvability; demotion accepted (R-03), allergens accepted (R-13), cook time fabricated (R-09) | rejected list counted, reasons dropped | yes | cache writes are not | no (network state) | yes |
| validate → persist | no fitness criterion; persists before knowing whether the retry helps (7 residue recipes in 5 failed requests) | file write only; no provenance | yes | **no** | dedupe by exact fingerprint only | yes |
| persist → mutate pool | drops tags (11/15), may replace pool with the whole store (R-15: 6 → 64) | stderr line only | yes | in-memory | no | yes |
| mutate → plan | same profile; different pool semantics | — | yes | — | yes | yes |
| plan → terminate | 4 exits collapse into one shape; exceptions lose the planner result (R-12) | `stats` dropped at serialization (B13) | yes (3) | — | — | partially |

### Mapping today's exits onto the required terminal states

| Required state | Exists today? | How it would be detected today | Evidence |
|---|---|---|---|
| SUCCESS | yes | `success=True` | R-02/04/08; also R-06/09/13 (should not have been successes) |
| UNRECOVERABLE_INFEASIBILITY | **only for FM-3 / FM-BATCH-CONFLICT / FM-TAG-EMPTY-at-first-slot** | ineligible code | R-10; missing for R-05/06/07/11 |
| NO_USEFUL_RECOVERY_FOUND | as "abort" status inside dropped stats | signature-equal and nothing persisted | R-03/05/11/14 (all after contaminating writes) |
| RECOVERY_LIMIT_REACHED | implicit (loop ends) | history length 3, still failing | R-07 |
| INVALID_RECOVERY_OUTPUT | no distinct state | would appear as "abort" or exception | R-03 (demoted recipe was *accepted*, so it appears as no-progress) |
| DATA_SOURCE_FAILURE | no; raised as exception | HTTP 422/502/504, planner result discarded | R-12 |
| SYSTEM_ERROR | no; raised | HTTP 500 | — |

### Termination conditions the loop needs (definition for Phase 9/10)

- **Before the first LLM call:** a deterministic `diagnose(result, profile, pool, filters)` step that returns either `UNRECOVERABLE_INFEASIBILITY(reason)` or a `GapSpec` (which slot/day/nutrient/macro, what property a candidate must have, which exclusions it must respect, which tags it must carry). No `GapSpec` ⇒ stop, no LLM call, no writes.
- **After each attempt:** a measurable improvement criterion computed from the planner's own artefacts (candidate count for the failing slot, nutrient reachable total, macro window reachability) compared before/after; no improvement ⇒ NO_USEFUL_RECOVERY_FOUND.
- **Accept-before-persist:** a draft enters the *candidate* pool only; it is persisted only if the plan that used it succeeds, and then with provenance. A failed request leaves no residue.
- **Every exit returns the deterministic result plus a typed `RecoveryOutcome{state, attempts, llm_calls, accepted, rejected_reasons, persisted, gap_spec, improvement_trace}`** that survives serialization.
- **Data-source errors** are caught at the boundary and reported as `DATA_SOURCE_FAILURE` with the original planner result intact.

---

## Cross-phase summary against the hypotheses in `EVALUATION_PLAN.md` §14

| Family | Outcome | Supports |
|---|---|---|
| A/B/C NL | numeric fields ~97 %; 15 safety/constraint statements structurally dropped; 14 invented schedule constraints; 7 hard/soft inversions | architectural (schema), not model |
| D diagnosis | 5/6 unrecoverable cases treated as recoverable | **H3** |
| E positive | 3/3 recover | mechanism salvageable |
| H validation | demoted recipe persisted; allergen planned; fabricated time drove HC-3 | **H2** |
| I tagging | LLM tagging 0/6 valid and destroys curated tags; hard-eligibility gate itself is sound | **H4** (write path), H2 (prompt) |
| J mutation | filter bypassed; pool 6 → 64 on fallback; tags lost in 11/15 | **H3 + H4** |
| K/L termination | 4 of 7 required states absent; result lost on exception; history dropped | **H3** |
| F FoodData Central | 11 % wrong-identity resolutions; 2 mapper defects; no provenance | data layer, shared root cause with H4 |

H1 ("sound, just noisy data") is rejected by D, H, I, J and K/L. The evidence supports H2, H3 and H4 jointly, which is the input to the Phase 9 decision.
