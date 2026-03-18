# Agents

## Cursor Cloud specific instructions

### Overview

Macrova (nutrition-agent) is a Python meal planning application with a CLI and FastAPI REST API. The Flutter frontend is scaffolded but has no source code yet — skip it.

### Running the application

- **CLI**: `python3 plan_meals.py` (generates a daily meal plan to stdout)
- **REST API**: `python3 -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000`
  - `GET /api/recipes` — list recipes
  - `POST /api/plan` — generate a meal plan (requires body with `daily_calories`, `daily_protein_g`, `daily_fat_g_min`, `daily_fat_g_max`, `schedule`)

### Data files

Before running CLI or API, three example files must be copied (the update script handles this):

```
cp config/user_profile.yaml.example config/user_profile.yaml
cp data/recipes/recipes.json.example data/recipes/recipes.json
cp data/ingredients/custom_ingredients.json.example data/ingredients/custom_ingredients.json
```

These are `.gitignore`d, so they won't exist on a fresh checkout until copied.

### Tests, lint, type-check

- **Tests**: `pytest tests/` — 526 tests, all self-contained (no network/API key needed), ~1s runtime
- **Formatter**: `black --check .` — pre-existing formatting drift exists (49 files); do not reformat unless explicitly asked
- **Type checker**: `mypy src/` — has a pre-existing module resolution error; run with `mypy --explicit-package-bases src/` to work around it

### Gotchas

- `pip install` installs to `~/.local/bin` which may not be on `PATH`. The update script prepends it.
- The USDA API key (`.env` / `USDA_API_KEY`) is only needed for `--ingredient-source api` mode; local mode and all tests work without it.
- The Flutter frontend (`frontend/`) has an empty `lib/` directory — widget tests will fail. Ignore it.
