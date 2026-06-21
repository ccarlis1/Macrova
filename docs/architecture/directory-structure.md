# Directory Structure

Module map for the Macrova (`nutrition-agent`) repository. When this doc conflicts with `src/`, trust the source.

```
nutrition-agent/
├── README.md, AGENTS.md, CLAUDE.md
├── QUICK_START.md, USAGE.md
├── plan_meals.py              # CLI entry shim
├── requirements.txt, pytest.ini
├── .env.example, .python-version
│
├── config/
│   └── user_profile.yaml      # User goals, schedule, preferences (copy from .example)
│
├── data/
│   ├── ingredients/           # Local ingredient DB (copy from .example)
│   ├── recipes/               # recipes.json, recipe_tags.json (copy from .example)
│   └── reference/             # Upper-limit and reference nutrition data
│
├── docs/                      # See docs/README.md for navigation
│   ├── architecture/
│   ├── planner/
│   ├── tagging/, llm/, testing/, product/, roadmap/, agents/
│   ├── sprints/               # Per-sprint task stubs (e.g. sprint1/)
│   └── archive/               # Historical sprint plans and derived summaries
│
├── frontend/                  # Flutter app (provider state management)
│
├── openapi/
│   └── openapi.json           # Committed API snapshot
│
├── scripts/
│   ├── run_pytest.py          # Canonical test runner
│   ├── run_export_openapi.py  # OpenAPI export wrapper
│   ├── export_openapi.py
│   ├── _venv.py
│   ├── benchmark_meal_plan_search.py
│   ├── export_planner_debug_artifacts.py
│   ├── migrate_recipes_tags.py
│   ├── migrate_recipes_time_tags.py
│   ├── load_ingredients_by_id.py
│   └── export_flutter_cached_ingredients_bundle.py
│
├── src/
│   ├── cli.py                 # CLI entrypoint
│   ├── api/
│   │   ├── server.py          # FastAPI app (/api/v1)
│   │   ├── recipe_sync.py
│   │   ├── tag_routes.py
│   │   ├── meal_prep_routes.py
│   │   └── error_mapping.py
│   ├── config/
│   │   └── llm_settings.py
│   ├── data_layer/
│   │   ├── models.py
│   │   ├── recipe_db.py, ingredient_db.py, nutrition_db.py
│   │   ├── user_profile.py
│   │   ├── meal_prep.py
│   │   └── upper_limits.py
│   ├── ingestion/
│   │   ├── ingredient_parser.py, ingredient_normalizer.py, ingredient_validator.py
│   │   ├── usda_client.py, ingredient_cache.py
│   │   ├── nutrient_mapper.py, nutrition_profile_builder.py
│   │   ├── recipe_retriever.py
│   │   └── ...
│   ├── llm/                   # Optional LLM assistance (validated before use)
│   │   ├── client.py, schemas.py, pipeline.py
│   │   ├── recipe_generator.py, recipe_validator.py, recipe_tagger.py
│   │   ├── ingredient_matcher.py, constraint_parser.py, planner_assistant.py
│   │   ├── tag_repository.py, tag_filtering_service.py
│   │   └── ...
│   ├── models/
│   │   ├── schedule.py
│   │   └── legacy_schedule_migration.py
│   ├── nutrition/
│   │   ├── calculator.py
│   │   └── aggregator.py
│   ├── planning/              # Deterministic phase-based meal planner
│   │   ├── planner.py         # Public API: plan_meals
│   │   ├── orchestrator.py    # Optional LLM feedback wrapper
│   │   ├── converters.py
│   │   ├── phase0_models.py … phase7_search.py
│   │   ├── phase9_carb_scaling.py
│   │   ├── phase10_reporting.py
│   │   ├── micronutrient_policy.py
│   │   └── slot_attributes.py
│   ├── providers/
│   │   ├── ingredient_provider.py
│   │   ├── local_provider.py, api_provider.py
│   │   └── summary_hybrid_provider.py
│   ├── scoring/
│   │   └── recipe_scorer.py
│   └── output/
│       └── formatters.py
│
└── tests/
    ├── conftest.py
    ├── api/                   # API contract tests
    ├── integration/
    ├── planning/
    ├── test_phase0_meal_plan_foundation.py … test_phase7_search.py
    ├── test_llm_*.py
    └── fixtures/
```

## Layer responsibilities

### `src/planning/`

Phase-based deterministic planner. Public entry: `planner.plan_meals`. Phases 0–7 implement models, state, hard constraints, feasibility, scoring, ordering, candidates, and backtracking search. Phase 9 handles carb scaling; phase 10 builds `MealPlanResult` and reporting.

### `src/llm/`

Optional assistants around the planner — recipe generation, tagging, ingredient matching, NL config parsing, planner feedback. Outputs are schema-validated and USDA-backed before persistence. Never called from inside `phase7_search`.

### `src/api/`

FastAPI REST surface under `/api/v1` for planning, recipes, tags, meal-prep, ingredients, and LLM status.

### `frontend/`

Flutter UI: Profile, Ingredient Hub, Recipe Builder, Recipe Library, Planner Config, Meal Plan View, Agent pane. See `docs/usage/flutter-setup.md`.

### `docs/`

Role-based documentation. Canonical planner spec: `docs/planner/mealplan-specification.md`. Agent instructions: root `AGENTS.md`.
