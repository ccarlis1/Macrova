import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'features/agent/llm_config_provider.dart';
import 'providers/ingredient_provider.dart';
import 'providers/meal_plan_provider.dart';
import 'providers/profile_provider.dart';
import 'providers/recipe_builder_coordinator.dart';
import 'providers/recipe_provider.dart';
import 'theme.dart';
import 'widgets/app_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final profile = ProfileProvider();
  final llmGate = LlmConfigProvider(profile);
  final ingredients = IngredientProvider();
  final recipes = RecipeProvider();
  final recipeBuilderCoordinator = RecipeBuilderCoordinator();
  final mealPlan = MealPlanProvider();

  await profile.load();
  await profile.mergeBundledUserProfileIfEnabled();
  profile.addListener(llmGate.syncCredentialsFromProfile);
  await mealPlan.load();
  await llmGate.loadFromProfile();
  if (!llmGate.llmReady &&
      LlmConfigProvider.isAssistedPlanningMode(mealPlan.planningMode)) {
    mealPlan.setPlanningMode('deterministic');
  }
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
      llmGate: llmGate,
      ingredients: ingredients,
      recipes: recipes,
      recipeBuilderCoordinator: recipeBuilderCoordinator,
      mealPlan: mealPlan,
    ),
  );
}

class MacrovaApp extends StatelessWidget {
  const MacrovaApp({
    super.key,
    required this.profile,
    required this.llmGate,
    required this.ingredients,
    required this.recipes,
    required this.recipeBuilderCoordinator,
    required this.mealPlan,
  });

  final ProfileProvider profile;
  final LlmConfigProvider llmGate;
  final IngredientProvider ingredients;
  final RecipeProvider recipes;
  final RecipeBuilderCoordinator recipeBuilderCoordinator;
  final MealPlanProvider mealPlan;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: profile),
        ChangeNotifierProvider.value(value: llmGate),
        ChangeNotifierProvider.value(value: ingredients),
        ChangeNotifierProvider.value(value: recipes),
        ChangeNotifierProvider.value(value: recipeBuilderCoordinator),
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
