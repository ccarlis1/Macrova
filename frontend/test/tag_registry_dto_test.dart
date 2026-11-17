import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:macrova/models/tag.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/services/api_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

String _fixture(String name) =>
    File('test/fixtures/$name').readAsStringSync();

/// LLM-sourced registry entries (not in the seeded registry) to exercise the
/// tag-semantics eligibility rule.
const _llmTags = [
  {
    'slug': 'brunch',
    'display': 'Brunch',
    'type': 'context',
    'source': 'llm',
    'semantic_class': 'meal_role',
    'eligibility': 'proposed',
  },
  {
    'slug': 'supper',
    'display': 'Supper',
    'type': 'context',
    'source': 'llm',
    'semantic_class': 'meal_role',
    'eligibility': 'approved',
  },
  {
    'slug': 'elevenses',
    'display': 'Elevenses',
    'type': 'context',
    'source': 'user',
    'semantic_class': 'meal_role',
    'eligibility': 'rejected',
  },
];

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('ApiService.listTags', () {
    test('Given the captured GET /api/v1/tags body, Then every field parses',
        () async {
      late Uri requested;
      final client = MockClient((req) async {
        requested = req.url;
        return http.Response(_fixture('tags_list_response.json'), 200);
      });

      final tags = await ApiService.listTags(client: client);

      expect(requested.path, '/api/v1/tags');
      expect(requested.queryParameters, isEmpty);
      expect(tags, hasLength(14));
      final breakfast = tags.firstWhere((t) => t.slug == 'breakfast');
      expect(breakfast.display, 'Breakfast');
      expect(breakfast.type, 'context');
      expect(breakfast.source, 'system');
      expect(breakfast.semanticClass, 'meal_role');
      expect(breakfast.eligibility, isNull);
      expect(breakfast.hardFilterAllowed, isTrue);
      expect(breakfast.plannerHardEligible, isTrue);
      expect(breakfast.isMealRole, isTrue);
      expect(breakfast.isOfferable, isTrue);
      final mealPrep = tags.firstWhere((t) => t.slug == 'meal-prep');
      expect(mealPrep.semanticClass, 'capability');
      expect(mealPrep.isMealRole, isFalse);
    });

    test('Given a type, Then it is sent as ?type=', () async {
      late Uri requested;
      final client = MockClient((req) async {
        requested = req.url;
        return http.Response('{"tags": []}', 200);
      });

      await ApiService.listTags(type: 'context', client: client);

      expect(requested.queryParameters, {'type': 'context'});
    });

    test('Given an error envelope, Then ApiException carries its code',
        () async {
      final client = MockClient(
        (_) async => http.Response(
          '{"error": {"code": "TAG_INVALID", "message": "Invalid tag type."}}',
          400,
        ),
      );

      expect(
        () => ApiService.listTags(client: client),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'TAG_INVALID'),
        ),
      );
    });
  });

  group('RecipeProvider tag registry', () {
    List<TagMeta> registry() {
      final body = jsonDecode(_fixture('tags_list_response.json'))
          as Map<String, dynamic>;
      return [
        ...TagMeta.listFromResponse(body),
        for (final t in _llmTags) TagMeta.fromJson(t),
      ];
    }

    test(
        'Given system and LLM tags, Then meal roles offer only approved or '
        'system/user ones, in registry order', () async {
      final provider = RecipeProvider(tagListFn: () async => registry());

      await provider.loadTagRegistry();

      expect(
        provider.mealRoleTags.map((t) => t.slug),
        ['breakfast', 'dinner', 'lunch', 'snack', 'supper'],
      );
    });

    test('Given the registry loaded once, Then it is not fetched again',
        () async {
      var calls = 0;
      final provider = RecipeProvider(
        tagListFn: () async {
          calls++;
          return registry();
        },
      );

      await Future.wait([
        provider.loadTagRegistry(),
        provider.loadTagRegistry(),
      ]);
      await provider.loadTagRegistry();
      expect(calls, 1);

      await provider.loadTagRegistry(force: true);
      expect(calls, 2);
    });

    test('Given a failing fetch, Then the error is kept and retry recovers',
        () async {
      var fail = true;
      final provider = RecipeProvider(
        tagListFn: () async {
          if (fail) {
            throw const ApiException(
              statusCode: 500,
              code: 'HTTP_ERROR',
              message: 'down',
            );
          }
          return registry();
        },
      );

      await provider.loadTagRegistry();
      expect(provider.tagRegistry, isNull);
      expect(provider.tagRegistryError, 'down');

      fail = false;
      await provider.loadTagRegistry();
      expect(provider.tagRegistryError, isNull);
      expect(provider.mealRoleTags, isNotEmpty);
    });
  });

  test('kCuisineVocabulary matches the OpenAPI RecipeSyncItem.cuisine enum', () {
    final spec = jsonDecode(
      File('../openapi/openapi.json').readAsStringSync(),
    ) as Map<String, dynamic>;
    final cuisine = spec['components']['schemas']['RecipeSyncItem']
        ['properties']['cuisine'] as Map<String, dynamic>;
    final variants = (cuisine['anyOf'] as List).cast<Map<String, dynamic>>();
    final enumValues = variants.firstWhere((v) => v.containsKey('enum'))['enum']
        as List;

    expect(kCuisineVocabulary, enumValues.cast<String>());
  });
}
