import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/recipe_sync_result.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/services/api_service.dart';
import 'package:macrova/services/storage_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

Recipe _detail({String? cuisine, String? cost, List<String>? flags}) {
  final json = jsonDecode(
    File('test/fixtures/recipe_detail_meal_prep.json').readAsStringSync(),
  ) as Map<String, dynamic>;
  json['cuisine'] = cuisine;
  json['cost_level'] = cost;
  json['dietary_flags'] = flags;
  return Recipe.fromJson(json);
}

const _line = RecipeIngredientEntry(
  ingredientId: 'i1',
  ingredientName: 'oats',
  quantity: 50,
);

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  RecipeProvider provider(Map<String, Recipe Function()> details,
      [List<String>? calls]) {
    return RecipeProvider(
      recipeSyncFn: (b) async =>
          RecipeSyncResult(syncedIds: [for (final r in b) r.id]),
      recipeDetailFn: (id) async {
        calls?.add(id);
        final make = details[id];
        if (make == null) {
          throw const ApiException(
            statusCode: 404,
            code: 'RECIPE_NOT_FOUND',
            message: 'not found',
          );
        }
        return make();
      },
      recipeListFn: () async => const [],
    );
  }

  group('RecipeProvider server tag fields (FE-12)', () {
    test(
        'Given loaded server tags, When the recipe is saved (synced), Then '
        'they are stale and reload on next need (FE-14: is_meal_prep_capable '
        'is recomputed by the server)', () async {
      await StorageService.saveRecipes([
        const Recipe(id: 'a', name: 'A', ingredients: [_line]),
      ]);
      final calls = <String>[];
      final p = provider({'a': () => _detail()}, calls);
      await p.load();
      await p.loadServerTags(['a']);
      expect(p.hasServerTags('a'), isTrue);

      await p.updateRecipe(p.getById('a')!.copyWith(servings: 2));

      expect(p.hasServerTags('a'), isFalse);
      await p.loadServerTags(['a']);
      expect(calls, ['a', 'a']);
      expect(p.getById('a')!.isMealPrepCapable, isTrue);
    });

    test(
        'Given a remembered cuisine/cost, When the detail has its own, Then '
        'the server value wins', () async {
      await StorageService.saveRecipes([
        const Recipe(
          id: 'fe12-oat-bowl',
          name: 'Oats',
          ingredients: [_line],
          cuisine: 'italian',
          costLevel: 'premium',
        ),
      ]);
      final p = provider({
        'fe12-oat-bowl': () =>
            _detail(cuisine: 'american', cost: 'cheap', flags: ['vegan']),
      });
      await p.load();

      final r = await p.fetchRecipeDetail('fe12-oat-bowl');

      expect(r.cuisine, 'american');
      expect(r.costLevel, 'cheap');
      expect(r.dietaryFlags, ['vegan']);
      expect(p.hasServerTags('fe12-oat-bowl'), isTrue);
    });

    test(
        'Given a remembered cuisine/cost, When the recipe has no tag entry '
        '(nulls), Then the remembered values are kept', () async {
      const local = Recipe(
        id: 'fe12-oat-bowl',
        name: 'Oats',
        ingredients: [_line],
        cuisine: 'thai',
        costLevel: 'premium',
      );
      await StorageService.saveRecipes([local]);
      final p = provider({'fe12-oat-bowl': () => _detail()});
      await p.load();

      final r = await p.refreshServerTags(local);

      expect(r.cuisine, 'thai');
      expect(r.costLevel, 'premium');
      expect(r.dietaryFlags, isNull);
      // Lines are local; tags come from the detail.
      expect(r.ingredients.single.ingredientName, 'oats');
      expect(r.isMealPrepCapable, isTrue);
      expect(p.getById('fe12-oat-bowl')!.cuisine, 'thai');
    });

    test(
        'Given ids, When loadServerTags runs twice, Then each id is fetched '
        'once, and a failed id stays unchecked', () async {
      await StorageService.saveRecipes([
        const Recipe(id: 'a', name: 'A', ingredients: [_line]),
      ]);
      final calls = <String>[];
      final p = provider({
        'a': () => _detail(cuisine: 'american', cost: 'standard'),
      }, calls);
      await p.load();

      await p.loadServerTags(['a', 'missing']);
      await p.loadServerTags(['a', 'missing']);

      expect(calls, ['a', 'missing']);
      expect(p.hasServerTags('a'), isTrue);
      expect(p.hasServerTags('missing'), isFalse);
      expect(p.serverTagsLoading, isFalse);
      // A stored recipe with lines keeps them (refreshServerTags).
      final a = p.getById('a')!;
      expect(a.name, 'A');
      expect(a.cuisine, 'american');
    });
  });
}
