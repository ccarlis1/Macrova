import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/starter_recipe.dart';
import 'package:macrova/models/tag.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/services/api_service.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/starter_pack_sheet.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../providers/recipe_provider_starter_test.dart' show FakeStarterServer;

// FE-16: the starter-pack picker sheet.

List<TagMeta> _registry() => TagMeta.listFromResponse(
      jsonDecode(File('test/fixtures/tags_list_response.json').readAsStringSync())
          as Map<String, dynamic>,
    );

const _open = Key('open_sheet');

/// Pumps a launcher, opens the sheet, returns the provider. [server]'s pool
/// becomes the library (after a list refresh).
Future<RecipeProvider> _openSheet(
  WidgetTester tester, {
  FakeStarterServer? server,
  RecipeProvider? provider,
  MealPlanProvider? mealPlan,
}) async {
  tester.view.physicalSize = const Size(1200, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  final s = server ?? FakeStarterServer();
  final recipes = provider ??
      RecipeProvider(
        recipeListFn: s.list,
        starterListFn: () async =>
            StarterRecipe.listFromResponse(_listJson()),
        starterImportFn: s.import,
        tagListFn: () async => _registry(),
      );
  await recipes.load();
  await tester.runAsync(recipes.syncSummariesFromApi);

  Widget app = MaterialApp(
    theme: AppTheme.light,
    home: Scaffold(
      body: Builder(
        builder: (context) => TextButton(
          key: _open,
          onPressed: () => StarterPackSheet.show(context),
          child: const Text('open'),
        ),
      ),
    ),
  );
  app = ChangeNotifierProvider<RecipeProvider>.value(
    value: recipes,
    child: mealPlan == null
        ? app
        : ChangeNotifierProvider<MealPlanProvider>.value(
            value: mealPlan,
            child: app,
          ),
  );
  await tester.pumpWidget(app);
  await tester.tap(find.byKey(_open));
  await tester.pumpAndSettle();
  return recipes;
}

Map<String, dynamic> _listJson() =>
    jsonDecode(File('test/fixtures/starter_recipes_list.json').readAsStringSync())
        as Map<String, dynamic>;

Checkbox _box(WidgetTester tester, String id) =>
    tester.widget<Checkbox>(find.byKey(StarterPackSheet.checkboxKey(id)));

FilledButton _importButton(WidgetTester tester) =>
    tester.widget<FilledButton>(find.byKey(StarterPackSheet.importKey));

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets(
      'Given the sheet opens, Then every starter recipe is listed with its '
      'facts and meal roles, nothing is pre-selected, and Import is disabled',
      (tester) async {
    await _openSheet(tester);

    for (final id in [for (var i = 1; i <= 18; i++) 'recipe_${'$i'.padLeft(3, '0')}']) {
      expect(find.byKey(StarterPackSheet.rowKey(id)), findsOneWidget);
      expect(_box(tester, id).value, isFalse, reason: id);
      expect(_box(tester, id).onChanged, isNotNull, reason: id);
    }
    expect(find.text('Carb Heavy'), findsOneWidget);
    expect(find.text('802 kcal · 30 g protein · 15 min'), findsOneWidget);
    final row = find.byKey(StarterPackSheet.rowKey('recipe_001'));
    expect(
      find.descendant(of: row, matching: find.text('Lunch')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: row, matching: find.text('Dinner')),
      findsOneWidget,
    );
    expect(find.text('In your library'), findsNothing);
    expect(find.text('Nothing selected'), findsOneWidget);
    expect(_importButton(tester).onPressed, isNull);
  });

  testWidgets(
      'Given recipes already in the library, Then their rows say so and '
      'cannot be ticked, and Select all skips them', (tester) async {
    final server = FakeStarterServer()
      ..pool['recipe_001'] = 'Carb Heavy'
      ..pool['recipe_009'] = 'Greek Yogurt Protein Bowl';
    await _openSheet(tester, server: server);

    for (final id in ['recipe_001', 'recipe_009']) {
      final row = find.byKey(StarterPackSheet.rowKey(id));
      expect(
        find.descendant(of: row, matching: find.text('In your library')),
        findsOneWidget,
      );
      expect(_box(tester, id).onChanged, isNull);
      expect(_box(tester, id).value, isFalse);
    }
    await tester.tap(find.byKey(StarterPackSheet.rowKey('recipe_001')));
    await tester.pump();
    expect(_box(tester, 'recipe_001').value, isFalse);
    expect(_importButton(tester).onPressed, isNull);

    await tester.tap(find.byKey(StarterPackSheet.selectAllKey));
    await tester.pump();
    expect(find.text('16 recipes selected'), findsOneWidget);
    expect(_box(tester, 'recipe_002').value, isTrue);
    expect(_box(tester, 'recipe_001').value, isFalse);

    await tester.tap(find.text('Clear selection'));
    await tester.pump();
    expect(find.text('Nothing selected'), findsOneWidget);
  });

  testWidgets(
      'Given two ticked recipes, When Import is tapped, Then those ids are '
      'imported, the sheet closes and a snackbar says how many',
      (tester) async {
    final server = FakeStarterServer();
    final recipes = await _openSheet(tester, server: server);

    await tester.tap(find.byKey(StarterPackSheet.checkboxKey('recipe_017')));
    await tester.tap(find.byKey(StarterPackSheet.rowKey('recipe_003')));
    await tester.pump();
    expect(find.text('2 recipes selected'), findsOneWidget);
    expect(_importButton(tester).onPressed, isNotNull);

    await tester.tap(find.byKey(StarterPackSheet.importKey));
    await tester.pumpAndSettle();

    // Pack order, not tap order.
    expect(server.importCalls, [
      ['recipe_003', 'recipe_017'],
    ]);
    expect(find.byType(StarterPackSheet), findsNothing);
    expect(find.text('Imported 2 recipes into your library.'), findsOneWidget);
    expect(recipes.remoteRecipeIds, {'recipe_003', 'recipe_017'});
  });

  testWidgets(
      'Given Planner Config has ticked recipes, When recipes are imported, '
      'Then the snackbar says to tick them there', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final mealPlan = MealPlanProvider()..toggleRecipe('my-own');
    await _openSheet(tester, mealPlan: mealPlan);

    await tester.tap(find.byKey(StarterPackSheet.rowKey('recipe_002')));
    await tester.pump();
    await tester.tap(find.byKey(StarterPackSheet.importKey));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('tick these to use them'),
      findsOneWidget,
    );
  });

  testWidgets(
      'Given the import request fails, Then the sheet stays open with the '
      'error and the selection', (tester) async {
    final recipes = RecipeProvider(
      recipeListFn: () async => const [],
      starterListFn: () async => StarterRecipe.listFromResponse(_listJson()),
      starterImportFn: (_) async => throw const ApiException(
        statusCode: 500,
        code: 'INTERNAL_ERROR',
        message: 'disk full',
      ),
      tagListFn: () async => _registry(),
    );
    await _openSheet(tester, provider: recipes);

    await tester.tap(find.byKey(StarterPackSheet.rowKey('recipe_002')));
    await tester.pump();
    await tester.tap(find.byKey(StarterPackSheet.importKey));
    await tester.pumpAndSettle();

    expect(find.byType(StarterPackSheet), findsOneWidget);
    expect(find.byKey(StarterPackSheet.importErrorKey), findsOneWidget);
    expect(find.textContaining('disk full'), findsOneWidget);
    expect(_box(tester, 'recipe_002').value, isTrue);
  });

  testWidgets(
      'Given the list fails, Then an error card offers Retry, which reloads',
      (tester) async {
    var calls = 0;
    final recipes = RecipeProvider(
      recipeListFn: () async => const [],
      starterListFn: () async {
        calls++;
        if (calls == 1) {
          throw const ApiException(
            statusCode: 503,
            code: 'HTTP_ERROR',
            message: 'server down',
          );
        }
        return StarterRecipe.listFromResponse(_listJson());
      },
      tagListFn: () async => _registry(),
    );
    await _openSheet(tester, provider: recipes);

    expect(find.byKey(StarterPackSheet.loadErrorKey), findsOneWidget);
    expect(find.text('server down'), findsOneWidget);

    await tester.tap(find.byKey(StarterPackSheet.retryKey));
    await tester.pumpAndSettle();

    expect(find.byKey(StarterPackSheet.loadErrorKey), findsNothing);
    expect(find.byKey(StarterPackSheet.rowKey('recipe_001')), findsOneWidget);
  });

  test('importSummary names skips and the pool hint', () {
    expect(
      StarterPackSheet.importSummary(
        const StarterImportResult(
          imported: ['a'],
          skipped: [
            StarterImportSkipped(id: 'b', reason: 'already_in_pool'),
            StarterImportSkipped(id: 'c', reason: 'already_in_pool'),
            StarterImportSkipped(id: 'd', reason: 'not_a_starter_recipe'),
          ],
        ),
      ),
      'Imported 1 recipe into your library. 2 recipes were already there. '
      '1 recipe is not in the starter pack.',
    );
    expect(
      StarterPackSheet.importSummary(const StarterImportResult()),
      'Nothing imported.',
    );
  });
}
