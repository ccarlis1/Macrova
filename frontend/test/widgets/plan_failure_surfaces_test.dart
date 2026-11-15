import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/recipe_sync_result.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/meal_plan_view_screen.dart';
import 'package:macrova/screens/today_screen.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/advisory_card.dart';
import 'package:macrova/widgets/failure_panel.dart';
import 'package:macrova/widgets/failure_view_model.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'widget_test_helpers.dart';

// FE-11: plain-language failure surfaces on Today and Meal Plan View.

class _ReadyLlmGate extends LlmConfigProvider {
  _ReadyLlmGate(super.profile);

  @override
  bool get llmReady => true;

  @override
  void revokeReady(String message) {}
}

/// Records plan requests instead of calling the API.
class _FakePlanProvider extends MealPlanProvider {
  final List<PlanRequest> requests = [];

  @override
  Future<void> generatePlan(PlanRequest request) async {
    requests.add(request);
  }
}

const _goals = {
  'daily_calories': 2000,
  'daily_protein_g': 150.0,
  'daily_fat_g_min': 50.0,
  'daily_fat_g_max': 70.0,
  'daily_carbs_g': 200.0,
};

const _request = PlanRequest(
  dailyCalories: 2000,
  dailyProteinG: 150,
  dailyFatGMin: 50,
  dailyFatGMax: 70,
  days: 2,
  planningMode: 'deterministic',
);

Map<String, dynamic> _meal(String name, int slot) => {
      'meal_type': 'Meal',
      'name': name,
      'slot_index': slot,
      'nutrition': {
        'calories': 500,
        'protein_g': 30,
        'fat_g': 15,
        'carbs_g': 50,
      },
      'busyness_level': 2,
    };

/// Partial 2-day plan: day 1 slot 1 and day 2 slot 0 fail, plus one plan-wide failure.
MealPlan _slotFailurePlan({Map<String, dynamic>? failureCause}) {
  return MealPlan.fromPlanApiV1Response({
    'success': false,
    'termination_code': 'TC-2',
    'plan_status': 'partial',
    'days': 2,
    'daily_plans': [
      {
        'day': 1,
        'meals': [_meal('Day1 Oats', 0), _meal('Day1 Stew', 2)],
      },
      {
        'day': 2,
        'meals': [_meal('Day2 Salad', 1)],
      },
    ],
    'goals': _goals,
    'warnings': const <String, dynamic>{},
    'report': {
      'failures': [
        {
          'code': 'FM-1',
          'message': 'raw message d1',
          'day_index': 0,
          'slot_index': 1,
          'fix_hint': 'raw hint d1',
          'explanation': 'Day 1, meal 2 has no recipe that fits its constraints.',
          'fix': 'Add a recipe that fits day 1, meal 2.',
        },
        {
          'code': 'FM-TAG-EMPTY',
          'message': 'raw message d2',
          'day_index': 1,
          'slot_index': 0,
          'explanation': 'Day 2, meal 1 requires the "vegan" tag.',
          'fix': 'Tag a recipe "vegan".',
        },
        {
          'code': 'FM-4',
          'message': 'raw plan-wide message',
          'explanation': 'Not enough omega 3 over the plan.',
          'fix': 'Add recipes rich in omega 3.',
        },
      ],
      if (failureCause != null) 'failure_cause': failureCause,
    },
  });
}

/// Plan-wide failure only, with a recipe gap.
MealPlan _gapPlan({required bool recipeCouldHelp}) {
  return MealPlan.fromPlanApiV1Response({
    'success': false,
    'termination_code': 'TC-2',
    'plan_status': 'failed',
    'days': 1,
    'daily_plans': const [],
    'goals': _goals,
    'warnings': const <String, dynamic>{},
    'report': {
      'failures': [
        {
          'code': 'FM-MACRO-INFEASIBLE',
          'message': 'Macro targets unreachable',
          'explanation': 'No combination of recipes meets your targets.',
          'fix': 'Add recipes close to 650 kcal and 40 g protein per meal.',
        },
      ],
      'failure_cause': {
        'cause': recipeCouldHelp ? 'macro_gap' : 'IMPOSSIBLE_TARGETS',
        'recipe_could_help': recipeCouldHelp,
        if (recipeCouldHelp)
          'recipe_gap': {
            'per_meal_calories': 650.0,
            'per_meal_protein_g': 40.0,
            'per_meal_fat_g_max': null,
            'per_meal_carbs_g': null,
            'cook_time_cap_minutes': null,
            'excluded_ingredients': <String>[],
            'nutrient_min_per_recipe': <String, double>{},
            'meal_types': <String>[],
            'slots': <List<int>>[],
          },
      },
    },
  });
}

MealPlan _successWithWarnings() {
  return MealPlan.fromPlanApiV1Response({
    'success': true,
    'plan_status': 'success',
    'days': 1,
    'daily_plans': [
      {
        'day': 1,
        'meals': [_meal('Fine Oats', 0)],
      },
    ],
    'goals': _goals,
    'warnings': ['Sodium advisory: weekly total high'],
    'report': {'failures': <dynamic>[]},
  });
}

Widget _wrapScreen({
  required Widget screen,
  required MealPlanProvider mealPlan,
  bool llmReady = false,
}) {
  final profile = ProfileProvider();
  return MaterialApp(
    theme: AppTheme.light,
    home: MultiProvider(
      providers: [
        ChangeNotifierProvider<ProfileProvider>.value(value: profile),
        ChangeNotifierProvider<MealPlanProvider>.value(value: mealPlan),
        ChangeNotifierProvider<RecipeProvider>(create: (_) => RecipeProvider()),
        ChangeNotifierProvider<LlmConfigProvider>.value(
          value: llmReady ? _ReadyLlmGate(profile) : LlmConfigProvider(profile),
        ),
      ],
      child: Scaffold(body: screen),
    ),
  );
}

void _bigView(WidgetTester tester) {
  tester.view.physicalSize = const Size(1000, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('FailurePanel field mapping', () {
    testWidgets(
      'Given explanation and message, When rendered, '
      'Then the explanation, fix and code show and message/fix_hint do not',
      (tester) async {
        const failure = PlanFailure(
          code: 'FM-1',
          message: 'Planner ended with no candidates for slot',
          fixHint: 'Relax constraints (raw hint)',
          explanation: 'Day 1, meal 2 has no recipe that fits its constraints.',
          fix: 'Add a recipe that fits day 1, meal 2.',
        );
        await tester.pumpWidget(
          wrapWidget(FailureViewModel.fromPlanFailure(failure).toPanel()),
        );

        expect(
          find.text('Day 1, meal 2 has no recipe that fits its constraints.'),
          findsOneWidget,
        );
        expect(find.text('Planner ended with no candidates for slot'), findsNothing);
        expect(find.text('Add a recipe that fits day 1, meal 2.'), findsOneWidget);
        expect(find.text('Relax constraints (raw hint)'), findsNothing);
        expect(find.text('FM-1'), findsOneWidget);
      },
    );

    testWidgets(
      'Given no explanation or fix (old server), When rendered, '
      'Then message and fix_hint are the fallbacks',
      (tester) async {
        const failure = PlanFailure(
          code: 'FM-5',
          message: 'Search budget exhausted',
          fixHint: 'Try fewer days',
        );
        await tester.pumpWidget(
          wrapWidget(FailureViewModel.fromPlanFailure(failure).toPanel()),
        );

        expect(find.text('Search budget exhausted'), findsOneWidget);
        expect(find.text('Try fewer days'), findsOneWidget);
        expect(find.text('FM-5'), findsOneWidget);
      },
    );
  });

  group('Recipe gap summary', () {
    test('uses only non-null gap fields', () {
      expect(
        FailureViewModel.summarizeRecipeGap(
          const PlanRecipeGap(perMealCalories: 650, perMealProteinG: 40),
        ),
        'A recipe near 650 kcal and 40 g protein would help.',
      );
      expect(
        FailureViewModel.summarizeRecipeGap(
          const PlanRecipeGap(
            perMealProteinG: 40.4,
            cookTimeCapMinutes: 20,
            nutrientMinPerRecipe: {'omega_3_g': 1.1},
            excludedIngredients: ['a', 'b', 'c', 'd', 'e'],
          ),
        ),
        'A recipe near 40 g protein, rich in Omega-3, ready in 20 min or less, '
        'without a, b, c and 2 more, would help.',
      );
      expect(FailureViewModel.summarizeRecipeGap(const PlanRecipeGap()), isNull);
    });
  });

  group('Slot failures', () {
    testWidgets(
      'Given two slot failures on different slots, When Meal Plan View renders, '
      'Then each shows inline on its slot and the plan-wide one is in the hero',
      (tester) async {
        _bigView(tester);
        final provider = MealPlanProvider()..applyPlanResult(_slotFailurePlan());

        await tester.pumpWidget(
          _wrapScreen(screen: const MealPlanViewScreen(), mealPlan: provider),
        );
        await tester.pumpAndSettle();

        final d1 = find.byKey(FailureViewModel.slotKey(0, 1));
        final d2 = find.byKey(FailureViewModel.slotKey(1, 0));
        expect(d1, findsOneWidget);
        expect(d2, findsOneWidget);
        expect(
          find.descendant(of: d1, matching: find.text('FM-1')),
          findsOneWidget,
        );
        expect(
          find.descendant(
            of: d1,
            matching: find.text('Add a recipe that fits day 1, meal 2.'),
          ),
          findsOneWidget,
        );
        expect(
          find.descendant(of: d2, matching: find.text('FM-TAG-EMPTY')),
          findsOneWidget,
        );
        expect(
          find.descendant(of: d2, matching: find.text('Tag a recipe "vegan".')),
          findsOneWidget,
        );

        // Slot order: day 1 slot 0 meal, slot 1 failure, slot 2 meal.
        final oatsY = tester.getTopLeft(find.text('Day1 Oats')).dy;
        final failY = tester.getTopLeft(d1).dy;
        final stewY = tester.getTopLeft(find.text('Day1 Stew')).dy;
        expect(oatsY < failY && failY < stewY, isTrue);

        final hero = find.byKey(FailureViewModel.heroKey);
        expect(hero, findsOneWidget);
        expect(
          find.descendant(
            of: hero,
            matching: find.text('Not enough omega 3 over the plan.'),
          ),
          findsOneWidget,
        );
        expect(
          find.descendant(of: hero, matching: find.text('FM-1')),
          findsNothing,
        );
        expect(find.text('raw message d1'), findsNothing);
        expect(find.text('TC-2'), findsNothing);
      },
    );

    testWidgets(
      'Given slot failures, When the calendar is shown, '
      'Then the slot failures move into the hero panel',
      (tester) async {
        _bigView(tester);
        final provider = MealPlanProvider()..applyPlanResult(_slotFailurePlan());

        await tester.pumpWidget(
          _wrapScreen(screen: const MealPlanViewScreen(), mealPlan: provider),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text('Calendar'));
        await tester.pumpAndSettle();

        expect(find.byKey(FailureViewModel.slotKey(0, 1)), findsNothing);
        final hero = find.byKey(FailureViewModel.heroKey);
        for (final text in [
          'Day 1, meal 2 has no recipe that fits its constraints.',
          'Day 2, meal 1 requires the "vegan" tag.',
          'Not enough omega 3 over the plan.',
        ]) {
          expect(
            find.descendant(of: hero, matching: find.text(text)),
            findsOneWidget,
          );
        }
      },
    );

    testWidgets(
      'Given slot failures on day 1 and day 2, When Today renders, '
      'Then day 1 is inline and day 2 stays visible in the hero',
      (tester) async {
        _bigView(tester);
        final provider = MealPlanProvider()..applyPlanResult(_slotFailurePlan());

        await tester.pumpWidget(
          _wrapScreen(screen: const TodayScreen(), mealPlan: provider),
        );
        await tester.pumpAndSettle();

        final d1 = find.byKey(FailureViewModel.slotKey(0, 1));
        expect(d1, findsOneWidget);
        expect(
          find.descendant(of: d1, matching: find.text('FM-1')),
          findsOneWidget,
        );
        expect(find.byKey(FailureViewModel.slotKey(1, 0)), findsNothing);

        final hero = find.byKey(FailureViewModel.heroKey);
        expect(
          find.descendant(
            of: hero,
            matching: find.text('Day 2, meal 1 requires the "vegan" tag.'),
          ),
          findsOneWidget,
        );
        expect(
          find.descendant(
            of: hero,
            matching: find.text('Not enough omega 3 over the plan.'),
          ),
          findsOneWidget,
        );
      },
    );
  });

  group('Recipe help', () {
    testWidgets(
      'Given recipe_could_help and a ready LLM gate, When Find a recipe is tapped, '
      'Then the same request is re-run with planning_mode assisted',
      (tester) async {
        _bigView(tester);
        final provider = _FakePlanProvider()
          ..applyPlanResult(_gapPlan(recipeCouldHelp: true))
          ..debugSetLastRequest(_request);

        await tester.pumpWidget(
          _wrapScreen(
            screen: const MealPlanViewScreen(),
            mealPlan: provider,
            llmReady: true,
          ),
        );
        await tester.pumpAndSettle();

        expect(
          find.text('A recipe near 650 kcal and 40 g protein would help.'),
          findsOneWidget,
        );
        expect(find.byKey(FailureViewModel.setupAiKey), findsNothing);

        await tester.tap(find.byKey(FailureViewModel.findRecipeKey));
        await tester.pumpAndSettle();

        expect(provider.requests, hasLength(1));
        final sent = provider.requests.single;
        expect(sent.planningMode, 'assisted');
        expect(
          Map.of(sent.toJson())..remove('planning_mode'),
          Map.of(_request.toJson())..remove('planning_mode'),
        );
        // One-off: the persisted planner mode is unchanged.
        expect(provider.planningMode, 'deterministic');
      },
    );

    testWidgets(
      'Given recipe_could_help and a ready gate on Today, When Find a recipe is tapped, '
      'Then the provider re-runs with assisted',
      (tester) async {
        _bigView(tester);
        final provider = _FakePlanProvider()
          ..applyPlanResult(_gapPlan(recipeCouldHelp: true))
          ..debugSetLastRequest(_request);

        await tester.pumpWidget(
          _wrapScreen(
            screen: const TodayScreen(),
            mealPlan: provider,
            llmReady: true,
          ),
        );
        await tester.pumpAndSettle();

        await tester.tap(find.byKey(FailureViewModel.findRecipeKey));
        await tester.pumpAndSettle();

        expect(provider.requests.single.planningMode, 'assisted');
      },
    );

    testWidgets(
      'Given recipe_could_help and the LLM gate not ready, When rendered, '
      'Then the gap summary and Set up AI help show, not Find a recipe',
      (tester) async {
        _bigView(tester);
        final provider = _FakePlanProvider()
          ..applyPlanResult(_gapPlan(recipeCouldHelp: true))
          ..debugSetLastRequest(_request);

        await tester.pumpWidget(
          _wrapScreen(screen: const MealPlanViewScreen(), mealPlan: provider),
        );
        await tester.pumpAndSettle();

        final setup = find.byKey(FailureViewModel.setupAiKey);
        expect(setup, findsOneWidget);
        expect(
          find.descendant(of: setup, matching: find.text('Set up AI help')),
          findsOneWidget,
        );
        expect(
          find.descendant(
            of: setup,
            matching: find.text(
              'A recipe near 650 kcal and 40 g protein would help.',
            ),
          ),
          findsOneWidget,
        );
        expect(find.byKey(FailureViewModel.findRecipeKey), findsNothing);
        expect(find.text('Find a recipe'), findsNothing);

        // Tapping outside an AppShell is a safe no-op and never plans.
        await tester.tap(setup);
        await tester.pumpAndSettle();
        expect(provider.requests, isEmpty);
      },
    );

    testWidgets(
      'Given recipe_could_help false, When rendered with a ready gate, '
      'Then no recipe action is shown',
      (tester) async {
        _bigView(tester);
        final provider = _FakePlanProvider()
          ..applyPlanResult(_gapPlan(recipeCouldHelp: false))
          ..debugSetLastRequest(_request);

        await tester.pumpWidget(
          _wrapScreen(
            screen: const MealPlanViewScreen(),
            mealPlan: provider,
            llmReady: true,
          ),
        );
        await tester.pumpAndSettle();

        expect(find.byType(FailurePanel), findsOneWidget);
        expect(find.byKey(FailureViewModel.findRecipeKey), findsNothing);
        expect(find.byKey(FailureViewModel.setupAiKey), findsNothing);
        expect(find.byKey(FailureViewModel.recipeGapKey), findsNothing);
      },
    );

    testWidgets(
      'Given failure_cause null, When rendered on Today with a ready gate, '
      'Then no recipe action is shown',
      (tester) async {
        _bigView(tester);
        final provider = _FakePlanProvider()
          ..applyPlanResult(_slotFailurePlan())
          ..debugSetLastRequest(_request);

        await tester.pumpWidget(
          _wrapScreen(
            screen: const TodayScreen(),
            mealPlan: provider,
            llmReady: true,
          ),
        );
        await tester.pumpAndSettle();

        expect(find.byKey(FailureViewModel.heroKey), findsOneWidget);
        expect(find.byKey(FailureViewModel.findRecipeKey), findsNothing);
        expect(find.byKey(FailureViewModel.setupAiKey), findsNothing);
      },
    );

    testWidgets(
      'Given a ready gate but no request to re-run (plan-from-text), When rendered, '
      'Then only the gap summary shows',
      (tester) async {
        _bigView(tester);
        final provider = _FakePlanProvider()
          ..applyPlanResult(_gapPlan(recipeCouldHelp: true));

        await tester.pumpWidget(
          _wrapScreen(
            screen: const MealPlanViewScreen(),
            mealPlan: provider,
            llmReady: true,
          ),
        );
        await tester.pumpAndSettle();

        expect(find.byKey(FailureViewModel.findRecipeKey), findsNothing);
        expect(find.byKey(FailureViewModel.recipeGapKey), findsOneWidget);
      },
    );
  });

  group('Success with warnings (regression)', () {
    for (final entry in {
      'Today': const TodayScreen(),
      'Meal Plan View': const MealPlanViewScreen(),
    }.entries) {
      testWidgets(
        'Given success with warnings, When ${entry.key} renders, '
        'Then AdvisoryCard shows and FailurePanel does not',
        (tester) async {
          _bigView(tester);
          final provider = MealPlanProvider()
            ..applyPlanResult(_successWithWarnings());

          await tester.pumpWidget(
            _wrapScreen(screen: entry.value, mealPlan: provider, llmReady: true),
          );
          await tester.pumpAndSettle();

          expect(find.byType(AdvisoryCard), findsOneWidget);
          expect(find.byType(FailurePanel), findsNothing);
        },
      );
    }
  });

  group('Sync rejections on failed and partial plans (FE-13 follow-up)', () {
    const rejected = RecipeSyncError(
      raw: 'r9: UNRESOLVED_INGREDIENTS: no gram weight for cup',
      recipeId: 'r9',
      recipeName: 'Mystery Stew',
      code: 'UNRESOLVED_INGREDIENTS',
      message: 'no gram weight for cup',
    );

    /// A provider whose pre-plan sync rejects one recipe and whose plan is [plan].
    Future<MealPlanProvider> planned(MealPlan plan) async {
      final provider = MealPlanProvider(
        recipeSyncFn: (_) async => const RecipeSyncResult(
          syncedIds: [],
          errors: [rejected],
        ),
        planFn: (_) async => plan,
      );
      await provider.generatePlanWithRecipeSync(
        recipesToSync: const [],
        request: _request,
      );
      return provider;
    }

    final screens = {
      'Today': const TodayScreen(),
      'Meal Plan View': const MealPlanViewScreen(),
    };
    final plans = {
      'failed': () => _gapPlan(recipeCouldHelp: false),
      'partial': () => _slotFailurePlan(),
    };

    for (final screen in screens.entries) {
      for (final plan in plans.entries) {
        testWidgets(
          'Given a ${plan.key} plan after a sync rejection, When '
          '${screen.key} renders, Then the FailurePanel and an AdvisoryCard '
          'naming the rejected recipe both show',
          (tester) async {
            _bigView(tester);
            final provider = await planned(plan.value());

            await tester.pumpWidget(
              _wrapScreen(screen: screen.value, mealPlan: provider),
            );
            await tester.pumpAndSettle();

            expect(find.byKey(FailureViewModel.heroKey), findsOneWidget);
            final card = find.byKey(syncWarningsCardKey);
            expect(card, findsOneWidget);
            expect(
              find.descendant(
                of: card,
                matching: find.text(recipeSyncWarning(rejected)),
              ),
              findsOneWidget,
            );
            expect(find.text('A recipe was not synced'), findsOneWidget);
          },
        );
      }

      testWidgets(
        'Given a successful plan after a sync rejection, When ${screen.key} '
        'renders, Then the rejection is among the advisories and no '
        'FailurePanel or separate sync card shows',
        (tester) async {
          _bigView(tester);
          final provider = await planned(_successWithWarnings());

          await tester.pumpWidget(
            _wrapScreen(screen: screen.value, mealPlan: provider),
          );
          await tester.pumpAndSettle();

          expect(find.byType(FailurePanel), findsNothing);
          expect(find.byKey(syncWarningsCardKey), findsNothing);
          expect(find.byType(AdvisoryCard), findsOneWidget);
          expect(
            find.textContaining(recipeSyncWarning(rejected)),
            findsOneWidget,
          );
        },
      );
    }

    test('the server warnings are not sync warnings', () async {
      final provider = await planned(_successWithWarnings());
      final plan = provider.mealPlan!;
      expect(plan.syncWarnings, [recipeSyncWarning(rejected)]);
      expect(plan.warnings, [
        recipeSyncWarning(rejected),
        'Sodium advisory: weekly total high',
      ]);
    });
  });

  group('MealPlanProvider.rerunLastRequest', () {
    test('is a no-op without a last request', () async {
      final provider = _FakePlanProvider();
      await provider.rerunLastRequest(planningMode: 'assisted');
      expect(provider.requests, isEmpty);
      expect(provider.canRerunLastRequest, isFalse);
    });

    test('applyPlanResult and clearPlan drop the last request', () {
      final provider = _FakePlanProvider()..debugSetLastRequest(_request);
      expect(provider.canRerunLastRequest, isTrue);
      provider.applyPlanResult(_successWithWarnings());
      expect(provider.canRerunLastRequest, isFalse);
      provider
        ..debugSetLastRequest(_request)
        ..clearPlan();
      expect(provider.canRerunLastRequest, isFalse);
    });
  });
}
