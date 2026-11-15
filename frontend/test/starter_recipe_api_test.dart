import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:macrova/models/starter_recipe.dart';
import 'package:macrova/services/api_service.dart';

// FE-16: `/api/v1/starter_recipes` client and DTOs, against responses captured
// in-process from the committed backend (see test/fixtures/README.md).

String _fixture(String name) => File('test/fixtures/$name').readAsStringSync();

Map<String, dynamic> _json(String name) =>
    jsonDecode(_fixture(name)) as Map<String, dynamic>;

void main() {
  group('StarterRecipe DTO', () {
    test('Given the captured list, Then all 18 parse with nutrition and tags',
        () {
      final list =
          StarterRecipe.listFromResponse(_json('starter_recipes_list.json'));

      expect(list, hasLength(18));
      final first = list.first;
      expect(first.id, 'recipe_001');
      expect(first.name, 'Carb Heavy');
      expect(first.cookingTimeMinutes, 15);
      expect(first.caloriesPerServing, 802.1);
      expect(first.proteinGPerServing, 30.0);
      expect(first.contextSlugs, ['lunch', 'dinner']);
      expect(first.tagSlugsByType['time'], ['time-2']);
      expect(first.readyForPlanning, isTrue);
      expect(first.unresolved, isEmpty);
      for (final r in list) {
        expect(r.caloriesPerServing, greaterThan(0), reason: r.id);
      }
    });

    test('Given an unresolved recipe, Then null nutrition and the names parse',
        () {
      final r = StarterRecipe.fromJson({
        'id': 'recipe_x',
        'name': 'X',
        'cooking_time_minutes': 10,
        'calories_per_serving': null,
        'protein_g_per_serving': null,
        'tag_slugs_by_type': <String, dynamic>{},
        'ready_for_planning': false,
        'unresolved': ['dragonfruit'],
      });
      expect(r.caloriesPerServing, isNull);
      expect(r.proteinGPerServing, isNull);
      expect(r.readyForPlanning, isFalse);
      expect(r.unresolved, ['dragonfruit']);
    });

    test('Given a list response without recipes, Then a FormatException', () {
      expect(
        () => StarterRecipe.listFromResponse({'items': []}),
        throwsFormatException,
      );
    });

    test('Given the captured partial import, Then imported and skipped parse',
        () {
      final r =
          StarterImportResult.fromJson(_json('starter_import_partial.json'));
      expect(r.imported, ['recipe_001', 'recipe_009', 'recipe_017']);
      expect(r.skipped, const [
        StarterImportSkipped(
          id: 'not-a-starter',
          reason: StarterImportSkipped.notAStarterRecipe,
        ),
      ]);

      final again =
          StarterImportResult.fromJson(_json('starter_import_already.json'));
      expect(again.imported, ['recipe_002']);
      expect(again.skipped, const [
        StarterImportSkipped(
          id: 'recipe_001',
          reason: StarterImportSkipped.alreadyInPool,
        ),
      ]);
    });
  });

  group('ApiService starter routes', () {
    test('When listing, Then GET /starter_recipes and the list parses',
        () async {
      final client = MockClient((req) async {
        expect(req.method, 'GET');
        expect(req.url.path, '/api/v1/starter_recipes');
        return http.Response(_fixture('starter_recipes_list.json'), 200);
      });
      final list = await ApiService.listStarterRecipes(client: client);
      expect(list.map((r) => r.id).take(2), ['recipe_001', 'recipe_002']);
    });

    test('When importing, Then POST {recipe_ids} and a partial skip parses',
        () async {
      final client = MockClient((req) async {
        expect(req.method, 'POST');
        expect(req.url.path, '/api/v1/starter_recipes/import');
        expect(jsonDecode(req.body), {
          'recipe_ids': ['recipe_001', 'recipe_009', 'recipe_017', 'not-a-starter'],
        });
        return http.Response(_fixture('starter_import_partial.json'), 200);
      });
      final r = await ApiService.importStarterRecipes(
        ['recipe_001', 'recipe_009', 'recipe_017', 'not-a-starter'],
        client: client,
      );
      expect(r.imported, hasLength(3));
      expect(r.skipped.single.reason, 'not_a_starter_recipe');
    });

    test('Given a 400 envelope, Then ApiException carries the server code',
        () async {
      final client = MockClient(
        (_) async =>
            http.Response(_fixture('starter_import_error_invalid.json'), 400),
      );
      await expectLater(
        ApiService.importStarterRecipes(const [], client: client),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 400)
              .having((e) => e.code, 'code', 'INVALID_REQUEST'),
        ),
      );
    });

    test('Given a 200 that is not the shape, Then INVALID_RESPONSE', () async {
      final client = MockClient((_) async => http.Response('[]', 200));
      await expectLater(
        ApiService.listStarterRecipes(client: client),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'INVALID_RESPONSE'),
        ),
      );
    });
  });
}
