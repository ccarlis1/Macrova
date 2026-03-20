# frontend

A new Flutter project.

## Recipes: local full data vs API summaries (hybrid)

`GET /api/v1/recipes` returns **only** `id` and `name`. The app still stores **full** `Recipe` objects (ingredients, per-serving macros) in local storage via `StorageService`.

- **`RecipeProvider.syncSummariesFromApi`** merges those API rows with local recipes **by id**. If you have a full local recipe with the same id, the local copy wins; otherwise the UI shows an **`Recipe.apiSummary`** placeholder (no ingredients, no macros).
- **Meal planning** sends `recipe_ids` to `POST /api/v1/plan`. Only ids that exist in the **server** recipe pool affect the solver. Local-only UUIDs are called out in the planner UI when the remote list is non-empty.
- A future **`GET /api/v1/recipes/{id}`** (or richer list payloads) would let the client hydrate full recipes from the API instead of placeholders.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter learning resources](https://docs.flutter.dev/reference/learning-resources)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
