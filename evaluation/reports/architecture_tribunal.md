# Macrova architecture tribunal

**Posture:** adversarial reviewer for a technical software/AI competition. The goal was to invalidate the central claims, not to fix them. No solutions are proposed here.

**Snapshot reviewed:** branch `140-dollar-sprint`, commit `ee58fcc`, working tree as described in `evaluation/initial_state.md`. All experiments were run on 2026-09-17 with `.venv` Python 3.12.13. Nothing in `src/`, `data/`, or `config/` was modified. Two read-only USDA API calls were made to verify nutrient IDs.

**Method:** read every planner phase, the LLM pipeline, the ingestion/provider layer, the CLI and API entry points, the spec and rules docs, and the test layout. Then ran the planner on the committed example data, on the local data with the USDA cache, on synthetic pools, and brute-forced feasibility of the real pool to compare against what the search reports.

---

## 1. Verdict

The project's central promise is "accurate nutrition calculations and meal balancing above all else" (README, product docs). Under scrutiny that promise does not hold on this snapshot. The planner algorithm is internally consistent and deterministic, but the numbers it plans over are largely wrong, the safety constraints it advertises are not wired into the entry points, and the search fails on a real three-day instance that a brute-force check proves feasible.

The test suite (1074 passing) does not detect any of this because it never pushes real ingredient data through the planner to a realistic success, and one test explicitly enshrines the behaviour that produces silent zeros.

---

## 2. Central claims versus evidence

| Claim (source) | Status | Evidence section |
| --- | --- | --- |
| "Accurate nutrition calculations" (README roadmap, checked as done) | Refuted | A1 to A6 |
| "Daily upper limits are enforced per-day, never averaged" (AGENTS.md) | Refuted; ULs are never passed to the planner from CLI or API | B1 |
| "Hard exclusion of allergens" (spec HC-1) | Weak; exact string match only, `peanuts` does not exclude `peanut butter` | B2 |
| "Deterministic backtracking search with structured failure reporting" (AGENTS.md, spec) | Deterministic, yes. Reports FM-5 on a feasible 3-day instance; reports FM-4 for an empty pool | C1, B4 |
| "Recipe generation is USDA-validated; only validated recipes persist" (AGENTS.md, roadmap) | Hollow; validation is "the name resolves to some USDA record". Oat oil passed as oats | D1, D2 |
| "Natural-language config maps text into explicit planner config" (AGENTS.md) | Partially; the config schema has no allergy, dislike, or micronutrient fields, so those statements are dropped | D5 |
| "Tag filtering falls back to full pool if the filter result is empty" (architecture.json) | Refuted; a cuisine filter on this repo yields zero recipes | B4 |
| "No network calls during planning; fail-fast resolution" (AGENTS.md) | True for the API provider; the local provider silently skips unknown ingredients instead of failing | A1 |
| "1074 tests, no network" (baseline) | True but not probative; see F | F1 to F3 |

---

## 3. Findings

### A. Nutrition data pipeline (the foundation)

**A1. The local ingredient database covers almost none of the recipes, and missing ingredients are silently dropped.**
`data/ingredients/custom_ingredients.json.example` has 7 entries. The committed example recipes reference 55 distinct ingredient names; 50 are absent from the local DB. The local file on this machine has the same 7 entries against 65 names. `NutritionCalculator.calculate_recipe_nutrition` catches `IngredientNotFoundError` and `continue`s (`src/nutrition/calculator.py`, comment: "In MVP, we'll skip missing ingredients"). `LocalIngredientProvider.resolve_all` is a no-op, so the "fail-fast resolution" contract does not apply to the default provider. Result on the default CLI run: every recipe planned with zero or near-zero nutrition, and the FM-4 report lists `achieved: 0.0` for all 25 tracked nutrients.

| Data set | Ingredient names needed | Missing from local DB |
| --- | --- | --- |
| `recipes.json.example` | 55 | 50 |
| local `recipes.json` (32 recipes) | 65 | 59 |

The baseline report recorded this outcome as "planning reports infeasibility". It is not infeasibility. It is absence of data, misreported as a nutrition failure.

**A2. USDA name resolution is deterministic and frequently wrong.**
`CachedIngredientLookup` asks USDA for the top 8 relevance-ranked candidates across all data types and re-ranks them with string heuristics (`ingredient_ranker.py`). The cache on this machine shows what that produces:

| Recipe ingredient name | Resolved USDA record |
| --- | --- |
| `eggs` | Bread, egg |
| `oats` | Oil, oat |
| `milk 1% fat lowfat` | Cheese, cottage, lowfat, 1% milkfat |
| `bell pepper` | TACO BELL, Nachos |
| `cherry tomatoes` | Cherries, raw |
| `banana` | Bananas, dehydrated, or banana powder |
| `chicken breast` | Chicken breast, roll, oven-roasted (deli roll) |
| `tortillas corn` | Tortillas, flour, shelf stable |
| `acai berry` | Beverages, Acai berry drink, fortified |
| `milk` | Branded "MILK" (label data) |
| `feta cheese reduced fat` | Cheese, feta (full fat) |
| `hamburger or beef 95%` | Beef, ground, 93% lean |

Consequences on the local recipe pool: "Mexican Egg Skillet" is 260 g of egg bread; "Oatmeal with Fruits" is 100 g of oat oil plus dehydrated banana powder at 1474 kcal and 107 g fat; "Power Shake" is 400 g of cottage cheese. The 7-entry local DB was evidently populated from the same resolver: its `chicken breast` (134 kcal, 14.6 g protein per 100 g) matches the deli roll, not chicken breast.

**A3. The USDA nutrient mapping table has three errors that bias tracked nutrients.**
Verified against raw USDA records fetched during this review.

- Vitamin D IDs are swapped. `nutrient_mapper.py` labels 1110 as micrograms and multiplies by 40, and labels 1114 as IU with no conversion. USDA reports 1110 as IU and 1114 as micrograms. Foods carrying both are overstated about 40x. Egg yolk: USDA 218 IU per 100 g, cache holds 8725 IU per 100 g. The single-day plan below "meets" its vitamin D floor with 5287 IU, which is above the 4000 IU upper limit that is not enforced (B1).
- Foundation-type foods have no nutrient 1008 (Energy). Their energy is under 2047/2048, which the mapper ignores. Every Foundation entry in the cache has 0 kcal: tomato, sweet potato, kiwi, spaghetti squash, shiitake. Macros and micros for those foods are non-zero, so a recipe can carry protein and carbs with zero calories.
- Omega-3 is mapped from nutrient 1272 only, which is DHA. ALA (1404) and EPA (1278) are ignored. Chia seeds, with 17.8 g ALA per 100 g in USDA, show `omega_3_g = 0.0` in the cache. The mapper comment calls 1272 "total polyunsaturated (omega-3 proxy)", which is also wrong. The omega-3 daily floor of 1.6 g is effectively unreachable except through fatty fish.

**A4. The ingredient cache is unversioned and internally inconsistent.**
The cached salmon entry holds 761 IU vitamin D, which is consistent with a correct mapping. The cached egg yolk entry holds 8725 IU, which is consistent with the current swapped mapping. `IngredientCache` stores no mapper or schema version and the module docstring states "No silent invalidation or auto-refresh". Entries produced under different code versions coexist and are all treated as authoritative.

**A5. Volume units silently fall through as grams, and two contradictory conversion layers exist.**
`NutritionCalculator._convert_quantity_to_grams` returns the raw quantity for any unit it does not recognise. The committed example recipes use `cup`, `tbsp`, and `cup, whole pieces`. Measured: 1 cup tomato is computed as 1 g; 2 cups jasmine rice as 2 g; 4 tbsp carrots as 4 g; 1 kg as 1 g. A strict `NutritionScaler` exists in `src/ingestion/nutrition_scaler.py` that raises on volume units, with a docstring promising "no silent fallbacks", but nothing on the planning path uses it. Millilitres are treated as grams regardless of density (oil, honey).

**A6. Local DB entries carry the upstream errors.**
`tomato` and `mushrooms` in the local DB have 0 kcal with non-zero macros. `tomato` reports 2.27 mg iron per 100 g (USDA raw tomato is about 0.27 mg).

### B. Constraint enforcement

**B1. Upper limits are never enforced in any entry point, and the demographic is hard-coded.**
`src/cli.py` builds `resolved_ul` and then calls `plan_meals(planning_profile, recipe_pool, args.days)` without it. `src/api/server.py` never imports the UL loader. `converters.convert_profile` sets `demographic="adult_male"` unconditionally and the CLI passes `demographic="adult_male"` regardless of the YAML value. The HC-4/FC-3 code paths are correct but unreachable in production. Evidence: the successful single-day plan on this machine totals 5287 IU vitamin D against a 4000 IU UL and is reported as `plan_status: success`.

**B2. Allergen exclusion is an exact normalised-string match.**
`check_hc1_excluded_ingredients` compares `name.lower().strip()` for equality. With `excluded_ingredients = ["peanuts", "shellfish", "egg"]`, a recipe containing `peanut butter`, `shrimp`, and `eggs` passes HC-1 (verified). The legacy `RecipeScorer` used substring matching; the live planner does not. Recipe ingredient names are free text from users and LLMs, so exact matching is the weakest possible allergen guard.

**B3. Single-day plans skip micronutrient floors and do not warn when below them.**
For D = 1 the search returns TC-4 before weekly validation. `result_from_success` only emits the soft-deficit warning for nutrients between the tau floor and the full RDI. In the single-day plan above, omega-3 achieved 0.1 g against a 1.28 g floor and omega-6 achieved 9.0 g against 13.6 g; neither appears in warnings. A user asking for one day gets "success" with hard floors unmet and unmentioned.

**B4. A tag preference empties the pool and the failure is misreported.**
`recipe_tags.json` has an empty `tags_by_id`. `filter_recipe_ids_by_preferences` returns `[]` when no recipe has tags, and `apply_tag_filtering` returns `[]` rather than the full pool. Running `--cuisine mexican` logs `output_recipe_count: 0` and the planner then reports FM-4 "Weekly micronutrient targets are infeasible" with 25 structural deficits, for a one-day plan. The real cause (zero candidates) is not in the report. This also contradicts spec TC-4, which says weekly validation is not performed for D = 1; the structural pre-check fires anyway.

**B5. FC-4 assumes every remaining day has the current day's slot count.**
`check_fc4_cross_day_rdi` multiplies `days_left` by `max_daily_achievable(n, slot_count_of_current_day)`. With per-day schedules that differ in slot count (which the spec explicitly allows), the bound can be too tight and prune feasible plans, violating the spec's "feasibility checks are conservative".

**B6. The UL reference table applies supplement-only limits to food totals.**
`ul_by_demographic.json` sets magnesium at 350 mg per day. The IOM 350 mg figure is for supplemental magnesium; dietary magnesium has no UL. The example profile targets 400 mg per day. Under strict tau the RDI floor exceeds the UL, so the problem would be infeasible by construction if ULs were wired. The same supplement-only caveat applies to the niacin, folate, and vitamin E rows.

**B7. Sodium is modelled as a floor.**
The profile lists `sodium_mg: 1500` under micronutrient goals and the planner treats every goal as a minimum to reach (tau x RDI x D). The planner will backtrack away from low-sodium days. The only upper signal is an advisory at 200 percent, which the single-day plan already exceeded.

### C. Search feasibility and scalability

**C1. The search reports FM-5 on a real three-day instance that is provably feasible.**
Using the local 32 recipes with the USDA cache and the committed profile (tau 0.8, three level-4 slots per day):

| Horizon | Planner result | Wall time | Attempts | Backtracks |
| --- | --- | --- | --- | --- |
| 1 day | TC-4 success | under 2 s | 3 | 0 |
| 2 days | TC-1 success | 1.8 s | n/a | n/a |
| 3 days | TC-3 / FM-5 (attempt limit) | 15.3 s | 50000 | 38071 |

A brute-force check in this review enumerated all 4960 three-recipe days, found 79 that pass daily validation, and found sequences of those days that satisfy HC-8 and every weekly floor for both D = 2 and D = 3. A valid three-day plan exists. The planner does not find it within its budget and cannot say whether one exists (`search_exhaustive: false`). The "partial" output it returns repeats day 1 as day 3 and lists no deficient nutrients, so the user cannot tell what went wrong.

**C2. Synthetic pools show the same pathology.**
With eight tracked micronutrients and random but realistic recipes, pools of 30 and 60 recipes over 7 days hit the 50000-attempt limit in about 8 s each. A pool of 120 recipes succeeds in 28 attempts. Without micronutrient targets, every configuration succeeds in under 40 attempts. The chronological backtracking design, with FC-4 evaluated only at day boundaries and candidate lists scored once per day, thrashes inside later days while the binding constraint is a weekly aggregate. There is no proof of infeasibility, no restart, and no bound tied to problem size.

**C3. The daily tolerance design makes small pools structurally brittle.**
Daily validation requires calories, protein, and carbs each within plus or minus 10 percent and fat inside a range, over three discrete recipes with no same-day repeats. Only 79 of 4960 combinations of the local pool pass. Carbs are a derived quantity (from calories, protein, and the median of the fat range) yet carry their own 10 percent band, so the three bands are not independent. The README's three-slot example day (2263 kcal against a 2400 target) would fail its own protein band at 166 g against 150 g.

### D. LLM reliability

**D1. "USDA-validated" means only that a name resolves to some record.**
`validate_recipe_draft` checks unit, quantity, provider resolution, and that nutrition computation does not raise. There is no plausibility check on the resolved record or the resulting macros. "Oatmeal with Fruits" was validated and persisted five times with oat oil as its base (1474 kcal, 107 g fat per serving).

**D2. Unresolvable ingredients are silently demoted to "to taste" and the recipe is persisted anyway.**
`validate_recipe_draft` catches `IngredientResolutionError`, flips the ingredient to `to taste`, and continues. `data/recipes/recipes.json` contains `llm_59834f6218eb974e` "Oatmeal with Fruits" whose `rolled oats` and `water` are `to taste`; it plans as a 453 kcal banana-and-honey dish with no oats. The AGENTS.md rule "do not persist generated recipes unless nutrition validation and ingredient resolution pass" is not what the code does.

**D3. Cooking time for LLM recipes is fabricated.**
`_estimate_cooking_time_minutes` returns 5 x number of instruction lines, clamped to 120. That fabricated number then drives HC-3, a hard constraint. Every LLM recipe in the pool has a 20 or 25 minute cooking time regardless of content.

**D4. Duplicate generation is not controlled.**
The pool contains 14 `llm_*` recipes for three dishes (five "Oatmeal with Fruits", five "Grilled Chicken with Vegetables", three "Quinoa Salad") that differ only in quantities or water versus milk. Fingerprint dedupe is exact-match on ingredient quantities. Sprint ticket AI-5 (fuzzy duplicate detection) is still `todo`.

**D5. Natural-language planning drops allergies, dislikes, and micronutrient goals.**
`PlannerConfigJson` has fields for days, meals per day, calorie and protein targets, cuisine, budget, and optional schedule. `user_profile_from_planner_config` sets `allergies=[]`, `disliked_foods=[]`, `daily_micronutrient_targets=None`. A prompt containing "I am allergic to peanuts" is parsed by the LLM into a schema that cannot represent it, validates cleanly, and produces a plan with no exclusion. Cuisine strings are mapped into `liked_foods` where they match nothing. The spec's "validated" guarantee here is purely syntactic.

**D6. Ingredient matching trusts the model's self-reported confidence.**
`validate_matches` rejects below a 0.7 confidence that the LLM itself emitted, then accepts anything the provider resolves. Given A2, "resolves" is a low bar (`bell pepper` resolves to nachos).

**D7. Assisted planning mutates the recipe store during a plan request.**
`plan_with_llm_feedback` appends validated recipes to `recipes.json` as a side effect of `/api/v1/plan` and the CLI. The feedback cache is keyed on a hash of the failure report, so any change in report shape or profile invalidates "deterministic" replay; `assisted_cached` raises on a cold cache. The persisted duplicates in D4 are the visible residue of this loop.

**D8. The tag lifecycle contract is untested against real data.**
`tags_by_id` is empty, `hard_eligible_tag_slugs` is only populated on the API path, and LLM tags with `tag_metadata` lifecycle are never produced by `tag_recipes` (it emits the four enum fields only). The approved/proposed gating exists in code but has no data flowing through it.

### E. Domain modelling

- Vitamin D is a hard weekly floor of 600 IU per day, while the product doc says vitamin D "does not matter" and comes from sun or supplements. With correct mapping the floor is close to unreachable from food; with the current mapping it is met by egg bread and a branded milk label.
- Omega-3 is a hard floor computed from DHA only (A3).
- Sodium is a floor (B7).
- ULs use supplement-only figures (B6) and the demographic is ignored (B1).
- Carbs are derived from the fat-range median and then constrained independently (C3).
- "To taste" exclusion is by unit string; a recipe can hide its main ingredient as "to taste" (D2).

### F. Evaluation validity

**F1. The test suite never exercises realistic nutrition through the planner.**
Planner tests build `PlanningRecipe` objects with hand-set nutrition. `tests/conftest.py` copies the example data files when absent, and those files produce all-zero nutrition (A1), so any API or CLI test that ran the example data to a real success would fail; none does. `tests/test_nutrition_calculator.py::test_calculate_recipe_missing_ingredient` asserts the silent-skip behaviour as correct. No test checks that a resolved USDA description resembles the requested ingredient, that Foundation foods have energy, or that vitamin D units are right.

**F2. The baseline misdiagnosed the default failure.**
`evaluation/initial_state.md` treats the default FM-4 as a known infeasibility to be preserved. It is a data-coverage failure (A1). Any sprint metric built on "reduce FM-4" will measure the wrong thing.

**F3. Dead and parallel code inflate confidence.**
`src/scoring/recipe_scorer.py` (767 lines, its own weight scheme, allergen substring logic, a "micronutrient" score that is really macro diversity) is not called by any production path but has a test file. `NutritionScaler` (strict) and `NutritionCalculator` (lenient) implement contradictory unit semantics. Two tie-break specifications exist: the spec's five-rule cascade and `phase5_ordering.ordering_key`'s three-key tuple plus seeded RNG.

**F4. CI does not run what AGENTS.md requires.**
`.github/workflows/ci.yml` uses Python 3.11 and bare `python -m pytest`; AGENTS.md mandates 3.12 and `scripts/run_pytest.py`. The README badge says 3.10+. Nothing in CI runs the CLI end to end.

**F5. Output is content-deterministic but not byte-deterministic.**
Sorted-JSON hashes of the same plan are identical across `PYTHONHASHSEED` 0, 1, and 2. Raw JSON differs because micronutrient dicts are rebuilt from Python sets. Any snapshot comparison on raw output will flake.

**F6. Failure signalling at the CLI boundary is inconsistent.**
On failure the CLI exits 0, prints "Meal plan generated with warnings" to stderr, and emits `plan_status: failed` in JSON. Scripts cannot detect failure by exit code.

### G. Documentation and process drift

- AGENTS.md and `docs/README.md` point to `docs/planner/mealplan-specification.md`, which does not exist; the file is `mealplan-specification-v3.md`. Ten source files cite `MEALPLAN_SPECIFICATION_v1.md`.
- `.cursor/architecture.json` says meal-prep routes and the tag file are missing; both exist. It says tag filtering falls back to the full pool; it does not (B4).
- README marks "Accurate nutrition calculations and meal balancing" as done.
- The spec says FM-4 is a weekly failure and TC-4 skips weekly validation for D = 1; the implementation emits FM-4 for D = 1 (B4).
- `USAGE.md` says the planner "will still generate a plan" when targets are unmet; the planner returns failure or best-effort partials instead.
- The frontend serialises LLM and USDA API keys inside the user profile model (`frontend/lib/models/user_profile.dart` `toJson`), which is persisted by the storage service.

---

## 4. Assumptions Macrova needs to be true

Every one of these must hold for the system to plan reliably. Items marked with an asterisk are currently false on this snapshot.

1. Every ingredient name in the recipe pool resolves to nutrition data, or planning refuses to proceed. *
2. A resolved USDA record is the food the recipe author meant. *
3. USDA nutrient IDs and units are mapped correctly, for all data types (SR Legacy, Foundation, Survey, Branded). *
4. Branded records carry the micronutrients the planner tracks. *
5. Recipe quantities are in mass units, or volume units are converted with a density. *
6. Cached nutrition entries were produced by the current mapping code. *
7. The local ingredient DB entries are correct per 100 g. *
8. Upper limits are loaded, matched to the user's demographic, and passed into the search. *
9. UL values are appropriate for dietary intake rather than supplements. *
10. Excluded-ingredient matching catches the forms allergens actually take in ingredient names. *
11. Micronutrient goals are true minimums (sodium is not). *
12. Tracked nutrient targets are reachable from food in the pool (vitamin D, omega-3). *
13. The recipe pool is large and varied enough that plus or minus 10 percent on three macros plus a fat range admits many valid days. *
14. Chronological backtracking with a fixed 50000-attempt cap finds a valid multi-day plan when one exists. *
15. FC-4's bound is conservative for schedules whose slot counts vary by day. *
16. Single-day users do not need micronutrient floors checked or reported. *
17. LLM recipe validation rejects recipes whose resolved ingredients are implausible. *
18. LLM recipes with unresolvable ingredients are rejected rather than degraded. *
19. LLM recipe cooking times reflect the recipe. *
20. Near-duplicate generated recipes are detected. *
21. The natural-language schema can represent every safety-relevant statement a user makes (allergies, exclusions). *
22. LLM self-reported confidence is calibrated enough to gate ingredient matches.
23. The LLM feedback loop's writes to `recipes.json` are acceptable side effects of a plan request.
24. Tag data exists and flows through the approved/proposed lifecycle. *
25. The tag filter falls back rather than emptying the pool. *
26. Tests exercise real data end to end and would catch silent zeros. *
27. CI runs the canonical commands on the pinned interpreter. *
28. Output is byte-stable for snapshot comparison. *
29. Documentation paths and status notes match the code. *

---

## 5. Reproduction commands

All commands run from the repository root inside `.venv`.

Default run (all-zero nutrition reported as FM-4):

```bash
.venv/bin/python plan_meals.py --output json
```

Local DB coverage and per-recipe zeros:

```bash
.venv/bin/python -c "from src.data_layer.recipe_db import RecipeDB; from src.data_layer.nutrition_db import NutritionDB; from src.providers.local_provider import LocalIngredientProvider; from src.planning.converters import extract_ingredient_names; r=RecipeDB('data/recipes/recipes.json.example').get_all_recipes(); p=LocalIngredientProvider(NutritionDB('data/ingredients/custom_ingredients.json.example')); n=extract_ingredient_names(r); print(len(n), sum(p.get_ingredient_info(x) is None for x in n))"
```

USDA resolution and mapping errors (uses the on-disk cache, no network):

```bash
.venv/bin/python -c "import json; [print(f, json.load(open('.cache/ingredients/'+f))['description']) for f in ['eggs.json','oats.json','milk_1_fat_lowfat.json','bell_pepper.json','cherry_tomatoes.json']]; e=json.load(open('.cache/ingredients/chia_seeds.json')); print('chia omega3', e['nutrition']['micronutrients']['omega_3_g']); t=json.load(open('.cache/ingredients/tomato.json')); print('tomato kcal', t['nutrition']['calories'], t['data_type'])"
```

Unit fallthrough and allergen match:

```bash
.venv/bin/python -c "from src.data_layer.models import Ingredient; from src.data_layer.nutrition_db import NutritionDB; from src.providers.local_provider import LocalIngredientProvider; from src.nutrition.calculator import NutritionCalculator; c=NutritionCalculator(LocalIngredientProvider(NutritionDB('data/ingredients/custom_ingredients.json'))); print('1 cup tomato carbs g:', c.calculate_ingredient_nutrition(Ingredient('tomato',1,'cup')).carbs_g)"
```

UL not wired (grep shows `resolved_ul` computed in `src/cli.py` but not passed; absent from `src/api/server.py`):

```bash
grep -n "resolved_ul\|plan_meals(" src/cli.py src/api/server.py
```

Real-data horizon results (cache-backed, no network needed once cached):

```bash
.venv/bin/python plan_meals.py --ingredient-source api --days 1 --output json
.venv/bin/python plan_meals.py --ingredient-source api --days 3 --output json
```

Empty pool misreported as FM-4:

```bash
.venv/bin/python plan_meals.py --ingredient-source api --days 1 --cuisine mexican --output json
```

Hash-seed output drift:

```bash
for s in 0 1; do PYTHONHASHSEED=$s .venv/bin/python plan_meals.py --ingredient-source api --days 1 --output json 2>/dev/null | shasum; done
```
