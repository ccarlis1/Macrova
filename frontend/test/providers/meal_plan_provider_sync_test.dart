import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/recipe_sync_result.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/services/api_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

MealPlan _plan({List<String> warnings = const []}) =>
    MealPlan.fromPlanApiV1Response({
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
      'warnings': warnings,
      'report': {'failures': <dynamic>[]},
    });

const _request = PlanRequest(
  dailyCalories: 2000,
  dailyProteinG: 150,
  dailyFatGMin: 50,
  dailyFatGMax: 70,
  schedule: {'07:00': 2},
);

const _recipes = [
  Recipe(id: 'r-1', name: 'Almond Bowl'),
  Recipe(id: 'r-2', name: 'Rice'),
];

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('MealPlanProvider pre-plan sync (FE-13)', () {
    test(
        'Given the sync rejects a recipe, Then the plan carries a warning '
        'naming it, ahead of the server warnings', () async {
      final provider = MealPlanProvider(
        recipeSyncFn: (batch) async => RecipeSyncResult(
          syncedIds: const ['r-2'],
          errors: [
            RecipeSyncError.parse(
              "r-1: INVALID_REQUEST: dietary flag 'vegan' is contradicted by "
              "ingredient(s) 'honey': remove the flag or the ingredient.",
              sent: batch,
            ),
          ],
        ),
        planFn: (_) async => _plan(warnings: const ['Sodium advisory.']),
      );

      await provider.generatePlanWithRecipeSync(
        recipesToSync: _recipes,
        request: _request,
      );

      expect(provider.error, isNull);
      final warnings = provider.mealPlan!.warnings;
      expect(warnings, hasLength(2));
      expect(warnings.first, contains('"Almond Bowl" was not synced'));
      expect(warnings.first, contains("dietary flag 'vegan'"));
      expect(warnings.last, 'Sodium advisory.');
    });

    test('Given a clean sync, Then the plan warnings are unchanged', () async {
      final provider = MealPlanProvider(
        recipeSyncFn: (batch) async =>
            RecipeSyncResult(syncedIds: [for (final r in batch) r.id]),
        planFn: (_) async => _plan(),
      );

      await provider.generatePlanWithRecipeSync(
        recipesToSync: _recipes,
        request: _request,
      );

      expect(provider.mealPlan!.warnings, isEmpty);
    });

    test('Given the whole sync fails, Then the plan is not requested',
        () async {
      var planned = false;
      final provider = MealPlanProvider(
        recipeSyncFn: (_) async => throw const ApiException(
          statusCode: 500,
          code: 'HTTP_ERROR',
          message: 'down',
        ),
        planFn: (_) async {
          planned = true;
          return _plan();
        },
      );

      await provider.generatePlanWithRecipeSync(
        recipesToSync: _recipes,
        request: _request,
      );

      expect(planned, isFalse);
      expect(provider.error, 'down');
    });
  });
}
