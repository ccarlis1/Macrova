import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/recipe_sync_result.dart';
import 'package:macrova/models/tag.dart';
import 'package:macrova/providers/ingredient_provider.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_builder_coordinator.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/planner_config_screen.dart';
import 'package:macrova/screens/recipe_builder_screen.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../providers/recipe_provider_starter_test.dart' show FakeStarterServer;

// FE-16: after a starter import, the next plan uses the imported recipes and
// they open in the Recipe Builder as normal, savable recipes.

Map<String, dynamic> _json(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync())
        as Map<String, dynamic>;

/// `GET /recipes/{id}` for an imported id: the captured recipe_009 detail
/// (cup / tbsp / scoop lines with their conversions) under that id.
Future<Recipe> _detail(String id) async {
  final d = Recipe.fromJson(_json('starter_recipe_detail_units.json'));
  return d.copyWith(id: id, name: 'Imported $id');
}

void _bigView(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _PlanCapture {
  final List<PlanRequest> requests = [];
  final List<List<String>> synced = [];

  MealPlanProvider provider() => MealPlanProvider(
        planFn: (request) async {
          requests.add(request);
          return MealPlan.fromPlanApiV1Response({
            'success': true,
            'plan_status': 'success',
            'days': 1,
            'daily_plans': const [],
            'goals': const {},
            'warnings': const <String>[],
            'report': {'failures': const <dynamic>[]},
          });
        },
        recipeSyncFn: (batch) async {
          synced.add([for (final r in batch) r.id]);
          return RecipeSyncResult(syncedIds: [for (final r in batch) r.id]);
        },
      )..setDays(1);
}

Future<void> _pumpPlanner(
  WidgetTester tester,
  RecipeProvider recipes,
  MealPlanProvider mealPlan,
) async {
  final profile = ProfileProvider();
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<ProfileProvider>.value(value: profile),
        ChangeNotifierProvider<LlmConfigProvider>.value(
          value: LlmConfigProvider(profile),
        ),
        ChangeNotifierProvider<RecipeProvider>.value(value: recipes),
        ChangeNotifierProvider<MealPlanProvider>.value(value: mealPlan),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const Scaffold(body: PlannerConfigScreen()),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _tapGenerate(WidgetTester tester) async {
  final button = find.widgetWithText(FilledButton, 'Generate Meal Plan');
  await tester.ensureVisible(button);
  await tester.tap(button);
  await tester.pumpAndSettle();
}

const _imported = ['recipe_001', 'recipe_009', 'recipe_017'];

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets(
      'Given an empty pool, When 3 starter recipes are imported and a plan is '
      'generated, Then the request reads the server pool that holds them',
      (tester) async {
    _bigView(tester);
    final server = FakeStarterServer();
    final recipes = server.provider(detail: _detail);
    await recipes.load();
    await tester.runAsync(() => recipes.importStarterRecipes(_imported));
    expect(recipes.recipes.map((r) => r.id).toSet(), _imported.toSet());

    final capture = _PlanCapture();
    await _pumpPlanner(tester, recipes, capture.provider());
    await _tapGenerate(tester);

    // No Planner Config selection: `/plan` gets no `recipe_ids`, so the
    // server plans with its whole pool, which now holds the 3 imports.
    expect(capture.requests, hasLength(1));
    expect(capture.requests.single.recipeIds, isNull);
    expect(capture.requests.single.toJson().containsKey('recipe_ids'), isFalse);
    expect(server.pool.keys.toSet(), _imported.toSet());
    // Nothing local to push: the imports already live on the server.
    expect(capture.synced, [<String>[]]);
  });

  testWidgets(
      'Given the 3 imports ticked in Planner Config, When a plan is generated, '
      'Then recipe_ids lists them and their details sync first',
      (tester) async {
    _bigView(tester);
    final server = FakeStarterServer();
    final recipes = server.provider(detail: _detail);
    await recipes.load();
    await tester.runAsync(() => recipes.importStarterRecipes(_imported));

    final capture = _PlanCapture();
    final mealPlan = capture.provider();
    for (final id in _imported) {
      mealPlan.toggleRecipe(id);
    }
    await _pumpPlanner(tester, recipes, mealPlan);
    await _tapGenerate(tester);

    expect(capture.requests, hasLength(1));
    expect(capture.requests.single.recipeIds?.toSet(), _imported.toSet());
    expect(capture.synced.single.toSet(), _imported.toSet());
  });

  testWidgets(
      'Given an imported recipe with cup/tbsp/scoop lines, When it opens in '
      'the Recipe Builder, Then no line is flagged and Update is enabled',
      (tester) async {
    _bigView(tester);
    final server = FakeStarterServer();
    final registry = TagMeta.listFromResponse(_json('tags_list_response.json'));
    final recipes = RecipeProvider(
      recipeListFn: server.list,
      starterImportFn: server.import,
      recipeDetailFn: _detail,
      tagListFn: () async => registry,
      recipeSyncFn: (batch) async =>
          RecipeSyncResult(syncedIds: [for (final r in batch) r.id]),
    );
    await recipes.load();
    await tester.runAsync(() => recipes.importStarterRecipes(['recipe_009']));
    final summary = recipes.getById('recipe_009')!;
    expect(summary.ingredients, isEmpty);

    final coord = RecipeBuilderCoordinator();
    final profile = ProfileProvider();
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: Scaffold(
          body: MultiProvider(
            providers: [
              ChangeNotifierProvider.value(value: profile),
              ChangeNotifierProvider.value(value: LlmConfigProvider(profile)),
              ChangeNotifierProvider.value(value: IngredientProvider()),
              ChangeNotifierProvider.value(value: recipes),
              ChangeNotifierProvider.value(value: coord),
            ],
            child: const RecipeBuilderScreen(),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    coord.openForEdit(summary);
    await tester.pumpAndSettle();

    expect(recipes.getById('recipe_009')!.ingredients, hasLength(7));
    expect(find.textContaining('No gram weight'), findsNothing);
    expect(
      find.byKey(RecipeBuilderScreenState.unresolvedTotalsNoteKey),
      findsNothing,
    );
    final update = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Update'),
    );
    expect(update.onPressed, isNotNull);
  });
}
