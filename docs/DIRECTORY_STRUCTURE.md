# Directory Structure

```
nutrition-agent/
├── README.md
├── knowledge.md
├── ARCHITECTURE.md
├── DIRECTORY_STRUCTURE.md
├── IMPLEMENTATION_PLAN.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── config/
│   ├── __init__.py
│   ├── user_profile.yaml          # User preferences, goals, constraints
│   ├── nutrition_goals.yaml       # Macro/micro targets, RDI values
│   └── model_config.yaml          # LLM settings, embedding config
│
├── data/
│   ├── __init__.py
│   ├── ingredients/               # Ingredient databases
│   │   ├── usda_ingredients.json
│   │   └── custom_ingredients.json
│   ├── recipes/                   # Recipe databases
│   │   ├── recipes.json
│   │   └── recipe_embeddings.pkl  # Pre-computed embeddings
│   └── nutrition/                 # Nutrition databases
│       └── nutrition_db.json
│
├── src/
│   ├── __init__.py
│   │
│   ├── data_layer/
│   │   ├── __init__.py
│   │   ├── ingredient_db.py       # Ingredient database interface
│   │   ├── recipe_db.py           # Recipe database interface
│   │   ├── nutrition_db.py        # Nutrition database interface
│   │   └── user_profile.py        # User profile management
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── ingredient_parser.py   # Parse and normalize ingredients
│   │   ├── recipe_retriever.py    # Fetch recipes (embedding/keyword)
│   │   └── nutrition_fetcher.py   # Get nutrition data
│   │
│   ├── nutrition/
│   │   ├── __init__.py
│   │   ├── calculator.py          # Calculate nutrition for recipes/meals
│   │   ├── aggregator.py          # Daily/weekly aggregation
│   │   ├── macro_allocator.py     # Macro distribution logic
│   │   └── rdi_validator.py       # Validate against RDIs
│   │
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── recipe_scorer.py       # Score recipes
│   │   ├── llm_reasoner.py        # LLM-based reasoning
│   │   └── constraint_checker.py  # Validate constraints
│   │
│   ├── planning/
│   │   ├── __init__.py
│   │   ├── meal_planner.py        # Main orchestration
│   │   ├── schedule_handler.py    # Process time constraints
│   │   ├── satiety_calculator.py  # Satiety distribution
│   │   └── meal_prep_integrator.py # Meal prep support (future)
│   │
│   ├── output/
│   │   ├── __init__.py
│   │   ├── formatter.py           # Format meals
│   │   ├── structured_output.py   # Generate JSON output
│   │   └── report_generator.py  # Human-readable reports
│   │
│   └── utils/
│       ├── __init__.py
│       ├── embeddings.py          # Embedding utilities
│       └── validators.py          # Input validation
│
├── tests/
│   ├── __init__.py
│   ├── test_ingredient_parser.py
│   ├── test_nutrition_calculator.py
│   ├── test_recipe_scorer.py
│   ├── test_meal_planner.py
│   └── fixtures/
│       ├── sample_recipes.json
│       └── sample_nutrition.json
│
├── scripts/
│   ├── setup_data.py              # Initialize databases
│   ├── generate_embeddings.py     # Pre-compute recipe embeddings
│   └── update_nutrition_db.py     # Update nutrition database
│
└── examples/
    ├── example_usage.py
    └── sample_output.json
```

## Directory Explanations

### `config/`
- YAML files for user preferences, nutrition goals, and model configuration
- Easy to edit without code changes

### `data/`
- All data files (ingredients, recipes, nutrition)
- JSON format for easy inspection and updates
- Pre-computed embeddings for performance

### `src/`
- Main source code organized by layer
- Each module has clear responsibilities
- Easy to test and extend

### `tests/`
- Unit tests for each module
- Fixtures for test data

### `scripts/`
- Utility scripts for setup and maintenance
- Data initialization and updates

### `examples/`
- Example usage and expected outputs
- Helpful for understanding the system

