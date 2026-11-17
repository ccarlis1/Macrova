import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/planner_config_screen.dart';
import 'package:macrova/services/api_service.dart';
import 'package:macrova/services/storage_service.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/macrova_chip.dart';
import 'package:macrova/widgets/planner/tag_pool_filter_section.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../widgets/widget_test_helpers.dart';

Future<void> _pumpScreen(
  WidgetTester tester, {
  ProfileProvider? profile,
  MealPlanProvider? mealPlan,
  RecipeProvider? recipes,
}) async {
  final p = profile ?? ProfileProvider();
  final mp = mealPlan ?? MealPlanProvider();
  final rp = recipes ?? RecipeProvider();

  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<ProfileProvider>.value(value: p),
        ChangeNotifierProvider<LlmConfigProvider>.value(
          value: LlmConfigProvider(p),
        ),
        ChangeNotifierProvider<RecipeProvider>.value(value: rp),
        ChangeNotifierProvider<MealPlanProvider>.value(value: mp),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const Scaffold(body: PlannerConfigScreen()),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('PlannerConfigScreen', () {
    testWidgets(
      'Given the day-count selector, When a day chip is tapped, '
      'Then MealPlanProvider.days updates',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 2400);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final mealPlan = MealPlanProvider();
        expect(mealPlan.days, 7);

        await _pumpScreen(tester, mealPlan: mealPlan);

        // The first seven MacrovaChips are the day-count selector (1..7);
        // index 2 corresponds to day 3.
        await tester.tap(find.byType(MacrovaChip).at(2));
        await tester.pumpAndSettle();

        expect(mealPlan.days, 3);
      },
    );

    testWidgets(
      'Given a recipe in the pool, When its row is tapped, '
      'Then it becomes selected',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 2400);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final mealPlan = MealPlanProvider();
        mealPlan.setDays(1);
        final recipes = RecipeProvider();
        await StorageService.saveRecipes([sampleRecipe]);
        await recipes.load();

        await _pumpScreen(tester, mealPlan: mealPlan, recipes: recipes);

        expect(find.text('Test Salad'), findsOneWidget);
        expect(mealPlan.selectedRecipeIds, isEmpty);
        expect(
          find.text('0 recipes selected from your library'),
          findsOneWidget,
        );

        await tester.tap(find.text('Test Salad'));
        await tester.pumpAndSettle();

        expect(mealPlan.selectedRecipeIds, contains('r1'));
        expect(
          find.text('1 recipes selected from your library'),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'Given pool filter chips, When dietary/cost/prep/cuisine are tapped, '
      'Then MealPlanProvider state updates',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 3200);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final mealPlan = MealPlanProvider();
        mealPlan.setDays(1);

        await _pumpScreen(tester, mealPlan: mealPlan);

        expect(find.text('Recipe pool filters'), findsOneWidget);

        await tester.ensureVisible(find.byKey(const Key('pool_filter_cuisine_mexican')));
        await tester.tap(find.byKey(const Key('pool_filter_cuisine_mexican')));
        await tester.pumpAndSettle();
        expect(mealPlan.cuisine, contains('mexican'));

        await tester.tap(find.byKey(const Key('pool_filter_cost_cheap')));
        await tester.pumpAndSettle();
        expect(mealPlan.costLevel, 'cheap');

        await tester.tap(find.byKey(const Key('pool_filter_prep_quick_meal')));
        await tester.pumpAndSettle();
        expect(mealPlan.prepTimeBucket, 'quick_meal');

        await tester.tap(find.byKey(const Key('pool_filter_dietary_vegan')));
        await tester.pumpAndSettle();
        expect(mealPlan.dietaryFlags, contains('vegan'));

        expect(mealPlan.activePoolFilterCount, 4);
        expect(find.text('Pool filters are active'), findsOneWidget);
        expect(find.textContaining('4 filters'), findsOneWidget);
      },
    );

    testWidgets(
      'Given active pool filters, When PlanRequest is built from provider, '
      'Then toJson includes pool tag keys; clearing omits them',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 3200);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final mealPlan = MealPlanProvider();
        mealPlan.setDays(1);
        await _pumpScreen(tester, mealPlan: mealPlan);

        await tester.ensureVisible(find.byKey(const Key('pool_filter_cuisine_italian')));
        await tester.tap(find.byKey(const Key('pool_filter_cuisine_italian')));
        await tester.tap(find.byKey(const Key('pool_filter_cost_standard')));
        await tester.tap(find.byKey(const Key('pool_filter_prep_snack')));
        await tester.tap(find.byKey(const Key('pool_filter_dietary_vegetarian')));
        await tester.pumpAndSettle();

        PlanRequest requestFromProvider(MealPlanProvider p) => PlanRequest(
              dailyCalories: 2000,
              dailyProteinG: 100,
              dailyFatGMin: 40,
              dailyFatGMax: 80,
              days: p.days,
              cuisine: p.cuisine.isEmpty ? null : List<String>.from(p.cuisine),
              costLevel: p.costLevel,
              prepTimeBucket: p.prepTimeBucket,
              dietaryFlags:
                  p.dietaryFlags.isEmpty ? null : List<String>.from(p.dietaryFlags),
            );

        final withFilters = requestFromProvider(mealPlan).toJson();
        expect(withFilters['cuisine'], ['italian']);
        expect(withFilters['cost_level'], 'standard');
        expect(withFilters['prep_time_bucket'], 'snack');
        expect(withFilters['dietary_flags'], ['vegetarian']);

        await tester.tap(find.byKey(const Key('pool_filter_cuisine_clear')));
        await tester.tap(find.byKey(const Key('pool_filter_cost_standard')));
        await tester.tap(find.byKey(const Key('pool_filter_prep_snack')));
        await tester.tap(find.byKey(const Key('pool_filter_dietary_vegetarian')));
        await tester.pumpAndSettle();

        expect(mealPlan.cuisine, isEmpty);
        expect(mealPlan.costLevel, isNull);
        expect(mealPlan.prepTimeBucket, isNull);
        expect(mealPlan.dietaryFlags, isEmpty);

        final cleared = requestFromProvider(mealPlan).toJson();
        expect(cleared.containsKey('cuisine'), isFalse);
        expect(cleared.containsKey('cost_level'), isFalse);
        expect(cleared.containsKey('prep_time_bucket'), isFalse);
        expect(cleared.containsKey('dietary_flags'), isFalse);
      },
    );
  });

  group('Pool filter missing-value warnings (FE-12)', () {
    // Local copies (with remembered values that the server's override).
    final pool = [
      sampleRecipe.copyWith(id: 'a', name: 'A', cuisine: 'italian'),
      sampleRecipe.copyWith(id: 'b', name: 'B'),
      sampleRecipe.copyWith(id: 'c', name: 'C', costLevel: 'cheap'),
      sampleRecipe.copyWith(id: 'd', name: 'D'),
    ];

    /// Stored tag fields per `GET /api/v1/recipes/{id}`; `d` is not on the
    /// server (404).
    Recipe detail(String id) => switch (id) {
          'a' => Recipe(id: id, name: 'A', cuisine: 'thai', costLevel: 'cheap'),
          'b' => Recipe(
              id: id, name: 'B', cuisine: 'unknown', costLevel: 'standard'),
          'c' => Recipe(id: id, name: 'C'), // no tag entry: nulls
          _ => throw const ApiException(
              statusCode: 404,
              code: 'RECIPE_NOT_FOUND',
              message: 'not found',
            ),
        };

    Future<(RecipeProvider, List<String>)> loadPool() async {
      await StorageService.saveRecipes(pool);
      final calls = <String>[];
      final recipes = RecipeProvider(
        recipeDetailFn: (id) async {
          calls.add(id);
          return detail(id);
        },
      );
      await recipes.load();
      return (recipes, calls);
    }

    void bigView(WidgetTester tester) {
      tester.view.physicalSize = const Size(1000, 3600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
    }

    MealPlanProvider selectAll() {
      final mealPlan = MealPlanProvider()..setDays(1);
      for (final id in ['a', 'b', 'c', 'd']) {
        mealPlan.toggleRecipe(id);
      }
      return mealPlan;
    }

    Future<void> tapKey(WidgetTester tester, String key) async {
      await tester.ensureVisible(find.byKey(Key(key)));
      await tester.tap(find.byKey(Key(key)));
      await tester.pumpAndSettle();
    }

    testWidgets(
      'Given a selected pool, When a cuisine filter is selected, Then the '
      'stored cuisines are loaded and the AdvisoryCard counts the ones without',
      (tester) async {
        bigView(tester);
        final (recipes, calls) = await loadPool();
        await _pumpScreen(tester, mealPlan: selectAll(), recipes: recipes);

        expect(calls, isEmpty);
        expect(find.byKey(TagPoolFilterSection.cuisineGapKey), findsNothing);

        await tapKey(tester, 'pool_filter_cuisine_mexican');

        expect(calls.toSet(), {'a', 'b', 'c', 'd'});
        expect(find.byKey(TagPoolFilterSection.cuisineGapKey), findsOneWidget);
        // b is `unknown`, c has no tag entry; a's server value (thai) wins
        // over its remembered italian; d isn't on the server.
        expect(
          find.text('2 recipes have no cuisine set and will be left out.'),
          findsOneWidget,
        );
        expect(recipes.getById('a')!.cuisine, 'thai');
        expect(find.byKey(TagPoolFilterSection.uncheckedKey), findsOneWidget);
        expect(
          find.text('Stored cuisine and cost not checked for 1 recipe'),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'Given a selected pool, Then only selected recipes are fetched and '
      'counted',
      (tester) async {
        bigView(tester);
        final (recipes, calls) = await loadPool();
        final mealPlan = MealPlanProvider()..setDays(1);
        mealPlan.toggleRecipe('a');
        mealPlan.toggleRecipe('b');
        await _pumpScreen(tester, mealPlan: mealPlan, recipes: recipes);

        await tapKey(tester, 'pool_filter_cuisine_mexican');

        expect(calls.toSet(), {'a', 'b'});
        expect(
          find.text('1 recipe has no cuisine set and will be left out.'),
          findsOneWidget,
        );
        expect(find.byKey(TagPoolFilterSection.uncheckedKey), findsNothing);
      },
    );

    testWidgets(
      'Given no selection (whole library), When a cuisine filter is selected, '
      'Then no details are fetched and the pool is reported unchecked',
      (tester) async {
        bigView(tester);
        final (recipes, calls) = await loadPool();
        await _pumpScreen(
          tester,
          mealPlan: MealPlanProvider()..setDays(1),
          recipes: recipes,
        );

        await tapKey(tester, 'pool_filter_cuisine_mexican');

        expect(calls, isEmpty);
        // Locally remembered values are not counted.
        expect(find.byKey(TagPoolFilterSection.cuisineGapKey), findsNothing);
        expect(
          find.text('Stored cuisine and cost not checked for 4 recipes'),
          findsOneWidget,
        );
        expect(find.textContaining('Select recipes in the pool'),
            findsOneWidget);
      },
    );

    testWidgets(
      'Given stored costs, When Cheap is selected, Then Standard / unset '
      'recipes are counted; Standard (the stored default) shows no warning',
      (tester) async {
        bigView(tester);
        final (recipes, _) = await loadPool();
        await _pumpScreen(tester, mealPlan: selectAll(), recipes: recipes);

        await tapKey(tester, 'pool_filter_cost_cheap');

        // b is standard; c has no tag entry but keeps its remembered cheap.
        expect(
          find.text(
              '1 recipe is Standard or has no cost set and will be left out.'),
          findsOneWidget,
        );

        await tapKey(tester, 'pool_filter_cost_standard');

        expect(find.byKey(TagPoolFilterSection.costGapKey), findsNothing);
        expect(find.byKey(TagPoolFilterSection.uncheckedKey), findsNothing);
      },
    );
  });

  group('MealPlanProvider pool filters', () {
    test(
      'Given persisted filter keys, When load is called, '
      'Then valid enums restore and invalid values are ignored',
      () async {
        await StorageService.savePlannerConfig({
          'days': 3,
          'cuisine': ['mexican', ''],
          'cost_level': 'not_a_level',
          'prep_time_bucket': 'quick_meal',
          'dietary_flags': ['vegan', 'keto'],
        });

        final mealPlan = MealPlanProvider();
        await mealPlan.load();

        expect(mealPlan.days, 3);
        expect(mealPlan.cuisine, ['mexican']);
        expect(mealPlan.costLevel, isNull);
        expect(mealPlan.prepTimeBucket, 'quick_meal');
        expect(mealPlan.dietaryFlags, ['vegan']);
      },
    );
  });
}
