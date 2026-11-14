import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';

Map<String, dynamic> _detailFixture() => jsonDecode(
      File('test/fixtures/recipe_detail_meal_prep.json').readAsStringSync(),
    ) as Map<String, dynamic>;

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

  group('FE-12 tags', () {
    const line = RecipeIngredientEntry(
      ingredientId: 'i1',
      ingredientName: 'oats',
      quantity: 80,
      unit: 'g',
    );

    test(
        'Given tags, cuisine and cost, Then toSyncPayload sends them, minus the '
        'server-derived time type', () {
      const r = Recipe(
        id: 'rid',
        name: 'Oats',
        ingredients: [line],
        tagSlugsByType: {
          'context': ['breakfast', 'meal-prep'],
          'nutrition': ['high-fiber'],
          'time': ['time-2'],
        },
        isMealPrepCapable: true,
        cuisine: 'american',
        costLevel: 'cheap',
      );

      final p = r.toSyncPayload();

      expect(p['tag_slugs_by_type'], {
        'context': ['breakfast', 'meal-prep'],
        'nutrition': ['high-fiber'],
      });
      expect(p['cuisine'], 'american');
      expect(p['cost_level'], 'cheap');
      expect(p.containsKey('is_meal_prep_capable'), isFalse);
    });

    test(
        'Given no tags (or only time) and no cuisine/cost, Then those keys are '
        'omitted so the server keeps its stored values', () {
      const untagged = Recipe(id: 'a', name: 'A', ingredients: [line]);
      const timeOnly = Recipe(
        id: 'b',
        name: 'B',
        ingredients: [line],
        tagSlugsByType: {
          'time': ['time-1'],
        },
      );

      for (final r in [untagged, timeOnly]) {
        final p = r.toSyncPayload();
        expect(p.containsKey('tag_slugs_by_type'), isFalse);
        expect(p.containsKey('cuisine'), isFalse);
        expect(p.containsKey('cost_level'), isFalse);
      }
    });

    test(
        'Given the captured recipe detail, Then fromJson reads '
        'tag_slugs_by_type and is_meal_prep_capable', () {
      final r = Recipe.fromJson(_detailFixture());

      expect(r.id, 'fe12-oat-bowl');
      expect(r.servings, 2);
      expect(r.tagSlugsByType, {
        'context': ['breakfast', 'meal-prep'],
        'nutrition': ['high-fiber'],
        'time': ['time-2'],
      });
      expect(r.isMealPrepCapable, isTrue);
      expect(r.hasMealPrepTag, isTrue);
      // The detail doesn't return cuisine / cost_level.
      expect(r.cuisine, isNull);
      expect(r.costLevel, isNull);
      // Re-syncing sends back every type the server returned, except time.
      expect(r.toSyncPayload()['tag_slugs_by_type'], {
        'context': ['breakfast', 'meal-prep'],
        'nutrition': ['high-fiber'],
      });
    });

    test('Given an older detail without tag fields, Then defaults apply', () {
      final json = _detailFixture()
        ..remove('tag_slugs_by_type')
        ..remove('is_meal_prep_capable');

      final r = Recipe.fromJson(json);

      expect(r.tagSlugsByType, isEmpty);
      expect(r.isMealPrepCapable, isFalse);
    });

    test('Given tags, cuisine and cost, Then local storage round-trips them',
        () {
      const r = Recipe(
        id: 'rid',
        name: 'Oats',
        ingredients: [line],
        tagSlugsByType: {
          'context': ['lunch'],
        },
        isMealPrepCapable: true,
        cuisine: 'thai',
        costLevel: 'premium',
      );

      final back = Recipe.fromJson(
        jsonDecode(jsonEncode(r.toJson())) as Map<String, dynamic>,
      );

      expect(back.tagSlugsByType, r.tagSlugsByType);
      expect(back.isMealPrepCapable, isTrue);
      expect(back.cuisine, 'thai');
      expect(back.costLevel, 'premium');
    });
  });
}
