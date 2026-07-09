import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/meal_detail_sheet.dart';
import 'package:macrova/widgets/sticky_cta.dart';

Meal _meal() {
  return const Meal(
    mealType: 'Breakfast',
    recipe: {'name': 'Oatmeal'},
    nutrition: NutritionProfile(
      calories: 300,
      proteinG: 10,
      fatG: 5,
      carbsG: 50,
    ),
    busynessLevel: 2,
  );
}

void main() {
  group('MealDetailSheet', () {
    testWidgets(
      'Given a meal, When shown, Then Mark cooked is present and Pin/Swap are not',
      (tester) async {
        tester.view.physicalSize = const Size(800, 1200);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        var toggled = false;

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light,
            home: Builder(
              builder: (context) {
                return Scaffold(
                  body: TextButton(
                    onPressed: () {
                      MealDetailSheet.show(
                        context: context,
                        meal: _meal(),
                        day: 1,
                        mealIndex: 0,
                        isCooked: false,
                        onToggleCooked: () => toggled = true,
                      );
                    },
                    child: const Text('Open'),
                  ),
                );
              },
            ),
          ),
        );

        await tester.tap(find.text('Open'));
        await tester.pumpAndSettle();

        expect(find.text('Oatmeal'), findsOneWidget);
        expect(find.text('Mark cooked'), findsOneWidget);
        expect(find.text('This device only'), findsOneWidget);
        expect(find.text('Pin'), findsNothing);
        expect(find.text('Swap'), findsNothing);
        expect(find.byType(StickyCta), findsOneWidget);

        await tester.tap(find.text('Mark cooked'));
        await tester.pumpAndSettle();

        expect(toggled, isTrue);
        expect(find.text('Mark cooked'), findsNothing);
      },
    );

    testWidgets(
      'Given cooked meal, When shown, Then Mark not cooked label is used',
      (tester) async {
        tester.view.physicalSize = const Size(800, 1200);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light,
            home: Builder(
              builder: (context) {
                return Scaffold(
                  body: TextButton(
                    onPressed: () {
                      MealDetailSheet.show(
                        context: context,
                        meal: _meal(),
                        day: 1,
                        mealIndex: 0,
                        isCooked: true,
                        onToggleCooked: () {},
                      );
                    },
                    child: const Text('Open'),
                  ),
                );
              },
            ),
          ),
        );

        await tester.tap(find.text('Open'));
        await tester.pumpAndSettle();

        expect(find.text('Mark not cooked'), findsOneWidget);
        expect(find.text('Marked cooked'), findsOneWidget);
      },
    );
  });
}
