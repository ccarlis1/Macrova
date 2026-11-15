import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/profile_pin.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/meal_plan_view_screen.dart';
import 'package:macrova/screens/planner_config_screen.dart';
import 'package:macrova/services/api_service.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/macrova_chip.dart';
import 'package:macrova/widgets/meal_card.dart';
import 'package:macrova/widgets/planner/pinned_meals_section.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../pin_test_helpers.dart';

// FE-15: Planner Config pin count + "Clear pins", and pin badges on Meal Plan
// View fed from MealPlanProvider's server pins.

Widget _screen(MealPlanProvider plan, Widget child) {
  final profile = ProfileProvider();
  return MultiProvider(
    providers: [
      ChangeNotifierProvider<ProfileProvider>.value(value: profile),
      ChangeNotifierProvider<LlmConfigProvider>.value(
        value: LlmConfigProvider(profile),
      ),
      ChangeNotifierProvider<RecipeProvider>.value(value: RecipeProvider()),
      ChangeNotifierProvider<MealPlanProvider>.value(value: plan),
    ],
    child: MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(body: child),
    ),
  );
}

void _bigView(WidgetTester tester) {
  tester.view.physicalSize = const Size(1000, 3200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

String _countText(WidgetTester tester) =>
    tester.widget<Text>(find.byKey(PinnedMealsSection.countKey)).data!;

const _twoPins = [
  ProfilePin(dayIndex: 0, slotIndex: 1, recipeId: 'recipe_001'),
  ProfilePin(dayIndex: 1, slotIndex: 0, recipeId: 'recipe_002'),
];

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('Planner Config pinned meals', () {
    testWidgets(
        'Given two server pins, When Planner Config opens, Then it fetches and '
        'shows the pin count', (tester) async {
      _bigView(tester);
      final server = FakePinServer(pins: _twoPins);

      await tester.pumpWidget(
        _screen(server.provider(), const PlannerConfigScreen()),
      );
      await tester.pumpAndSettle();

      expect(server.listCalls, 1);
      expect(find.byType(PinnedMealsSection), findsOneWidget);
      expect(_countText(tester), '2 pinned meals');
    });

    testWidgets(
        'Given pins, When Clear pins is dismissed, Then nothing is cleared; '
        'When confirmed, Then all pins clear and the plan is not re-run',
        (tester) async {
      _bigView(tester);
      final server = FakePinServer(pins: _twoPins);
      final plan = server.provider();
      await tester.pumpWidget(
        _screen(plan, const SingleChildScrollView(child: PinnedMealsSection())),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(PinnedMealsSection.clearKey));
      await tester.pumpAndSettle();
      expect(find.text('Clear all pins?'), findsOneWidget);
      await tester.tap(find.byKey(PinnedMealsSection.clearDismissKey));
      await tester.pumpAndSettle();
      expect(server.clearCalls, 0);
      expect(_countText(tester), '2 pinned meals');

      await tester.tap(find.byKey(PinnedMealsSection.clearKey));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(PinnedMealsSection.clearConfirmKey));
      await tester.pumpAndSettle();

      expect(server.clearCalls, 1);
      expect(_countText(tester), 'No pinned meals');
      expect(
        find.text('Cleared 2 pins. Applies next time you plan.'),
        findsOneWidget,
      );
      expect(server.planRequests, isEmpty);
      final clear = tester
          .widget<OutlinedButton>(find.byKey(PinnedMealsSection.clearKey));
      expect(clear.enabled, isFalse);
    });

    testWidgets('Given a list failure, Then the server code shows with Retry',
        (tester) async {
      _bigView(tester);
      final server = FakePinServer()
        ..listError = const ApiException(
          statusCode: 400,
          code: 'PROFILE_PIN_INVALID',
          message: 'pins must be a list',
        );
      await tester.pumpWidget(
        _screen(
          server.provider(),
          const SingleChildScrollView(child: PinnedMealsSection()),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(PinnedMealsSection.errorKey), findsOneWidget);
      expect(find.textContaining('PROFILE_PIN_INVALID'), findsOneWidget);

      server.listError = null;
      await tester.tap(find.byKey(PinnedMealsSection.retryKey));
      await tester.pumpAndSettle();
      expect(find.byKey(PinnedMealsSection.errorKey), findsNothing);
      expect(_countText(tester), 'No pinned meals');
    });
  });

  group('Meal Plan View pin badges', () {
    testWidgets(
        'Given a plan with a pinned meal and a planner meal whose slot was '
        'pinned since, Then they show "Pinned" and "Pinned · next plan"',
        (tester) async {
      _bigView(tester);
      Map<String, dynamic> meal(String id, int slot, String source) => {
            'recipe_id': id,
            'name': id,
            'meal_type': 'lunch',
            'slot_index': slot,
            'source': source,
            'nutrition': {
              'calories': 500,
              'protein_g': 30,
              'fat_g': 15,
              'carbs_g': 50,
            },
            'busyness_level': 2,
          };
      final mealPlan = MealPlan.fromPlanApiV1Response({
        'success': true,
        'plan_status': 'success',
        'days': 1,
        'daily_plans': [
          {
            'day': 1,
            'meals': [
              meal('recipe_003', 0, Meal.sourcePlanner),
              meal('recipe_001', 1, Meal.sourcePinnedAssignment),
              meal('recipe_005', 2, Meal.sourcePlanner),
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
        'report': {'failures': <dynamic>[]},
      });
      final server = FakePinServer(pins: const [
        ProfilePin(dayIndex: 0, slotIndex: 1, recipeId: 'recipe_001'),
        // Pinned after the plan ran.
        ProfilePin(dayIndex: 0, slotIndex: 2, recipeId: 'recipe_005'),
      ]);
      final plan = server.provider()..applyPlanResult(mealPlan);

      await tester.pumpWidget(_screen(plan, const MealPlanViewScreen()));
      await tester.pumpAndSettle();

      expect(server.listCalls, 1, reason: 'Meal Plan View fetches pins');
      final labels = [
        for (final e in find.byKey(MealCard.pinBadgeKey).evaluate())
          (e.widget as MacrovaChip).label,
      ];
      expect(labels, ['Pinned', 'Pinned · next plan']);
    });
  });
}
