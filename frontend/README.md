# frontend

A new Flutter project.

## Recipes: local full data vs API summaries (hybrid)

`GET /api/v1/recipes` returns **only** `id` and `name`. The app still stores **full** `Recipe` objects (ingredients, per-serving macros) in local storage via `StorageService`.

- **`RecipeProvider.syncSummariesFromApi`** merges those API rows with local recipes **by id**. If you have a full local recipe with the same id, the local copy wins; otherwise the UI shows an **`Recipe.apiSummary`** placeholder (no ingredients, no macros).
- **`GET /api/v1/recipes/{id}`** returns a full recipe for hydration / planner sync.
- **Meal planning** (`POST /api/v1/plan`) uses the whole **server** pool unless Planner Config has recipes ticked; then it sends those ids as `recipe_ids`. Before each plan the app syncs every locally stored full recipe, so local edits reach the server first.

### Starter pack (FE-16)

A new user's pool (a fresh `MACROVA_DATA_DIR`) is empty. The Recipe Library (empty state and its **Starter pack** action), Today's empty state, and the `EMPTY_POOL` plan failure open a picker sheet over `GET /api/v1/starter_recipes`; **Import** sends the ticked ids to `POST /api/v1/starter_recipes/import`, then refreshes `GET /api/v1/recipes`. The imported recipes are ordinary server recipes: opening one in the Recipe Builder loads its detail. The app keeps no copy of the starter pack and imports nothing on its own.

There is no bundled recipe asset any more (`assets/dev/server_recipes.json` and `BUNDLE_SERVER_RECIPES` were removed in FE-16): recipes come from the API.

### Bundled cached ingredients (USDA disk cache → Saved)

Python writes resolved foods to **`.cache/ingredients/*.json`**. To import them into the app as **Saved** ingredients (with per-100g macros and micronutrients):

1. Regenerate the Flutter asset from the repo root:

   `python3 scripts/export_flutter_cached_ingredients_bundle.py`

   This writes **`frontend/assets/dev/cached_ingredients.json`**.

2. Run with:

   `flutter run -d chrome --dart-define=BUNDLE_CACHED_INGREDIENTS=true`

When saved ingredients load, recipe lines whose per-100g macros are zero get them from a saved ingredient whose **name** matches (case-insensitive).

Imports are keyed by **`fdc_id`** (string) as **`Ingredient.id`**; existing rows with the same id are replaced.

### Profile

The profile lives on the device (`SharedPreferences`, edited on the Profile screen). No profile ships in the app bundle: `assets/dev/user_profile.yaml` and `BUNDLE_USER_PROFILE` were removed in FE-16, and `test/bundle_assets_test.dart` fails if a YAML asset is listed in `pubspec.yaml` again.

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
