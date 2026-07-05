import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/theme/app_theme.dart';

const sampleRecipe = Recipe(
  id: 'r1',
  name: 'Test Salad',
  servings: 2,
  ingredients: [
    RecipeIngredientEntry(
      ingredientId: 'i1',
      ingredientName: 'Lettuce',
      quantity: 100,
      caloriesPer100g: 15,
      proteinPer100g: 1,
      carbsPer100g: 2,
      fatPer100g: 0.2,
    ),
  ],
);

Widget wrapWidget(Widget child, {bool dark = false}) {
  return MaterialApp(
    theme: AppTheme.light,
    darkTheme: AppTheme.dark,
    themeMode: dark ? ThemeMode.dark : ThemeMode.light,
    home: Scaffold(
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: child,
      ),
    ),
  );
}

Future<void> pumpBothThemes(
  WidgetTester tester,
  Widget child, {
  required void Function() assertions,
}) async {
  for (final dark in [false, true]) {
    await tester.pumpWidget(wrapWidget(child, dark: dark));
    await tester.pump();
    assertions();
  }
}
