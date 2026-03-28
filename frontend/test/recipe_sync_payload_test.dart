import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';

void main() {
  test('toSyncPayload sends cooking_time_minutes and instructions', () {
    final r = Recipe(
      id: 'rid',
      name: 'Soup',
      ingredients: const [
        RecipeIngredientEntry(
          ingredientId: 'i1',
          ingredientName: 'water',
          quantity: 100,
          unit: 'g',
        ),
      ],
      servings: 2,
      cookingTimeMinutes: 35,
      instructions: const ['Boil.', 'Simmer.'],
    );
    final p = r.toSyncPayload();
    expect(p['cooking_time_minutes'], 35);
    expect(p['instructions'], ['Boil.', 'Simmer.']);
  });

  test('fromServerRecipeMap reads cooking_time_minutes and instructions', () {
    final r = Recipe.fromServerRecipeMap({
      'id': 'x',
      'name': 'Y',
      'cooking_time_minutes': 12,
      'instructions': ['A', 'B'],
      'ingredients': [
        {'name': 'salt', 'quantity': 1.0, 'unit': 'g'},
      ],
    });
    expect(r.cookingTimeMinutes, 12);
    expect(r.instructions, ['A', 'B']);
  });
}
