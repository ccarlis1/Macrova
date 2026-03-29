import '../models/models.dart';
import '../providers/recipe_provider.dart';

/// Default storefront for TinyFish search (v1); override when the app adds store settings.
const Map<String, String> kDefaultGroceryStore = {
  'id': 'walmart',
  'baseUrl': 'https://www.walmart.com',
};

/// Builds the JSON body for `POST /api/v1/grocery/optimize` from a generated [MealPlan].
///
/// Resolves structured ingredients from [RecipeProvider] using [Meal.recipeId].
/// Returns `null` if no recipes with ingredient lines could be resolved.
Map<String, dynamic>? buildGroceryOptimizeRequestBody({
  required MealPlan mealPlan,
  required RecipeProvider recipes,
  Map<String, dynamic>? preferences,
  List<Map<String, String>>? stores,
}) {
  final counts = <String, double>{};
  final seenIds = <String>{};
  for (final day in mealPlan.dailyPlans) {
    for (final meal in day.meals) {
      final id = meal.recipeId;
      if (id == null || id.isEmpty) continue;
      seenIds.add(id);
      counts[id] = (counts[id] ?? 0) + 1.0;
    }
  }

  final recipePayloads = <Map<String, dynamic>>[];
  for (final id in seenIds) {
    final r = recipes.getById(id);
    if (r == null || r.ingredients.isEmpty) {
      continue;
    }
    recipePayloads.add({
      'id': r.id,
      'name': r.name,
      'ingredients': [
        for (final e in r.ingredients)
          {
            'name': e.ingredientName,
            'quantity': e.quantity,
            'unit': e.unit,
            'isToTaste': false,
          },
      ],
    });
  }

  if (recipePayloads.isEmpty) {
    return null;
  }

  return {
    'schemaVersion': '1.0',
    'mealPlan': {
      'id': 'local-plan',
      'recipes': recipePayloads,
      'recipeServings': counts,
    },
    'preferences': preferences ?? const {'objective': 'balanced'},
    'stores': stores ?? [kDefaultGroceryStore],
  };
}
