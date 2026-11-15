import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/meal_card.dart';
import 'package:macrova/widgets/meal_detail_sheet.dart';

import 'widget_test_helpers.dart';

// FE-14: batch variant of MealCard / MealDetailSheet.

Meal _meal({String? source, double? servings}) => Meal(
      mealType: 'Breakfast',
      recipe: const {'name': 'Overnight Oat Bowl'},
      nutrition: const NutritionProfile(
        calories: 413,
        proteinG: 17,
        fatG: 9,
        carbsG: 64,
      ),
      busynessLevel: 2,
      slotIndex: 0,
      source: source,
      batchId: source == Meal.sourceMealPrepBatch ? 'b1' : null,
      servings: servings,
    );

MealCard _card(Meal m) => MealCard(
      mealType: m.mealType,
      recipeName: m.recipe['name'] as String,
      calories: m.nutrition.calories,
      proteinG: m.nutrition.proteinG,
      carbsG: m.nutrition.carbsG,
      fatG: m.nutrition.fatG,
      source: m.source,
      servings: m.servings,
    );

Future<void> _openSheet(WidgetTester tester, Meal meal) async {
  tester.view.physicalSize = const Size(800, 1200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.light,
      home: Builder(
        builder: (context) => Scaffold(
          body: TextButton(
            onPressed: () => MealDetailSheet.show(
              context: context,
              meal: meal,
              day: 1,
              mealIndex: 0,
              isCooked: false,
              onToggleCooked: () {},
            ),
            child: const Text('Open'),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Open'));
  await tester.pumpAndSettle();
}

void main() {
  group('MealCard', () {
    testWidgets(
        'Given a meal_prep_batch meal with servings, Then the Meal prep badge '
        'and the serving count show (both themes)', (tester) async {
      await pumpBothThemes(
        tester,
        _card(_meal(source: Meal.sourceMealPrepBatch, servings: 1)),
        assertions: () {
          expect(find.byKey(MealCard.mealPrepBadgeKey), findsOneWidget);
          expect(find.text('Meal prep'), findsOneWidget);
          expect(find.byKey(MealCard.mealPrepServingsKey), findsOneWidget);
          expect(find.text('1 serving'), findsOneWidget);
        },
      );
    });

    testWidgets(
        'Given a batch meal without servings, Then only the badge shows',
        (tester) async {
      await tester.pumpWidget(
        wrapWidget(_card(_meal(source: Meal.sourceMealPrepBatch))),
      );
      expect(find.byKey(MealCard.mealPrepBadgeKey), findsOneWidget);
      expect(find.byKey(MealCard.mealPrepServingsKey), findsNothing);
    });

    for (final source in [Meal.sourcePlanner, null]) {
      testWidgets('Given a $source meal, Then it looks unchanged (no badge)',
          (tester) async {
        await tester.pumpWidget(
          wrapWidget(_card(_meal(source: source, servings: 2))),
        );
        expect(find.text('Overnight Oat Bowl'), findsOneWidget);
        expect(find.byKey(MealCard.mealPrepBadgeKey), findsNothing);
        expect(find.byKey(MealCard.mealPrepServingsKey), findsNothing);
        expect(find.text('Meal prep'), findsNothing);
      });
    }
  });

  group('MealDetailSheet', () {
    testWidgets(
        'Given a batch meal, Then the sheet shows it comes from a meal-prep '
        'batch with its servings', (tester) async {
      await _openSheet(
        tester,
        _meal(source: Meal.sourceMealPrepBatch, servings: 2),
      );
      expect(find.byKey(MealDetailSheet.mealPrepKey), findsOneWidget);
      expect(find.text('From a meal-prep batch · 2 servings'), findsOneWidget);
    });

    testWidgets('Given a planner meal, Then no batch row shows', (tester) async {
      await _openSheet(tester, _meal(source: Meal.sourcePlanner));
      expect(find.byKey(MealDetailSheet.mealPrepKey), findsNothing);
      expect(find.text('Mark cooked'), findsOneWidget);
    });
  });
}
