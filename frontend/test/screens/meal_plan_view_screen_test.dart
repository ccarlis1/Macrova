import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/screens/meal_plan_view_screen.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/advisory_card.dart';
import 'package:macrova/widgets/failure_panel.dart';
import 'package:macrova/widgets/meal_plan_calendar.dart';
import 'package:provider/provider.dart';

const _goals = {
  'daily_calories': 2000,
  'daily_protein_g': 150.0,
  'daily_fat_g_min': 50.0,
  'daily_fat_g_max': 70.0,
  'daily_carbs_g': 200.0,
};

MealPlan _successWithWarningsPlan() {
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
    'goals': _goals,
    'warnings': ['Sodium advisory: weekly total high'],
    'report': {'failures': <dynamic>[]},
  });
}

MealPlan _multiDayPlan() {
  return MealPlan.fromPlanApiV1Response({
    'success': true,
    'plan_status': 'success',
    'days': 3,
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
      {
        'day': 2,
        'meals': [
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
        'totals': {
          'calories': 400,
          'protein_g': 20,
          'fat_g': 15,
          'carbs_g': 30,
        },
      },
      {
        'day': 3,
        'meals': const [],
        'totals': {
          'calories': 0,
          'protein_g': 0,
          'fat_g': 0,
          'carbs_g': 0,
        },
      },
    ],
    'goals': _goals,
    'warnings': const [],
    'report': {'failures': <dynamic>[]},
  });
}

MealPlan _actionableFailurePlan() {
  return MealPlan.fromPlanApiV1Response({
    'success': false,
    'termination_code': 'TC-2',
    'plan_status': 'failed',
    'days': 1,
    'daily_plans': const [],
    'goals': _goals,
    'warnings': const [],
    'report': {
      'failures': [
        {
          'code': 'FM-MACRO-INFEASIBLE',
          'message': 'No feasible plan for macro targets',
          'details': <String, dynamic>{},
          'fix_hint': 'Relax protein or calorie targets',
        },
      ],
    },
  });
}

MealPlan _partialPlan() {
  return MealPlan.fromPlanApiV1Response({
    'success': false,
    'termination_code': 'TC-2',
    'plan_status': 'partial',
    'plan_status_message': 'Only day 1 could be filled',
    'days': 1,
    'daily_plans': [
      {
        'day': 1,
        'meals': [
          {
            'meal_type': 'Breakfast',
            'name': 'Partial Oats',
            'nutrition': {
              'calories': 280,
              'protein_g': 12,
              'fat_g': 6,
              'carbs_g': 40,
            },
            'busyness_level': 2,
            'ingredients': ['oats'],
          },
        ],
        'totals': {
          'calories': 280,
          'protein_g': 12,
          'fat_g': 6,
          'carbs_g': 40,
        },
      },
    ],
    'goals': _goals,
    'warnings': const [],
    'report': {
      'failures': [
        {
          'code': 'FM-MACRO-INFEASIBLE',
          'message': 'Could not fill remaining slots',
          'details': <String, dynamic>{},
          'fix_hint': 'Widen the recipe pool',
        },
      ],
    },
  });
}

Widget _wrap(MealPlanProvider mealPlan) {
  return MaterialApp(
    theme: AppTheme.light,
    home: MultiProvider(
      providers: [
        ChangeNotifierProvider<ProfileProvider>(
          create: (_) => ProfileProvider(),
        ),
        ChangeNotifierProvider<MealPlanProvider>.value(value: mealPlan),
      ],
      child: const Scaffold(body: MealPlanViewScreen()),
    ),
  );
}

void main() {
  group('MealPlanViewScreen outcome split', () {
    testWidgets(
      'Given a successful plan with warnings, When rendered, '
      'Then an advisory (not a failure panel) is shown',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final provider = MealPlanProvider()
          ..applyPlanResult(_successWithWarningsPlan());

        await tester.pumpWidget(_wrap(provider));
        await tester.pumpAndSettle();

        expect(find.text('Advisories'), findsOneWidget);
        expect(find.byType(AdvisoryCard), findsOneWidget);
        expect(find.byType(FailurePanel), findsNothing);
      },
    );

    testWidgets(
      'Given an infeasible plan, When rendered, '
      'Then a failure panel shows FM code and fix_hint',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final provider = MealPlanProvider()
          ..applyPlanResult(_actionableFailurePlan());

        await tester.pumpWidget(_wrap(provider));
        await tester.pumpAndSettle();

        expect(find.byType(FailurePanel), findsOneWidget);
        expect(find.text('FM-MACRO-INFEASIBLE'), findsOneWidget);
        expect(find.text('Relax protein or calorie targets'), findsOneWidget);
        expect(find.text('TC-2'), findsNothing);
        expect(find.byType(AdvisoryCard), findsNothing);
        expect(find.text('Advisories'), findsNothing);
      },
    );

    testWidgets(
      'Given a partial plan, When rendered, '
      'Then meals and FailurePanel are both visible',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final provider = MealPlanProvider()..applyPlanResult(_partialPlan());

        await tester.pumpWidget(_wrap(provider));
        await tester.pumpAndSettle();

        expect(find.text('Partial Oats'), findsOneWidget);
        expect(find.byType(FailurePanel), findsOneWidget);
        expect(find.text('FM-MACRO-INFEASIBLE'), findsOneWidget);
        expect(find.text('Widen the recipe pool'), findsOneWidget);
      },
    );

    testWidgets(
      'Given a plan meal card, When tapped, Then MealDetailSheet opens with Mark cooked only',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final provider = MealPlanProvider()
          ..applyPlanResult(_successWithWarningsPlan());

        await tester.pumpWidget(_wrap(provider));
        await tester.pumpAndSettle();

        await tester.tap(find.text('Oatmeal'));
        await tester.pumpAndSettle();

        expect(find.text('Mark cooked'), findsOneWidget);
        expect(find.text('This device only'), findsOneWidget);
        expect(find.text('Pin'), findsNothing);
        expect(find.text('Swap'), findsNothing);
      },
    );
  });

  group('MealPlanViewScreen calendar toggle', () {
    testWidgets(
      'Given a multi-day plan, When Calendar is selected, '
      'Then the plan-horizon grid replaces the placeholder',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final provider = MealPlanProvider()..applyPlanResult(_multiDayPlan());

        await tester.pumpWidget(_wrap(provider));
        await tester.pumpAndSettle();

        expect(find.text('Calendar view coming soon'), findsNothing);
        expect(find.byType(MealPlanCalendar), findsNothing);

        await tester.tap(find.text('Calendar'));
        await tester.pumpAndSettle();

        expect(find.text('Calendar view coming soon'), findsNothing);
        expect(find.byType(MealPlanCalendar), findsOneWidget);
        expect(find.byKey(const ValueKey('calendar-day-1')), findsOneWidget);
        expect(find.byKey(const ValueKey('calendar-day-2')), findsOneWidget);
        expect(find.byKey(const ValueKey('calendar-day-3')), findsOneWidget);
        expect(find.text('Oatmeal'), findsOneWidget);
      },
    );

    testWidgets(
      'Given success-with-warnings, When Calendar is selected, '
      'Then advisories remain visible',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final provider = MealPlanProvider()
          ..applyPlanResult(_successWithWarningsPlan());

        await tester.pumpWidget(_wrap(provider));
        await tester.pumpAndSettle();

        await tester.tap(find.text('Calendar'));
        await tester.pumpAndSettle();

        expect(find.byType(MealPlanCalendar), findsOneWidget);
        expect(find.byType(AdvisoryCard), findsOneWidget);
        expect(find.byType(FailurePanel), findsNothing);
      },
    );

    testWidgets(
      'Given an actionable failure with empty daily_plans, When Calendar is selected, '
      'Then FailurePanel remains visible',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final provider = MealPlanProvider()
          ..applyPlanResult(_actionableFailurePlan());

        await tester.pumpWidget(_wrap(provider));
        await tester.pumpAndSettle();

        await tester.tap(find.text('Calendar'));
        await tester.pumpAndSettle();

        expect(find.byType(MealPlanCalendar), findsOneWidget);
        expect(find.text('No meals in this plan'), findsOneWidget);
        expect(find.byType(FailurePanel), findsOneWidget);
        expect(find.text('FM-MACRO-INFEASIBLE'), findsOneWidget);
        expect(find.text('Relax protein or calorie targets'), findsOneWidget);
      },
    );
  });
}
