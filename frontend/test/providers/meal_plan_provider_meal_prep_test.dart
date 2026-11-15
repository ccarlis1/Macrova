import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/meal_prep_batch.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/services/api_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../widgets/meal_prep_test_helpers.dart';

// FE-14: batch state on MealPlanProvider (server-owned list, no client store).

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test(
      'Given a plan from generatePlan, When a batch is created, Then the list '
      'reloads and the same request is re-run', () async {
    final server = FakeMealPrepServer();
    final plan = server.provider();
    await plan.generatePlan(planRequest);
    server.planRequests.clear();

    final reran = await plan.createMealPrepBatch(
      recipeId: 'fe14-oat-bowl',
      totalServings: 2,
      cookDate: '2026-11-14',
      assignments: const [MealPrepAssignment(dayIndex: 0, slotIndex: 0)],
    );

    expect(reran, isTrue);
    expect(plan.mealPrepBatches.single.id, 'b1');
    expect(server.planRequests.single.toJson(), planRequest.toJson());
    // The request never carries batches: the server reads its own.
    expect(server.planRequests.single.toJson().containsKey('active_batches'),
        isFalse);
  });

  test(
      'Given a plan from plan-from-text (no last request), When a batch is '
      'created, Then nothing is re-run', () async {
    final server = FakeMealPrepServer();
    final plan = server.provider()..applyPlanResult(twoDayPlan());

    final reran = await plan.createMealPrepBatch(
      recipeId: 'fe14-oat-bowl',
      totalServings: 2,
      cookDate: '2026-11-14',
      assignments: const [MealPrepAssignment(dayIndex: 1, slotIndex: 0)],
    );

    expect(reran, isFalse);
    expect(server.planRequests, isEmpty);
    expect(plan.mealPrepBatches, hasLength(1));
  });

  test(
      'Given a rejected create, Then ApiException propagates and nothing is '
      'reloaded or re-run', () async {
    final server = FakeMealPrepServer()
      ..createError = const ApiException(
        statusCode: 409,
        code: 'BATCH_CONFLICT',
        message: 'Slot conflict',
      );
    final plan = server.provider();
    await plan.generatePlan(planRequest);
    server.planRequests.clear();

    await expectLater(
      plan.createMealPrepBatch(
        recipeId: 'x',
        totalServings: 2,
        cookDate: '2026-11-14',
        assignments: const [MealPrepAssignment(dayIndex: 0, slotIndex: 0)],
      ),
      throwsA(isA<ApiException>()
          .having((e) => e.code, 'code', 'BATCH_CONFLICT')),
    );
    expect(server.listCalls, 0);
    expect(server.planRequests, isEmpty);
  });

  test('a failed list keeps the server code and the previous list', () async {
    final server = FakeMealPrepServer(
      batches: MealPrepBatch.listFromResponse(
        fixtureJson('meal_prep_batches_list.json'),
      ),
    );
    final plan = server.provider();
    await plan.loadMealPrepBatches();
    server.listError = const ApiException(
      statusCode: 500,
      code: 'INTERNAL_ERROR',
      message: 'boom',
    );

    await plan.loadMealPrepBatches();

    expect(plan.mealPrepBatches, hasLength(1));
    expect(plan.mealPrepErrorCode, 'INTERNAL_ERROR');
    expect(plan.mealPrepErrorMessage, 'boom');
    expect(plan.mealPrepLoading, isFalse);
  });

  test(
      'planSlotOptions lists planned meals and slot failures, 0-based and '
      'sorted', () {
    final plan = FakeMealPrepServer().provider()
      ..applyPlanResult(MealPlan.fromPlanApiV1Response({
        'success': false,
        'plan_status': 'partial',
        'days': 2,
        'daily_plans': [
          {
            'day': 2,
            'meals': [
              {
                'meal_type': 'Lunch',
                'name': 'Soup',
                'slot_index': 1,
                'nutrition': {
                  'calories': 1,
                  'protein_g': 1,
                  'fat_g': 1,
                  'carbs_g': 1,
                },
              },
            ],
          },
        ],
        'goals': {
          'daily_calories': 2000,
          'daily_protein_g': 150.0,
          'daily_fat_g_min': 50.0,
          'daily_fat_g_max': 70.0,
          'daily_carbs_g': 200.0,
        },
        'warnings': <String>[],
        'report': {
          'failures': [
            {'code': 'FM-1', 'message': 'x', 'day_index': 1, 'slot_index': 0},
            {'code': 'FM-1', 'message': 'y', 'day_index': 0, 'slot_index': 2},
          ],
        },
      }));

    final options = plan.planSlotOptions;
    expect(
      options.map((o) => (o.dayIndex, o.slotIndex, o.label)),
      [(0, 2, null), (1, 0, null), (1, 1, 'Lunch · Soup')],
    );
    expect(options.last.day, 2);
  });

  test('no plan, no slot options', () {
    expect(FakeMealPrepServer().provider().planSlotOptions, isEmpty);
  });
}
