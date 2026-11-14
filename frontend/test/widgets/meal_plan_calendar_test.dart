import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/meal_card.dart';
import 'package:macrova/widgets/meal_plan_calendar.dart';

MealPlanDay _day({
  required int day,
  List<Map<String, dynamic>> meals = const [],
  Map<String, num>? totals,
}) {
  final plan = MealPlan.fromPlanApiV1Response({
    'success': true,
    'days': 1,
    'daily_plans': [
      {
        'day': day,
        'meals': meals,
        'totals': totals ??
            {
              'calories': 0,
              'protein_g': 0,
              'fat_g': 0,
              'carbs_g': 0,
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
  });
  return plan.dailyPlans.first;
}

Widget _wrap(Widget child) {
  return MaterialApp(
    theme: AppTheme.light,
    home: Scaffold(
      body: SingleChildScrollView(child: child),
    ),
  );
}

void main() {
  group('MealPlanCalendar', () {
    testWidgets(
      'Given multi-day plans, When rendered, '
      'Then day cells and first meal day detail appear',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final days = [
          _day(
            day: 1,
            meals: [
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
            totals: {
              'calories': 300,
              'protein_g': 10,
              'fat_g': 5,
              'carbs_g': 50,
            },
          ),
          _day(
            day: 2,
            meals: [
              {
                'meal_type': 'Lunch',
                'name': 'Salad',
                'nutrition': {
                  'calories': 400,
                  'protein_g': 20,
                  'fat_g': 15,
                  'carbs_g': 30,
                },
                'busyness_level': 2,
                'ingredients': ['lettuce'],
              },
            ],
            totals: {
              'calories': 400,
              'protein_g': 20,
              'fat_g': 15,
              'carbs_g': 30,
            },
          ),
          _day(day: 3),
        ];

        await tester.pumpWidget(_wrap(MealPlanCalendar(dailyPlans: days)));
        await tester.pumpAndSettle();

        expect(find.byKey(const ValueKey('meal-plan-calendar')), findsOneWidget);
        expect(find.byKey(const ValueKey('calendar-day-1')), findsOneWidget);
        expect(find.byKey(const ValueKey('calendar-day-2')), findsOneWidget);
        expect(find.byKey(const ValueKey('calendar-day-3')), findsOneWidget);
        expect(find.text('Oatmeal'), findsOneWidget);
        expect(find.byType(MealCard), findsOneWidget);

        await tester.tap(find.byKey(const ValueKey('calendar-day-2')));
        await tester.pumpAndSettle();

        expect(find.text('Salad'), findsOneWidget);
        expect(find.text('Oatmeal'), findsNothing);
      },
    );

    testWidgets(
      'Given empty meals across days, When rendered, '
      'Then shows honest empty copy',
      (tester) async {
        await tester.pumpWidget(
          _wrap(MealPlanCalendar(dailyPlans: [_day(day: 1), _day(day: 2)])),
        );
        await tester.pumpAndSettle();

        expect(find.text('No meals in this plan'), findsOneWidget);
        expect(find.byType(MealCard), findsNothing);
      },
    );
  });
}
