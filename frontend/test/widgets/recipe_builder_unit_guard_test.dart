import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/tag.dart';
import 'package:macrova/providers/ingredient_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_builder_coordinator.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/recipe_builder_screen.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

List<TagMeta> _registry() => TagMeta.listFromResponse(
      jsonDecode(
        File('test/fixtures/tags_list_response.json').readAsStringSync(),
      ) as Map<String, dynamic>,
    );

/// A tagged recipe (so only the unit decides whether Save is allowed) whose
/// almond line is in `cup`, which it has no conversion for.
const _recipe = Recipe(
  id: 'local-unit',
  name: 'Almond Bowl',
  ingredients: [
    RecipeIngredientEntry(
      ingredientId: 'a',
      ingredientName: 'almonds',
      quantity: 2,
      unit: 'cup',
      caloriesPer100g: 600,
      unitConversions: {'tbsp': 9},
    ),
  ],
  tagSlugsByType: {
    'context': ['breakfast'],
  },
);

Future<RecipeProvider> _pump(WidgetTester tester, {Recipe recipe = _recipe}) async {
  tester.view.physicalSize = const Size(1200, 3200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  final recipes = RecipeProvider(
    recipeSyncFn: (batch) async => [for (final r in batch) r.id],
    tagListFn: () async => _registry(),
  );
  await recipes.load();
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
  coord.openForEdit(recipe);
  await tester.pumpAndSettle();
  return recipes;
}

FilledButton _updateButton(WidgetTester tester) => tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Update'),
    );

Future<void> _pickUnit(WidgetTester tester, String from, String to) async {
  await tester.tap(find.widgetWithText(DropdownButton<String>, from));
  await tester.pumpAndSettle();
  await tester.tap(find.text(to).last);
  await tester.pumpAndSettle();
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('Recipe Builder unit guard (FE-13)', () {
    testWidgets(
        'Given a line in a unit with no gram weight, Then it shows an inline '
        'error, no kcal, a totals note, and Save is disabled', (tester) async {
      await _pump(tester);

      expect(find.textContaining("No gram weight for 'cup'"), findsOneWidget);
      expect(find.text('— kcal'), findsOneWidget);
      expect(
        find.byKey(RecipeBuilderScreenState.unresolvedTotalsNoteKey),
        findsOneWidget,
      );
      expect(_updateButton(tester).onPressed, isNull);
    });

    testWidgets('Given the error, When g is chosen, Then it clears and Save is '
        'enabled', (tester) async {
      await _pump(tester);

      await _pickUnit(tester, 'cup', 'g');

      expect(find.textContaining('No gram weight'), findsNothing);
      expect(
        find.byKey(RecipeBuilderScreenState.unresolvedTotalsNoteKey),
        findsNothing,
      );
      expect(find.text('12 kcal'), findsWidgets); // 2 g × 6 kcal/g
      expect(_updateButton(tester).onPressed, isNotNull);
    });

    testWidgets('Given the error, When a known unit is chosen, Then it clears',
        (tester) async {
      await _pump(tester);

      await _pickUnit(tester, 'cup', 'tbsp');

      expect(find.textContaining('No gram weight'), findsNothing);
      expect(find.text('108 kcal'), findsWidgets); // 18 g × 6 kcal/g
      expect(_updateButton(tester).onPressed, isNotNull);
    });

    testWidgets(
        'Given a line with a unit conversion, Then the nutrition summary sends '
        'its grams_per_unit like sync does', (tester) async {
      final bodies = <Map<String, dynamic>>[];
      final client = MockClient((req) async {
        if (req.url.path == '/api/v1/nutrition/summary') {
          bodies.add(jsonDecode(req.body) as Map<String, dynamic>);
        }
        return http.Response('{"error":{"code":"X","message":"offline"}}', 500);
      });

      await http.runWithClient(
        () => _pump(
          tester,
          recipe: _recipe.copyWith(
            ingredients: [
              _recipe.ingredients.single.copyWith(unit: 'tbsp'),
            ],
          ),
        ),
        () => client,
      );

      expect(bodies, isNotEmpty);
      expect(bodies.last['ingredients'], [
        {
          'name': 'almonds',
          'quantity': 2.0,
          'unit': 'tbsp',
          'grams_per_unit': 9.0,
        },
      ]);
    });
  });
}
