# Data — domain models, stores, ingredient resolution and nutrition math

Status: implemented · Code: `src/data_layer/`, `src/nutrition/`, `src/ingestion/`, `src/providers/` · Facts: [generated/data.md](generated/data.md)

## Purpose
Turns stored recipes and ingredient records into gram-normalized, nutrition-bearing recipes the planner can search over, without any I/O during planning. Owns the file-backed stores (recipe pool, meal-prep batches, profile YAML), the committed reference tables, and the ingredient provider abstraction that hides local JSON vs USDA FoodData Central. Every number the planner sees comes from here, never from an LLM.

## Entry points
- `src/api/server.py::build_plan_inputs` — POST /api/v1/plan and /api/v1/plan-from-text: tag filter → resolve → convert.
- `src/cli.py::main` — same flow for the CLI; the api ingredient source switches to USDA.
- `src/planning/converters.py::extract_ingredient_names` / `src/planning/converters.py::convert_recipes` — the pool builders every caller uses.
- `src/api/server.py::nutrition_summary_endpoint` and `src/mcp_server/tools.py::build_provider` — draft nutrition via `src/providers/summary_hybrid_provider.py::SummaryHybridIngredientProvider`.
- `src/api/server.py::build_usda_provider` — USDA provider for LLM validation (see [llm.md](llm.md)).
- `scripts/setup_user_data.py` — creates a MACROVA_DATA_DIR folder.

## How it works
1. **Load recipes.** `src/data_layer/recipe_db.py::RecipeDB` reads the pool; `src/data_layer/recipe_db.py::parse_ingredient` keeps units as authored and leaves grams empty. `src/data_layer/models.py::Recipe.tags` is projected from canonical tags_by_id at load time and never written back.
2. **Resolve up front.** `src/planning/converters.py::extract_ingredient_names` collects sorted unique names (to-taste lines skipped); the provider's resolve_all does all I/O. Local mode is a no-op over `data/reference/ingredient_nutrition.json`. USDA mode resolves each name through `src/ingestion/ingredient_cache.py::CachedIngredientLookup` and fails fast on the first miss with `src/providers/api_provider.py::IngredientResolutionError`.
3. **USDA lookup (cache miss).** `src/ingestion/usda_client.py::USDAClient.search_candidates` → `src/ingestion/ingredient_ranker.py::rank_candidates` → `src/ingestion/usda_client.py::USDAClient.get_food_details` → `src/ingestion/nutrient_mapper.py::NutrientMapper` → `src/ingestion/ingredient_cache.py::check_nutrition_plausibility` (Atwater within 15%, pure-fat only for oil-like names) → write a per-name JSON file under .cache/ingredients (gitignored) with provenance (fdc_id, description, rank confidence, mapper version).
4. **Grams once.** `src/planning/converters.py::convert_recipes` calls `src/nutrition/calculator.py::NutritionCalculator.normalize_ingredient` per line. `src/nutrition/calculator.py::NutritionCalculator.to_grams` order: g → record grams_per_unit (plus scoop_size_g / large_size_g) → oz (28.35) → `src/ingestion/nutrition_scaler.py::BASE_SERVING_WEIGHTS` (large/medium/small eggs, fruit) → the recipe line's own grams_per_unit → else unresolved.
5. **Drop, don't zero.** `src/nutrition/calculator.py::NutritionCalculator.unresolved_ingredient_names` lists unknown names, unconvertible units and non-seasoning "to taste" lines (allow-list `data/reference/to_taste_allowed.json`). Such recipes leave the pool and land in warnings.nutrition; survivors get nutrition scaled from per_100g into `src/data_layer/models.py::NutritionProfile`.
6. **User data vs repo.** `src/data_layer/user_data.py::recipes_path`, `src/data_layer/user_data.py::recipe_tags_path` and `src/data_layer/user_data.py::meal_prep_batches_path` resolve per call: MACROVA_DATA_DIR unset → `data/recipes/recipes.json`, `data/recipes/recipe_tags.json`, data/meal_prep/batches.json (created on first write); set → files in that folder. `src/data_layer/user_data.py::setup_user_data` creates an empty pool plus the shipped tag registry; users import from `data/recipes/recipes.json.example` (read only via `src/data_layer/user_data.py::load_starter_recipes`).
7. **Meal-prep batches.** `src/data_layer/meal_prep.py::MealPrepBatchRepository` validates on create (≥2 servings, no duplicate slot, servings sum ≤ total), derives planned/active from cook_date at read time, and marks batches orphaned when their recipe is deleted. The planner turns active batches into locks.
8. **Profile and targets.** `src/data_layer/user_profile.py::UserProfileLoader` reads YAML (NUTRITION_USER_PROFILE_PATH or config/user_profile.yaml, gitignored; template `config/user_profile.yaml.example`); pins and schedule are written back to that file. `src/data_layer/macro_targets.py::validate_macro_targets` derives carbs and rejects inconsistent targets; `src/data_layer/upper_limits.py::upper_limits_for` and `src/data_layer/upper_limits.py::daily_rdis` read `data/reference/ul_by_demographic.json` / `data/reference/rdi_by_demographic.json`.

## Modules
| Module | Role | Status |
|---|---|---|
| `src/data_layer/models.py` | Domain dataclasses | implemented |
| `src/data_layer/recipe_db.py` | Recipe pool reader, legacy tag projection, save for deletes | implemented |
| `src/data_layer/nutrition_db.py` / `src/data_layer/ingredient_db.py` | Local ingredient table lookup by name or alias | implemented |
| `src/data_layer/user_data.py` | Where user-writable stores live | implemented |
| `src/data_layer/meal_prep.py` | Batch entities and JSON repository | implemented |
| `src/data_layer/user_profile.py` | Profile YAML, pins, PlannerConfigJson → UserProfile | implemented |
| `src/data_layer/macro_targets.py` | Carb derivation, target validation | implemented |
| `src/data_layer/upper_limits.py` | UL/RDI tables, daily UL check | implemented |
| `src/nutrition/calculator.py` | Grams conversion, nutrition scaling, to-taste policy | implemented |
| `src/providers/` | Local / USDA / summary-hybrid providers | implemented |
| `src/ingestion/ingredient_cache.py` | Disk cache, USDA lookup orchestration, plausibility gate | implemented |
| `src/ingestion/usda_client.py` | FDC HTTP client | implemented (legacy single-best lookup unused) |
| `src/ingestion/ingredient_ranker.py` | Deterministic candidate scoring | implemented |
| `src/ingestion/nutrient_mapper.py` | FDC nutrient ids → internal fields | implemented |
| `src/ingestion/ingredient_normalizer.py` / `src/ingestion/ingredient_validator.py` | Name canonicalization; unit/quantity checks for LLM drafts | implemented |
| `src/ingestion/nutrition_scaler.py` | Named count-unit weights only | implemented |

## Key types
- `src/data_layer/models.py::Recipe` — stored recipe; tags is a legacy projection, provenance is optional.
- `src/data_layer/models.py::Ingredient` — authored quantity/unit plus normalized grams and an optional per-line grams_per_unit.
- `src/data_layer/models.py::NutritionProfile` / `src/data_layer/models.py::MicronutrientProfile` — macros and 25 micronutrient fields.
- `src/data_layer/models.py::UserProfile` — targets, exclusions, schedule, demographic.
- `src/providers/ingredient_provider.py::IngredientDataProvider` — resolve_all + get_ingredient_info contract (per_100g dict).
- `src/ingestion/ingredient_cache.py::CacheEntry` — cached USDA food with provenance.
- `src/ingestion/ingredient_ranker.py::RankedResult` — selected candidate, confidence, margin, reasons.
- `src/data_layer/meal_prep.py::MealPrepBatch` — recipe, servings, slot assignments, status.
- `src/data_layer/exceptions.py::IngredientNotFoundError` — the single "cannot compute" signal; message carries the reason.

## Invariants
1. No network during planning: all lookups happen in resolve_all; `src/providers/api_provider.py::APIIngredientProvider.get_ingredient_info` raises on any name not pre-resolved. Guard: `tests/test_api_provider.py`.
2. No silent zeros or density guesses: unknown units raise in `src/nutrition/calculator.py::NutritionCalculator.to_grams`; `src/planning/converters.py::convert_recipes` drops the recipe with a logged reason. Guards: `tests/test_volume_unit_api_path.py`, `tests/test_ingredient_nutrition_reference.py`, `tests/test_converters.py`.
3. "To taste" is 0 g only for allow-listed seasonings: `src/nutrition/calculator.py::is_to_taste_allowed`. Guard: `tests/test_to_taste_allowed.py`.
4. USDA results are cached only after the plausibility gate: `src/ingestion/ingredient_cache.py::CachedIngredientLookup.lookup`. Guard: `tests/test_ingredient_nutrition_reference.py`.
5. User-writable paths come only from `src/data_layer/user_data.py`; a regex test bans the literal paths elsewhere in src/. Guard: `tests/test_user_data.py`; `tests/conftest.py` fails the session if a test changes the committed recipe or tag store.
6. Pool building is deterministic: sorted names, recipes sorted by id. Guard: `tests/test_converters.py`.

## Depends on / used by
Depends on `src/llm/tag_repository.py` (tags_by_id for the legacy tags projection) and `src/llm/schemas.py` (PlannerConfigJson, tag shapes). Used by `src/planning/` (converters, allergens, carb scaling read `data/reference/allergen_classes.json` and `data/reference/scalable_carb_sources.json`), `src/api/`, `src/cli.py`, `src/mcp_server/`, and the LLM validator. Full import graph: [generated/index.md](generated/index.md).

## Known gaps and traps
- USDA mode is all-or-nothing per request: one unknown name aborts the plan (CLI exit 3) instead of dropping one recipe. USDA records carry no grams_per_unit, so cup/tbsp/ml lines are unresolved there.
- `src/api/server.py` resolves the recipe and tag paths once at import; setting MACROVA_DATA_DIR after import has no effect on the API.
- Three writers touch the recipe file: `src/api/recipe_sync.py::atomic_upsert_recipes_by_id` (sync/create/import), `src/llm/repository.py::append_validated_recipes` (LLM), and `src/data_layer/recipe_db.py::RecipeDB.save` (delete). Change the stored shape in all three.
- The profile YAML and pins are not under MACROVA_DATA_DIR. Without the env var, the default batch file appears as an untracked file in the repo.
- `src/data_layer/models.py::Recipe.is_meal_prep_capable` reads the legacy tags projection. It is correct only because `src/data_layer/recipe_db.py::RecipeDB` builds that projection from tags_by_id.
- `src/ingestion/usda_client.py::USDAClient.lookup` (single best match) is only used in tests. The live path is search_candidates → ranker → get_food_details. The summary-hybrid docstring mentions custom_ingredients.json, but callers pass the reference table.
