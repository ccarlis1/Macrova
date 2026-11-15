import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/starter_recipe.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/services/api_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

// FE-16: RecipeProvider's starter-pack list and import, with fake API fns.

Map<String, dynamic> _json(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync())
        as Map<String, dynamic>;

List<StarterRecipe> _pack() =>
    StarterRecipe.listFromResponse(_json('starter_recipes_list.json'));

/// A fake server: a pool (id → name) that the import adds to, as BE-22 does.
class FakeStarterServer {
  final Map<String, String> pool = {};
  final List<List<String>> importCalls = [];
  final Map<String, String> pack = {for (final r in _pack()) r.id: r.name};

  Future<List<RecipeSummary>> list() async => [
        for (final e in pool.entries) RecipeSummary(id: e.key, name: e.value),
      ];

  Future<StarterImportResult> import(List<String> ids) async {
    importCalls.add(List.of(ids));
    final imported = <String>[];
    final skipped = <StarterImportSkipped>[];
    for (final id in ids) {
      if (!pack.containsKey(id)) {
        skipped.add(StarterImportSkipped(
          id: id,
          reason: StarterImportSkipped.notAStarterRecipe,
        ));
      } else if (pool.containsKey(id)) {
        skipped.add(StarterImportSkipped(
          id: id,
          reason: StarterImportSkipped.alreadyInPool,
        ));
      } else {
        pool[id] = pack[id]!;
        imported.add(id);
      }
    }
    return StarterImportResult(imported: imported, skipped: skipped);
  }

  RecipeProvider provider({RecipeDetailFn? detail}) => RecipeProvider(
        recipeListFn: list,
        starterListFn: () async => _pack(),
        starterImportFn: import,
        recipeDetailFn: detail,
      );
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('RecipeProvider starter pack (FE-16)', () {
    test('Given the list loads, Then starterRecipes holds the pack', () async {
      final server = FakeStarterServer();
      final recipes = server.provider();
      expect(recipes.starterRecipes, isNull);

      final f = recipes.loadStarterRecipes();
      expect(recipes.starterLoading, isTrue);
      await f;

      expect(recipes.starterLoading, isFalse);
      expect(recipes.starterError, isNull);
      expect(recipes.starterRecipes, hasLength(18));
    });

    test('Given the list fails, Then starterError holds the message', () async {
      final recipes = RecipeProvider(
        starterListFn: () async => throw const ApiException(
          statusCode: 500,
          code: 'INTERNAL_ERROR',
          message: 'boom',
        ),
      );
      await recipes.loadStarterRecipes();
      expect(recipes.starterRecipes, isNull);
      expect(recipes.starterError, 'boom');
    });

    test(
        'Given an empty pool, When 3 are imported, Then the library lists '
        'those 3 as server recipes and nothing is stored on the device',
        () async {
      final server = FakeStarterServer();
      final recipes = server.provider();
      await recipes.load();
      await recipes.syncSummariesFromApi();
      expect(recipes.recipes, isEmpty);

      final result = await recipes.importStarterRecipes(
        ['recipe_001', 'recipe_009', 'recipe_017'],
      );

      expect(result.imported, ['recipe_001', 'recipe_009', 'recipe_017']);
      expect(result.skipped, isEmpty);
      expect(
        recipes.recipes.map((r) => r.id).toSet(),
        {'recipe_001', 'recipe_009', 'recipe_017'},
      );
      expect(recipes.remoteRecipeIds, hasLength(3));
      expect(recipes.libraryRecipeIds, hasLength(3));
      expect(recipes.localFullRecipesForSync, isEmpty);
      expect(recipes.starterImporting, isFalse);
    });

    test('Given a partial import, Then skipped ids come back with reasons',
        () async {
      final server = FakeStarterServer()..pool['recipe_001'] = 'Carb Heavy';
      final recipes = server.provider();

      final result =
          await recipes.importStarterRecipes(['recipe_001', 'recipe_002', 'x']);

      expect(result.imported, ['recipe_002']);
      expect(result.skipped, const [
        StarterImportSkipped(id: 'recipe_001', reason: 'already_in_pool'),
        StarterImportSkipped(id: 'x', reason: 'not_a_starter_recipe'),
      ]);
    });

    test('Given the import request fails, Then it throws and nothing refreshes',
        () async {
      var listCalls = 0;
      final recipes = RecipeProvider(
        recipeListFn: () async {
          listCalls++;
          return const [];
        },
        starterImportFn: (_) async => throw const ApiException(
          statusCode: 400,
          code: 'INVALID_REQUEST',
          message: 'Invalid request schema.',
        ),
      );

      await expectLater(
        recipes.importStarterRecipes(['recipe_001']),
        throwsA(isA<ApiException>()),
      );
      expect(listCalls, 0);
      expect(recipes.starterImporting, isFalse);
    });

    test(
        'Given an imported recipe with cup/tbsp/scoop lines, When its detail '
        'loads, Then every line has a gram weight and sync sends '
        'grams_per_unit', () async {
      final server = FakeStarterServer();
      final detail = Recipe.fromJson(_json('starter_recipe_detail_units.json'));
      final recipes = server.provider(detail: (id) async => detail);
      await recipes.importStarterRecipes(['recipe_009']);

      final full = await recipes.fetchRecipeDetail('recipe_009');

      expect(full.ingredients, hasLength(7));
      expect(full.linesWithoutGramWeight, isEmpty);
      final yogurt = full.ingredients.first;
      expect(yogurt.unit, 'cup');
      expect(yogurt.hasGramWeight, isTrue);
      expect(yogurt.gramsPerUnitToSend, 245.0);
      expect(full.totalCalories, greaterThan(0));

      final lines = (full.toSyncPayload()['ingredients'] as List)
          .cast<Map<String, dynamic>>();
      final byUnit = {for (final l in lines) l['name']: l['grams_per_unit']};
      expect(byUnit['low fat greek yogurt'], 245.0);
      expect(byUnit['honey'], 21.0);
      expect(
        byUnit['whey protein powder 24 grams of protein per scoop'],
        28.67,
      );
      expect(byUnit['blueberries'], isNull); // `g` sends no weight
    });
  });
}
