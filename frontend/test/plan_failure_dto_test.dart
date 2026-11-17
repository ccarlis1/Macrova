import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';

Map<String, dynamic> _fixture(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync())
        as Map<String, dynamic>;

void main() {
  group('PlanFailure / PlanFailureCause DTOs (FE-11)', () {
    test(
      'Given a real /api/v1/plan recipe-gap failure, When parsed, '
      'Then explanation, fix, cause and failure_cause are populated',
      () {
        final plan = MealPlan.fromPlanApiV1Response(
          _fixture('plan_failure_recipe_gap.json'),
        );

        expect(plan.planStatus, 'partial');
        expect(plan.failures, hasLength(1));
        final f = plan.failures.single;
        expect(f.code, 'FM-4');
        expect(
          f.message,
          'Weekly micronutrient targets are infeasible with current constraints.',
        );
        expect(
          f.explanation,
          "The available recipes can't provide enough omega 3 and omega 6 over the plan.",
        );
        expect(f.fix, 'Add recipes rich in omega 3 and omega 6, or lower those goals.');
        expect(f.cause, 'nutrient_gap');
        expect(f.fixHint, isNotNull);
        expect(f.dayIndex, isNull);
        expect(f.slotIndex, isNull);
        expect(f.isSlotFailure, isFalse);

        final fc = plan.failureCause!;
        expect(fc.cause, 'nutrient_gap');
        expect(fc.recipeCouldHelp, isTrue);
        final gap = fc.recipeGap!;
        expect(gap.perMealCalories, 800.0);
        expect(gap.perMealProteinG, 50.0);
        expect(gap.perMealFatGMax, 33.3);
        expect(gap.perMealCarbsG, 93.8);
        // Absent from this response (exclude-none on the server): null, not 0.
        expect(gap.cookTimeCapMinutes, isNull);
        expect(gap.excludedIngredients, contains('peanuts'));
        expect(gap.nutrientMinPerRecipe.keys, ['omega_3_g', 'omega_6_g']);
        expect(gap.mealTypes, ['breakfast', 'lunch', 'dinner']);
        expect(gap.slots, isEmpty);
      },
    );

    test(
      'Given a real impossible-targets failure, When parsed, '
      'Then recipe_could_help is false and recipe_gap is null',
      () {
        final plan = MealPlan.fromPlanApiV1Response(
          _fixture('plan_failure_impossible_targets.json'),
        );

        expect(plan.planStatus, 'failed');
        expect(plan.failures.single.cause, 'IMPOSSIBLE_TARGETS');
        expect(plan.failures.single.explanation, startsWith('Your daily targets'));
        expect(plan.failureCause!.recipeCouldHelp, isFalse);
        expect(plan.failureCause!.recipeGap, isNull);
      },
    );

    test(
      'Given unknown keys and missing optional fields, When parsed, '
      'Then unknown keys are ignored and missing fields are null',
      () {
        final f = PlanFailure.fromJson({
          'code': 'FM-1',
          'message': 'No candidates',
          'day_index': 0,
          'slot_index': 2,
          'some_future_field': {'x': 1},
        });
        expect(f.explanation, isNull);
        expect(f.fix, isNull);
        expect(f.cause, isNull);
        expect(f.fixHint, isNull);
        expect(f.isSlotFailure, isTrue);

        final fc = PlanFailureCause.fromJson({
          'recipe_could_help': true,
          'recipe_gap': {
            'per_meal_protein_g': 40,
            'slots': [
              [0, 2],
            ],
            'unknown': 'ignored',
          },
          'also_unknown': 1,
        });
        expect(fc.cause, isNull);
        expect(fc.recipeGap!.perMealProteinG, 40.0);
        expect(fc.recipeGap!.perMealCalories, isNull);
        expect(fc.recipeGap!.cookTimeCapMinutes, isNull);
        expect(fc.recipeGap!.excludedIngredients, isEmpty);
        expect(fc.recipeGap!.nutrientMinPerRecipe, isEmpty);
        expect(fc.recipeGap!.slots, [
          [0, 2],
        ]);
      },
    );

    test(
      'Given a report without failure_cause (old server or success), When parsed, '
      'Then MealPlan.failureCause is null',
      () {
        final json = _fixture('plan_failure_recipe_gap.json');
        (json['report'] as Map).remove('failure_cause');
        final plan = MealPlan.fromPlanApiV1Response(json);
        expect(plan.failureCause, isNull);
        expect(plan.failures, hasLength(1));
      },
    );
  });

  group('PlanRequest.withPlanningMode', () {
    test('keeps every field and swaps planning_mode', () {
      const req = PlanRequest(
        dailyCalories: 2000,
        dailyProteinG: 150,
        dailyFatGMin: 50,
        dailyFatGMax: 70,
        days: 3,
        allergies: ['peanuts'],
        maxDailyCalories: 2200,
        planningMode: 'deterministic',
        recipeIds: ['r1'],
        cuisine: ['italian'],
        costLevel: 'cheap',
      );
      final json = req.toJson();
      final assisted = req.withPlanningMode('assisted').toJson();
      expect(assisted['planning_mode'], 'assisted');
      expect(
        Map.of(assisted)..remove('planning_mode'),
        Map.of(json)..remove('planning_mode'),
      );
    });
  });
}
