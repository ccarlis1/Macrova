import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/widgets/meal_card.dart';

void main() {
  group('Meal.mealTypeMatch parsing', () {
    test('fromPlanApiV1 reads meal_type_match true/false/null', () {
      final matched = Meal.fromPlanApiV1({
        'name': 'Oats',
        'meal_type': 'breakfast',
        'meal_type_match': true,
        'cooking_time_minutes': 10,
        'ingredients': <String>['oats'],
        'nutrition': {
          'calories': 300.0,
          'protein_g': 20.0,
          'fat_g': 8.0,
          'carbs_g': 40.0,
        },
        'busyness_level': 2,
      });
      expect(matched.mealTypeMatch, isTrue);

      final mismatched = Meal.fromPlanApiV1({
        'name': 'Steak',
        'meal_type': 'breakfast',
        'meal_type_match': false,
        'cooking_time_minutes': 20,
        'ingredients': <String>['beef'],
        'nutrition': {
          'calories': 500.0,
          'protein_g': 40.0,
          'fat_g': 20.0,
          'carbs_g': 10.0,
        },
        'busyness_level': 3,
      });
      expect(mismatched.mealTypeMatch, isFalse);

      final unknown = Meal.fromPlanApiV1({
        'name': 'Mystery',
        'meal_type': 'meal',
        'cooking_time_minutes': 5,
        'ingredients': <String>['rice'],
        'nutrition': {
          'calories': 200.0,
          'protein_g': 5.0,
          'fat_g': 2.0,
          'carbs_g': 40.0,
        },
        'busyness_level': 1,
      });
      expect(unknown.mealTypeMatch, isNull);
    });
  });

  group('MealCard mismatch chip', () {
    testWidgets('shows chip when mealTypeMatch is false', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: MealCard(
              mealType: 'breakfast',
              recipeName: 'Steak',
              calories: 500,
              proteinG: 40,
              carbsG: 10,
              fatG: 20,
              mealTypeMatch: false,
            ),
          ),
        ),
      );
      expect(find.text('Not tagged as breakfast'), findsOneWidget);
    });

    testWidgets('hides chip when mealTypeMatch is true or null', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: MealCard(
              mealType: 'breakfast',
              recipeName: 'Oats',
              calories: 300,
              proteinG: 20,
              carbsG: 40,
              fatG: 8,
              mealTypeMatch: true,
            ),
          ),
        ),
      );
      expect(find.textContaining('Not tagged as'), findsNothing);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: MealCard(
              mealType: 'breakfast',
              recipeName: 'Oats',
              calories: 300,
              proteinG: 20,
              carbsG: 40,
              fatG: 8,
            ),
          ),
        ),
      );
      expect(find.textContaining('Not tagged as'), findsNothing);
    });
  });
}
