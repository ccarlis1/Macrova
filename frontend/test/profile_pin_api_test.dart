import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/profile_pin.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/services/api_service.dart';

// FE-15: `/api/v1/profile/pins` client and DTO, against responses captured
// in-process from the committed backend (see test/fixtures/README.md).

String _fixture(String name) =>
    File('test/fixtures/$name').readAsStringSync();

Map<String, dynamic> _json(String name) =>
    jsonDecode(_fixture(name)) as Map<String, dynamic>;

void main() {
  group('ProfilePin DTO', () {
    test('Given the captured list response, Then every pin parses', () {
      final pins = ProfilePin.listFromResponse(_json('profile_pins_list.json'));

      expect(pins, const [
        ProfilePin(dayIndex: 0, slotIndex: 1, recipeId: 'recipe_001'),
        ProfilePin(dayIndex: 1, slotIndex: 0, recipeId: 'recipe_002'),
      ]);
    });

    test('Given a list response without pins, Then it is a FormatException',
        () {
      expect(
        () => ProfilePin.listFromResponse({'items': []}),
        throwsFormatException,
      );
    });

    test('Given the captured unpin response, Then deleted and pin parse', () {
      final r = ProfilePinDeleteResult.fromJson(_json('profile_pin_deleted.json'));
      expect(r.deleted, isTrue);
      expect(
        r.pin,
        const ProfilePin(dayIndex: 0, slotIndex: 1, recipeId: 'recipe_001'),
      );

      final none =
          ProfilePinDeleteResult.fromJson({'deleted': false, 'pin': null});
      expect(none.deleted, isFalse);
      expect(none.pin, isNull);
    });
  });

  group('ApiService pin routes', () {
    test('When listing, Then GET /profile/pins and the pins parse', () async {
      final client = MockClient((req) async {
        expect(req.method, 'GET');
        expect(req.url.path, '/api/v1/profile/pins');
        return http.Response(_fixture('profile_pins_list.json'), 200);
      });

      final pins = await ApiService.listPins(client: client);

      expect(pins.map((p) => (p.dayIndex, p.slotIndex)), [(0, 1), (1, 0)]);
    });

    test('When pinning, Then PUT /profile/pins/{day}/{slot} sends {recipe_id}',
        () async {
      late http.Request seen;
      final client = MockClient((req) async {
        seen = req;
        return http.Response(_fixture('profile_pin_created.json'), 200);
      });

      final pin = await ApiService.pin(0, 1, 'recipe_001', client: client);

      expect(seen.method, 'PUT');
      expect(seen.url.path, '/api/v1/profile/pins/0/1');
      expect(jsonDecode(seen.body), {'recipe_id': 'recipe_001'});
      expect(seen.headers['Content-Type'], startsWith('application/json'));
      expect(
        pin,
        const ProfilePin(dayIndex: 0, slotIndex: 1, recipeId: 'recipe_001'),
      );
    });

    test('Given a 404 RECIPE_NOT_FOUND, Then ApiException carries the code',
        () async {
      final client = MockClient(
        (_) async =>
            http.Response(_fixture('profile_pin_error_not_found.json'), 404),
      );

      await expectLater(
        ApiService.pin(0, 0, 'no-such-recipe', client: client),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', 'RECIPE_NOT_FOUND')
              .having((e) => e.statusCode, 'statusCode', 404)
              .having((e) => e.message, 'message',
                  "No recipe with id 'no-such-recipe'"),
        ),
      );
    });

    test('When unpinning, Then DELETE /profile/pins/{day}/{slot}', () async {
      final client = MockClient((req) async {
        expect(req.method, 'DELETE');
        expect(req.url.path, '/api/v1/profile/pins/0/1');
        return http.Response(_fixture('profile_pin_deleted.json'), 200);
      });

      final r = await ApiService.unpin(0, 1, client: client);

      expect(r.deleted, isTrue);
      expect(r.pin?.recipeId, 'recipe_001');
    });

    test('When clearing, Then DELETE /profile/pins returns cleared_count',
        () async {
      final client = MockClient((req) async {
        expect(req.method, 'DELETE');
        expect(req.url.path, '/api/v1/profile/pins');
        return http.Response(_fixture('profile_pins_cleared.json'), 200);
      });

      expect(await ApiService.clearPins(client: client), 1);
    });

    test('Given a 200 without the expected shape, Then INVALID_RESPONSE',
        () async {
      final client =
          MockClient((_) async => http.Response(jsonEncode({'x': 1}), 200));

      await expectLater(
        ApiService.clearPins(client: client),
        throwsA(isA<ApiException>()
            .having((e) => e.code, 'code', 'INVALID_RESPONSE')),
      );
    });
  });

  group('Index bases (REQUIRES_VERIFICATION 1, FE-15)', () {
    test(
        'Given pins at (0, 1) and (1, 0), Then the plan response places them on '
        'day 1 slot_index 1 and day 2 slot_index 0 as pinned_assignment', () {
      // Captured in sequence: PUT (0,1) and (1,0), then POST /plan (2 days).
      final pins = ProfilePin.listFromResponse(_json('profile_pins_list.json'));
      final plan = MealPlan.fromPlanApiV1Response(_json('plan_with_pin.json'));

      for (final pin in pins) {
        // daily_plans[].day is 1-based (= day_index + 1); slot_index is 0-based.
        final day = plan.dailyPlans.firstWhere((d) => d.day == pin.dayIndex + 1);
        final i = day.meals.indexWhere((m) => m.slotIndex == pin.slotIndex);
        expect(i, isNot(-1), reason: 'pin $pin has a meal in the plan');
        final meal = day.meals[i];
        expect(meal.source, Meal.sourcePinnedAssignment);
        expect(meal.recipeId, pin.recipeId);

        // The coordinate the detail sheet pins from is the same one.
        expect(
          MealPlanProvider.pinSlotFor(day.day, i, meal),
          (pin.dayIndex, pin.slotIndex),
        );
      }
    });
  });
}
