# frontend

A new Flutter project.

## Recipes: local full data vs API summaries (hybrid)

`GET /api/v1/recipes` returns **only** `id` and `name`. The app still stores **full** `Recipe` objects (ingredients, per-serving macros) in local storage via `StorageService`.

- **`RecipeProvider.syncSummariesFromApi`** merges those API rows with local recipes **by id**. If you have a full local recipe with the same id, the local copy wins; otherwise the UI shows an **`Recipe.apiSummary`** placeholder (no ingredients, no macros).
- **`GET /api/v1/recipes/{id}`** returns a full recipe for hydration / planner sync.
- **Meal planning** sends `recipe_ids` to `POST /api/v1/plan`. Only ids that exist in the **server** recipe pool affect the solver unless you sync local recipes first.

### Bundled server recipes (offline / dev)

When the API is unreachable, you can still load the same shape as `data/recipes/recipes.json` from a bundled asset:

1. Asset path: **`assets/dev/server_recipes.json`** (keep in sync with the repo file when recipes change):

   `cp ../data/recipes/recipes.json assets/dev/server_recipes.json`

2. Run with:

   `flutter run -d chrome --dart-define=BUNDLE_SERVER_RECIPES=true`

This merges bundled recipes into **`SharedPreferences`** (by `id`, overwriting existing entries with the same id). Ingredient lines have **quantities and names** but **macro fields are zero** until you use nutrition tooling or API-backed resolution.

**Automatic ingredient lines:** On startup the app always tries to load **`assets/dev/server_recipes.json`**. If the file exists (ships with the repo copy), recipe rows that only had **id + name** from `GET /api/v1/recipes` are shown with **full ingredient lines** from that JSON (no dart-define required). When **saved** ingredients load (including **`BUNDLE_CACHED_INGREDIENTS`**), matching lines get **per-100g macros** where the ingredient **name** matches (case-insensitive).

### Bundled cached ingredients (USDA disk cache → Saved)

Python writes resolved foods to **`.cache/ingredients/*.json`**. To import them into the app as **Saved** ingredients (with per-100g macros and micronutrients):

1. Regenerate the Flutter asset from the repo root:

   `python3 scripts/export_flutter_cached_ingredients_bundle.py`

   This writes **`frontend/assets/dev/cached_ingredients.json`**.

2. Run with:

   `flutter run -d chrome --dart-define=BUNDLE_CACHED_INGREDIENTS=true`

You can combine both dev bundles:

`flutter run -d chrome --dart-define=BUNDLE_SERVER_RECIPES=true --dart-define=BUNDLE_CACHED_INGREDIENTS=true`

Imports are keyed by **`fdc_id`** (string) as **`Ingredient.id`**; existing rows with the same id are replaced.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter learning resources](https://docs.flutter.dev/reference/learning-resources)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
