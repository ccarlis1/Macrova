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

### Bundled user profile (repo `config/user_profile.yaml` shape)

1. Asset path: **`assets/dev/user_profile.yaml`** — keep in sync with the repo when goals change:

   `cp ../config/user_profile.yaml assets/dev/user_profile.yaml`

2. Run with:

   `flutter run -d chrome --dart-define=BUNDLE_USER_PROFILE=true`

On startup (after loading saved prefs), the app **replaces** the profile with the bundled YAML, **writes it to** `SharedPreferences`, and clears API key fields in that snapshot (set keys in the Profile UI if needed). Macros match the Python loader: carbs are derived from calories, protein, and the fat range; `preferences.allergies` and `micronutrient_goals` are applied; `demographic` maps to demographic group.

Combine with recipe/ingredient bundles as needed, e.g.:

`flutter run -d chrome --dart-define=BUNDLE_USER_PROFILE=true --dart-define=BUNDLE_SERVER_RECIPES=true --dart-define=BUNDLE_CACHED_INGREDIENTS=true`

### Web: `LateInitializationError: _handledContextLostEvent` after hot restart

If the browser console shows:

`LateInitializationError: Field '_handledContextLostEvent' has not been initialized`

with a stack under `lib/_engine/engine/canvaskit/surface.dart`, that comes from **Flutter’s CanvasKit / WebGL layer**, not from this repo. It usually appears when the **WebGL context is lost** (hot restart, tab sleep, GPU reset) while the engine’s `onContextLost` handler runs **before** internal `late` fields are set—a known class of races in Flutter web.

**What to do:** Prefer a **full page refresh** (or stop and `flutter run` again) instead of relying on hot restart for web when you see this. If it keeps happening, `flutter upgrade` may pick up an engine fix. You can track related issues under [flutter/flutter](https://github.com/flutter/flutter/issues?q=is%3Aissue+canvaskit+context+lost) (CanvasKit / WebGL context loss).

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter learning resources](https://docs.flutter.dev/reference/learning-resources)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
