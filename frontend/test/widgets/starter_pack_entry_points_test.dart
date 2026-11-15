import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/starter_recipe.dart';
import 'package:macrova/models/tag.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_builder_coordinator.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/meal_plan_view_screen.dart';
import 'package:macrova/screens/recipe_library_screen.dart';
import 'package:macrova/screens/today_screen.dart';
import 'package:macrova/services/storage_service.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/failure_view_model.dart';
import 'package:macrova/widgets/starter_pack_sheet.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'widget_test_helpers.dart';

// FE-16: every entry point to the starter-pack sheet.

Map<String, dynamic> _json(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync())
        as Map<String, dynamic>;

/// A provider whose starter list is the captured pack; nothing is imported.
RecipeProvider _recipes() => RecipeProvider(
      recipeListFn: () async => const [],
      starterListFn: () async =>
          StarterRecipe.listFromResponse(_json('starter_recipes_list.json')),
      starterImportFn: (_) async => const StarterImportResult(),
      tagListFn: () async => TagMeta.listFromResponse(
        _json('tags_list_response.json'),
      ),
    );

/// The captured `/plan` response for an empty pool (FM-1, `EMPTY_POOL`).
MealPlan _emptyPoolPlan() =>
    MealPlan.fromPlanApiV1Response(_json('plan_empty_pool.json'));

void _bigView(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

Future<void> _pump(
  WidgetTester tester,
  Widget screen, {
  required RecipeProvider recipes,
  MealPlanProvider? mealPlan,
}) async {
  final profile = ProfileProvider();
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.light,
      home: MultiProvider(
        providers: [
          ChangeNotifierProvider<ProfileProvider>.value(value: profile),
          ChangeNotifierProvider<MealPlanProvider>.value(
            value: mealPlan ?? MealPlanProvider(),
          ),
          ChangeNotifierProvider<RecipeProvider>.value(value: recipes),
          ChangeNotifierProvider<RecipeBuilderCoordinator>.value(
            value: RecipeBuilderCoordinator(),
          ),
          ChangeNotifierProvider<LlmConfigProvider>.value(
            value: LlmConfigProvider(profile),
          ),
        ],
        child: Scaffold(body: screen),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _tapOpensSheet(WidgetTester tester, Finder target) async {
  expect(target, findsOneWidget);
  expect(find.byType(StarterPackSheet), findsNothing);
  await tester.ensureVisible(target);
  await tester.tap(target);
  await tester.pumpAndSettle();
  expect(find.byType(StarterPackSheet), findsOneWidget);
  expect(
    find.byKey(StarterPackSheet.rowKey('recipe_001')),
    findsOneWidget,
  );
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets(
      'Given an empty library, When "Start from the starter pack" is tapped, '
      'Then the sheet opens', (tester) async {
    _bigView(tester);
    final recipes = _recipes();
    await _pump(tester, const RecipeLibraryScreen(), recipes: recipes);

    expect(find.byKey(RecipeLibraryScreen.emptyBuildKey), findsOneWidget);
    await _tapOpensSheet(
      tester,
      find.byKey(RecipeLibraryScreen.emptyStarterPackKey),
    );
  });

  testWidgets(
      'Given a library with recipes, When the header Starter pack action is '
      'tapped, Then the sheet opens', (tester) async {
    _bigView(tester);
    await StorageService.saveRecipes([sampleRecipe]);
    final recipes = _recipes();
    await recipes.load();
    await _pump(tester, const RecipeLibraryScreen(), recipes: recipes);

    expect(find.byKey(RecipeLibraryScreen.emptyStarterPackKey), findsNothing);
    await _tapOpensSheet(tester, find.byKey(RecipeLibraryScreen.starterPackKey));
  });

  testWidgets(
      'Given no plan and an empty library, When Today\'s starter-pack link is '
      'tapped, Then the sheet opens', (tester) async {
    _bigView(tester);
    await _pump(tester, const TodayScreen(), recipes: _recipes());

    await _tapOpensSheet(tester, find.byKey(TodayScreen.starterPackKey));
  });

  testWidgets(
      'Given no plan but a library with recipes, Then Today shows no '
      'starter-pack link', (tester) async {
    _bigView(tester);
    await StorageService.saveRecipes([
      const Recipe(id: 'mine', name: 'Mine'),
    ]);
    final recipes = _recipes();
    await recipes.load();
    await _pump(tester, const TodayScreen(), recipes: recipes);

    expect(find.byKey(TodayScreen.starterPackKey), findsNothing);
  });

  testWidgets(
      'Given an EMPTY_POOL plan on Today, Then the FailurePanel links to the '
      'starter pack instead of AI recipe help, and the link opens the sheet',
      (tester) async {
    _bigView(tester);
    final plan = _emptyPoolPlan();
    expect(plan.failureCause?.cause, FailureViewModel.emptyPoolCause);
    expect(plan.failureCause?.recipeCouldHelp, isTrue);
    final mealPlan = MealPlanProvider()..applyPlanResult(plan);
    await _pump(tester, const TodayScreen(),
        recipes: _recipes(), mealPlan: mealPlan);

    expect(find.byKey(FailureViewModel.heroKey), findsOneWidget);
    expect(find.byKey(FailureViewModel.setupAiKey), findsNothing);
    expect(find.byKey(FailureViewModel.findRecipeKey), findsNothing);
    await _tapOpensSheet(tester, find.byKey(FailureViewModel.starterPackKey));
  });

  testWidgets(
      'Given an EMPTY_POOL plan on Meal Plan View, Then the FailurePanel '
      'links to the starter pack', (tester) async {
    _bigView(tester);
    final mealPlan = MealPlanProvider()..applyPlanResult(_emptyPoolPlan());
    await _pump(tester, const MealPlanViewScreen(),
        recipes: _recipes(), mealPlan: mealPlan);

    await _tapOpensSheet(tester, find.byKey(FailureViewModel.starterPackKey));
  });

  testWidgets(
      'Given a recipe-gap plan (not EMPTY_POOL), Then there is no '
      'starter-pack row', (tester) async {
    _bigView(tester);
    final mealPlan = MealPlanProvider()
      ..applyPlanResult(
        MealPlan.fromPlanApiV1Response(_json('plan_failure_recipe_gap.json')),
      );
    await _pump(tester, const TodayScreen(),
        recipes: _recipes(), mealPlan: mealPlan);

    expect(find.byKey(FailureViewModel.heroKey), findsOneWidget);
    expect(find.byKey(FailureViewModel.starterPackKey), findsNothing);
    expect(find.byKey(FailureViewModel.setupAiKey), findsOneWidget);
  });
}
