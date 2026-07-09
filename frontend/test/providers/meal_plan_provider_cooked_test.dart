import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/services/api_service.dart';
import 'package:macrova/services/storage_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

MealPlan _samplePlan() {
  return MealPlan.fromPlanApiV1Response({
    'success': true,
    'plan_status': 'success',
    'days': 1,
    'daily_plans': [
      {
        'day': 1,
        'meals': [
          {
            'meal_type': 'Breakfast',
            'name': 'Oatmeal',
            'nutrition': {
              'calories': 300,
              'protein_g': 10,
              'fat_g': 5,
              'carbs_g': 50,
            },
            'busyness_level': 2,
            'ingredients': ['oats'],
          },
        ],
        'totals': {
          'calories': 300,
          'protein_g': 10,
          'fat_g': 5,
          'carbs_g': 50,
        },
      },
    ],
    'goals': {
      'daily_calories': 2000,
      'daily_protein_g': 150.0,
      'daily_fat_g_min': 50.0,
      'daily_fat_g_max': 70.0,
      'daily_carbs_g': 200.0,
    },
    'report': {'failures': <dynamic>[]},
  });
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('MealPlanProvider cooked slots', () {
    test(
      'Given a slot toggle, When persisted and reloaded, Then isCooked reflects it',
      () async {
        final provider = MealPlanProvider();
        await provider.load();

        expect(provider.isCooked(1, 0), isFalse);
        provider.toggleCooked(1, 0);
        expect(provider.isCooked(1, 0), isTrue);

        final reloaded = MealPlanProvider();
        await reloaded.load();
        expect(reloaded.isCooked(1, 0), isTrue);
        expect(
          await StorageService.loadCookedSlots(),
          contains(MealPlanProvider.cookedSlotKey(1, 0)),
        );
      },
    );

    test(
      'Given cooked slots, When applyPlanResult succeeds, Then cooked set is cleared',
      () async {
        final provider = MealPlanProvider();
        await provider.load();
        provider.toggleCooked(1, 0);
        provider.toggleCooked(2, 1);
        expect(provider.cookedSlots, isNotEmpty);

        provider.applyPlanResult(_samplePlan());

        expect(provider.isCooked(1, 0), isFalse);
        expect(provider.cookedSlots, isEmpty);
        expect(await StorageService.loadCookedSlots(), isEmpty);
      },
    );

    test(
      'Given cooked slots, When clearPlan is called, Then cooked set is cleared',
      () async {
        final provider = MealPlanProvider();
        await provider.load();
        provider.applyPlanResult(_samplePlan());
        provider.toggleCooked(1, 0);
        expect(provider.cookedSlots, isNotEmpty);

        provider.clearPlan();
        await Future<void>.delayed(Duration.zero);

        expect(provider.mealPlan, isNull);
        expect(provider.cookedSlots, isEmpty);
        expect(await StorageService.loadCookedSlots(), isEmpty);
      },
    );
  });

  group('MealPlanProvider errorCode', () {
    test(
      'Given ApiException, When mapped, Then errorCode and errorMessage are set',
      () {
        final provider = MealPlanProvider();
        provider.debugSetError(
          const ApiException(
            statusCode: 400,
            code: 'FM-TAG-EMPTY',
            message: 'No recipes match tags',
          ),
        );

        expect(provider.errorCode, 'FM-TAG-EMPTY');
        expect(provider.errorMessage, 'No recipes match tags');
        expect(provider.error, 'No recipes match tags');
      },
    );

    test(
      'Given non-ApiException, When mapped, Then errorCode is null',
      () {
        final provider = MealPlanProvider();
        provider.debugSetError(Exception('network down'));

        expect(provider.errorCode, isNull);
        expect(provider.errorMessage, contains('network down'));
        expect(provider.error, contains('network down'));
      },
    );
  });
}
