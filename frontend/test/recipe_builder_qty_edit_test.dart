import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/providers/ingredient_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_builder_coordinator.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/recipe_builder_screen.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets(
    'Given an ingredient line, When quantity is edited, Then line kcal recomputes',
    (tester) async {
      final profile = ProfileProvider();
      final coord = RecipeBuilderCoordinator();
      final recipes = RecipeProvider(recipeSyncFn: (_) async => []);
      await recipes.load();

      const recipe = Recipe(
        id: 'r1',
        name: 'Oat Bowl',
        ingredients: [
          RecipeIngredientEntry(
            ingredientId: 'i1',
            ingredientName: 'oats',
            quantity: 100,
            unit: 'g',
            caloriesPer100g: 100,
          ),
        ],
        servings: 1,
      );

      await tester.pumpWidget(
        MaterialApp(
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
      await tester.pump();

      coord.openForEdit(recipe);
      await tester.pump();

      // Given: 100g at 100 kcal/100g renders 100 kcal on the line.
      expect(find.text('100 kcal'), findsWidgets);

      // When: the quantity field (hint "Qty") is doubled.
      final qtyField = find.byWidgetPredicate(
        (w) => w is TextField && w.decoration?.hintText == 'Qty',
      );
      expect(qtyField, findsOneWidget);
      await tester.enterText(qtyField, '200');
      await tester.pump();

      // Then: the recomputed calories replace the old value.
      expect(find.text('200 kcal'), findsWidgets);
      expect(find.text('100 kcal'), findsNothing);
    },
  );
}
