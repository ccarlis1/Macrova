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

  testWidgets('RecipeBuilderScreen loads recipe from coordinator pending edit',
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
          quantity: 50,
          unit: 'g',
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

    expect(find.text('Oat Bowl'), findsOneWidget);
    expect(find.text('oats'), findsOneWidget);
    expect(find.text('Create Recipe'), findsNothing);
    expect(find.text('Edit Recipe'), findsOneWidget);
  });

  testWidgets('startCreate clears builder title to create mode',
      (tester) async {
    final profile = ProfileProvider();
    final coord = RecipeBuilderCoordinator();
    final recipes = RecipeProvider(recipeSyncFn: (_) async => []);
    await recipes.load();

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

    coord.openForEdit(
      const Recipe(
        id: 'x',
        name: 'Temp',
        ingredients: [
          RecipeIngredientEntry(
            ingredientId: 'i',
            ingredientName: 'a',
            quantity: 1,
            unit: 'g',
          ),
        ],
        servings: 1,
      ),
    );
    await tester.pump();
    expect(find.text('Temp'), findsOneWidget);

    coord.startCreate();
    await tester.pump();

    expect(find.text('Create Recipe'), findsOneWidget);
    expect(find.text('Temp'), findsNothing);
  });
}
