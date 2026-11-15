import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/recipe_sync_result.dart';
import 'package:macrova/services/api_service.dart';

const _unitError =
    "r-1: UNIT_NOT_CONVERTIBLE: Ingredient 'almonds' has no gram conversion "
    "for unit 'cup': use a mass unit or send grams_per_unit for this line.";

const _sent = [
  Recipe(id: 'r-1', name: 'Almond Bowl'),
  Recipe(id: 'r-2', name: 'Rice'),
];

void main() {
  group('RecipeSyncError.parse (FE-13)', () {
    test('Given "<id>: <CODE>: <message>", Then each part is read', () {
      final e = RecipeSyncError.parse(_unitError, sent: _sent);

      expect(e.recipeId, 'r-1');
      expect(e.recipeName, 'Almond Bowl');
      expect(e.code, 'UNIT_NOT_CONVERTIBLE');
      expect(e.message, startsWith("Ingredient 'almonds' has no gram"));
      expect(e.message, endsWith('for this line.'));
      expect(e.displayText, 'Almond Bowl: ${e.message}');
    });

    test('Given a dietary-flag INVALID_REQUEST, Then it parses the same way',
        () {
      final e = RecipeSyncError.parse(
        "r-2: INVALID_REQUEST: dietary flag 'vegan' is contradicted by "
        "ingredient(s) 'honey': remove the flag or the ingredient.",
        sent: _sent,
      );

      expect(e.recipeName, 'Rice');
      expect(e.code, 'INVALID_REQUEST');
      expect(e.message, startsWith("dietary flag 'vegan'"));
    });

    test('Given an id containing ": ", Then the sent id is matched', () {
      const odd = Recipe(id: 'a: b', name: 'Odd');
      final e = RecipeSyncError.parse(
        'a: b: INGREDIENT_UNRESOLVED: Ingredient x is not in the table',
        sent: const [odd],
      );

      expect(e.recipeId, 'a: b');
      expect(e.code, 'INGREDIENT_UNRESOLVED');
    });

    test('Given an unsent id, Then the id is still read but has no name', () {
      final e = RecipeSyncError.parse(_unitError);

      expect(e.recipeId, 'r-1');
      expect(e.recipeName, isNull);
      expect(e.displayText, startsWith('r-1: Ingredient'));
    });

    test('Given an unexpected shape, Then the raw string is shown', () {
      final e = RecipeSyncError.parse('something went wrong');

      expect(e.recipeId, isNull);
      expect(e.code, isNull);
      expect(e.displayText, 'something went wrong');
    });
  });

  group('ApiService.syncRecipes (FE-13)', () {
    test('Given synced_ids and errors, Then both are returned', () async {
      late Map<String, dynamic> sentBody;
      final client = MockClient((req) async {
        sentBody = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response(
          jsonEncode({
            'synced_ids': ['r-2'],
            'errors': [_unitError],
          }),
          200,
        );
      });

      final result = await ApiService.syncRecipes(_sent, client: client);

      expect((sentBody['recipes'] as List).length, 2);
      expect(result.syncedIds, ['r-2']);
      expect(result.errors.single.recipeName, 'Almond Bowl');
      expect(result.errors.single.code, 'UNIT_NOT_CONVERTIBLE');
    });

    test('Given no errors key, Then errors is empty', () async {
      final client = MockClient(
        (_) async => http.Response('{"synced_ids": ["r-1"]}', 200),
      );

      final result = await ApiService.syncRecipes(_sent, client: client);

      expect(result.syncedIds, ['r-1']);
      expect(result.errors, isEmpty);
    });

    test('Given no synced_ids, Then INVALID_RESPONSE is thrown', () async {
      final client = MockClient((_) async => http.Response('{}', 200));

      expect(
        () => ApiService.syncRecipes(_sent, client: client),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'INVALID_RESPONSE'),
        ),
      );
    });
  });
}
