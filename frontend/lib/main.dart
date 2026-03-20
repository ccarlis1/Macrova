import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'providers/ingredient_provider.dart';
import 'providers/meal_plan_provider.dart';
import 'providers/profile_provider.dart';
import 'providers/recipe_provider.dart';
import 'theme.dart';
import 'widgets/app_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final profile = ProfileProvider();
  final ingredients = IngredientProvider();
  final recipes = RecipeProvider();
  final mealPlan = MealPlanProvider();

  await profile.load();
  await mealPlan.load();
  await ingredients.load();
  await ingredients.mergeBundledCachedIngredientsIfEnabled();

  await recipes.load();
  await recipes.hydrateBundledServerRecipesFromAsset();
  await recipes.mergeBundledServerRecipesIfEnabled();
  await recipes.applyIngredientNutritionFromSavedIngredients(
    ingredients.ingredients,
  );
  await recipes.syncSummariesFromApi();

  runApp(
    MacrovaApp(
      profile: profile,
      ingredients: ingredients,
      recipes: recipes,
      mealPlan: mealPlan,
    ),
  );
}

class MacrovaApp extends StatelessWidget {
  const MacrovaApp({
    super.key,
    required this.profile,
    required this.ingredients,
    required this.recipes,
    required this.mealPlan,
  });

  final ProfileProvider profile;
  final IngredientProvider ingredients;
  final RecipeProvider recipes;
  final MealPlanProvider mealPlan;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: profile),
        ChangeNotifierProvider.value(value: ingredients),
        ChangeNotifierProvider.value(value: recipes),
        ChangeNotifierProvider.value(value: mealPlan),
      ],
      child: MaterialApp(
        title: 'Macrova',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        home: const AppShell(),
      ),
    );
  }
}
