import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';

void main() {
  test('toSyncPayload sends cooking_time_minutes and instructions', () {
    const r = Recipe(
      id: 'rid',
      name: 'Soup',
      ingredients: [
        RecipeIngredientEntry(
          ingredientId: 'i1',
          ingredientName: 'water',
          quantity: 100,
          unit: 'g',
        ),
      ],
      servings: 2,
      cookingTimeMinutes: 35,
      instructions: ['Boil.', 'Simmer.'],
    );
    final p = r.toSyncPayload();
    expect(p['cooking_time_minutes'], 35);
    expect(p['instructions'], ['Boil.', 'Simmer.']);
    expect(p['default_servings'], 2);
  });

  test('toSyncPayload default_servings round-trips servings', () {
    const r = Recipe(
      id: 'rid',
      name: 'Soup',
      ingredients: [],
      servings: 4,
    );
    expect(r.toSyncPayload()['default_servings'], r.servings);
  });

  group('BE-19 grams_per_unit', () {
    const recipe = Recipe(
      id: 'rid',
      name: 'Porridge',
      ingredients: [
        RecipeIngredientEntry(
          ingredientId: 'oats',
          ingredientName: 'oats',
          quantity: 1,
          unit: 'cup',
          unitConversions: {'cup': 80, 'tbsp': 5},
        ),
        RecipeIngredientEntry(
          ingredientId: 'milk',
          ingredientName: 'milk',
          quantity: 200,
          unit: 'g',
          unitConversions: {'cup': 240},
        ),
        RecipeIngredientEntry(
          ingredientId: 'honey',
          ingredientName: 'honey',
          quantity: 1,
          unit: 'tbsp',
        ),
      ],
    );

    List<Map<String, dynamic>> lines() =>
        (recipe.toSyncPayload()['ingredients'] as List)
            .cast<Map<String, dynamic>>();

    test('Given a non-g unit with a conversion, Then its grams_per_unit is sent',
        () {
      expect(lines()[0]['grams_per_unit'], 80);
    });

    test('Given a g line, Then no grams_per_unit is sent', () {
      expect(lines()[1].containsKey('grams_per_unit'), isFalse);
    });

    test('Given a non-g unit with no conversion, Then no grams_per_unit is sent',
        () {
      expect(lines()[2].containsKey('grams_per_unit'), isFalse);
      expect(lines()[2]['unit'], 'tbsp');
    });
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
