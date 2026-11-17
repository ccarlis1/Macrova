import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:macrova/models/meal_prep_batch.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/services/api_service.dart';

// FE-14: `/api/v1/meal_prep_batches` client and DTO, against responses captured
// in-process from the committed backend (see test/fixtures/README.md).

String _fixture(String name) =>
    File('test/fixtures/$name').readAsStringSync();

Map<String, dynamic> _json(String name) =>
    jsonDecode(_fixture(name)) as Map<String, dynamic>;

void main() {
  group('MealPrepBatch DTO', () {
    test('Given the captured list response, Then every field parses', () {
      final list =
          MealPrepBatch.listFromResponse(_json('meal_prep_batches_list.json'));

      expect(list, hasLength(1));
      final b = list.single;
      expect(b.id, 'bbd7defaac1442ea8dee5152c2311e89');
      expect(b.recipeId, 'fe14-oat-bowl');
      expect(b.totalServings, 3);
      expect(b.assignedServings, 2.0);
      expect(b.remainingServings, 1.0);
      expect(b.cookDate, '2026-11-14');
      expect(b.status, 'active');
      expect(b.assignments.map((a) => (a.dayIndex, a.slotIndex)), [
        (0, 0),
        (1, 0),
      ]);
      expect(b.assignments.last.date, '2026-11-15');
      expect(b.assignments.last.slotId, 0);
    });

    test('Given a list response without batches, Then it is a FormatException',
        () {
      expect(
        () => MealPrepBatch.listFromResponse({'items': []}),
        throwsFormatException,
      );
    });

    test('a request assignment is canonical only (no date / slot_id)', () {
      const a = MealPrepAssignment(
        dayIndex: 1,
        slotIndex: 2,
        date: '2026-11-15',
        slotId: 2,
      );
      expect(a.toRequestJson(), {'day_index': 1, 'slot_index': 2, 'servings': 1.0});
    });

    test('servingsLabel', () {
      expect(servingsLabel(1), '1 serving');
      expect(servingsLabel(2.0), '2 servings');
      expect(servingsLabel(1.5), '1.5 servings');
    });
  });

  group('ApiService meal-prep routes', () {
    test(
        'Given active=true, When listing, Then GET carries ?active=true and the '
        'batches parse', () async {
      late Uri seen;
      final client = MockClient((req) async {
        seen = req.url;
        expect(req.method, 'GET');
        return http.Response(_fixture('meal_prep_batches_list.json'), 200);
      });

      final list = await ApiService.listMealPrepBatches(client: client);

      expect(seen.path, '/api/v1/meal_prep_batches');
      expect(seen.queryParameters, {'active': 'true'});
      expect(list.single.recipeId, 'fe14-oat-bowl');
    });

    test('When creating, Then the body is the server request shape', () async {
      late Map<String, dynamic> body;
      final client = MockClient((req) async {
        expect(req.method, 'POST');
        expect(req.url.path, '/api/v1/meal_prep_batches');
        body = jsonDecode(req.body) as Map<String, dynamic>;
        return http.Response(_fixture('meal_prep_batch_created.json'), 200);
      });

      final created = await ApiService.createMealPrepBatch(
        recipeId: 'fe14-oat-bowl',
        totalServings: 3,
        cookDate: '2026-11-14',
        assignments: const [
          MealPrepAssignment(dayIndex: 0, slotIndex: 0),
          MealPrepAssignment(dayIndex: 1, slotIndex: 0),
        ],
        client: client,
      );

      expect(body, {
        'recipe_id': 'fe14-oat-bowl',
        'total_servings': 3,
        'cook_date': '2026-11-14',
        'assignments': [
          {'day_index': 0, 'slot_index': 0, 'servings': 1.0},
          {'day_index': 1, 'slot_index': 0, 'servings': 1.0},
        ],
      });
      expect(created.id, 'bbd7defaac1442ea8dee5152c2311e89');
      expect(created.remainingServings, 1.0);
    });

    for (final (fixture, status, code) in [
      ('meal_prep_error_conflict.json', 409, 'BATCH_CONFLICT'),
      ('meal_prep_error_not_batchable.json', 422, 'RECIPE_NOT_BATCHABLE'),
    ]) {
      test('Given a $status $code response, Then ApiException carries the code',
          () async {
        final client =
            MockClient((_) async => http.Response(_fixture(fixture), status));

        final call = ApiService.createMealPrepBatch(
          recipeId: 'fe14-oat-bowl',
          totalServings: 2,
          cookDate: '2026-11-14',
          assignments: const [MealPrepAssignment(dayIndex: 0, slotIndex: 0)],
          client: client,
        );

        await expectLater(
          call,
          throwsA(
            isA<ApiException>()
                .having((e) => e.code, 'code', code)
                .having((e) => e.statusCode, 'statusCode', status)
                .having((e) => e.message, 'message',
                    _json(fixture)['error']['message']),
          ),
        );
      });
    }

    test('When cancelling, Then DELETE returns the cancelled id', () async {
      final client = MockClient((req) async {
        expect(req.method, 'DELETE');
        expect(req.url.path, '/api/v1/meal_prep_batches/b%201');
        return http.Response(jsonEncode({'cancelled_id': 'b 1'}), 200);
      });

      expect(await ApiService.cancelMealPrepBatch('b 1', client: client), 'b 1');
    });

    test('Given an unknown id, Then cancel throws NOT_FOUND', () async {
      final client = MockClient(
        (_) async => http.Response(
          jsonEncode({
            'error': {'code': 'NOT_FOUND', 'message': "No meal prep batch"},
          }),
          404,
        ),
      );

      await expectLater(
        ApiService.cancelMealPrepBatch('nope', client: client),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', 'NOT_FOUND')),
      );
    });
  });

  group('Index bases (REQUIRES_VERIFICATION, FE-14)', () {
    test(
        'Given a batch created at (0, 0), Then the plan response puts it on '
        'the first meal of day 1', () {
      // Captured in sequence: create (0,0)+(1,0), then POST /plan (2 days).
      final batch = MealPrepBatch.fromJson(_json('meal_prep_batch_created.json'));
      final plan = MealPlan.fromPlanApiV1Response(
        _json('plan_with_meal_prep_batch.json'),
      );

      final first = batch.assignments.first;
      expect((first.dayIndex, first.slotIndex), (0, 0));

      // daily_plans[].day is 1-based (= day_index + 1); slot_index is 0-based.
      final day1 = plan.dailyPlans.firstWhere((d) => d.day == first.dayIndex + 1);
      final meal = day1.meals.firstWhere((m) => m.slotIndex == first.slotIndex);
      expect(day1.day, 1);
      expect(meal.slotIndex, 0);
      expect(meal.isMealPrepBatch, isTrue);
      expect(meal.source, Meal.sourceMealPrepBatch);
      expect(meal.batchId, batch.id);
      expect(meal.recipeId, batch.recipeId);
      expect(meal.servings, 1.0);

      // The (1, 0) assignment is day 2's first meal.
      final day2 = plan.dailyPlans.firstWhere((d) => d.day == 2);
      expect(day2.meals.first.slotIndex, 0);
      expect(day2.meals.first.batchId, batch.id);
    });
  });
}
