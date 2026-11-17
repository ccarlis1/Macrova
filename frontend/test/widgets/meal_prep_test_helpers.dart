import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:macrova/models/meal_prep_batch.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/recipe_sync_result.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/services/api_service.dart';
import 'package:macrova/services/storage_service.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:provider/provider.dart';

Map<String, dynamic> fixtureJson(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync())
        as Map<String, dynamic>;

/// Meal-prep capable recipe (as the detail reports it after FE-12's switch).
const capableRecipe = Recipe(
  id: 'fe14-oat-bowl',
  name: 'Overnight Oat Bowl',
  servings: 3,
  ingredients: [
    RecipeIngredientEntry(ingredientId: 'i1', ingredientName: 'oats'),
  ],
  tagSlugsByType: {
    'context': ['breakfast', 'meal-prep'],
  },
  isMealPrepCapable: true,
);

const plainRecipe = Recipe(
  id: 'plain',
  name: 'Plain Oats',
  ingredients: [
    RecipeIngredientEntry(ingredientId: 'i1', ingredientName: 'oats'),
  ],
  tagSlugsByType: {
    'context': ['breakfast'],
  },
);

const planRequest = PlanRequest(
  dailyCalories: 2000,
  dailyProteinG: 150,
  dailyFatGMin: 50,
  dailyFatGMax: 70,
  days: 2,
  planningMode: 'deterministic',
);

Map<String, dynamic> _meal(String name, int slot) => {
      'meal_type': 'Meal',
      'name': name,
      'slot_index': slot,
      'nutrition': {
        'calories': 500,
        'protein_g': 30,
        'fat_g': 15,
        'carbs_g': 50,
      },
      'busyness_level': 2,
    };

/// 2-day plan, 2 meals per day, all planner meals.
MealPlan twoDayPlan() => MealPlan.fromPlanApiV1Response({
      'success': true,
      'plan_status': 'success',
      'days': 2,
      'daily_plans': [
        {
          'day': 1,
          'meals': [_meal('Eggs', 0), _meal('Salad', 1)],
        },
        {
          'day': 2,
          'meals': [_meal('Toast', 0), _meal('Soup', 1)],
        },
      ],
      'goals': {
        'daily_calories': 2000,
        'daily_protein_g': 150.0,
        'daily_fat_g_min': 50.0,
        'daily_fat_g_max': 70.0,
        'daily_carbs_g': 200.0,
      },
      'warnings': <String>[],
      'report': {'failures': <dynamic>[]},
    });

/// Fake meal-prep server: list / create / cancel against an in-memory list.
class FakeMealPrepServer {
  FakeMealPrepServer({List<MealPrepBatch>? batches})
      : batches = [...?batches];

  final List<MealPrepBatch> batches;
  int listCalls = 0;
  final List<Map<String, dynamic>> created = [];
  final List<String> cancelled = [];
  final List<PlanRequest> planRequests = [];

  /// Thrown by the next create instead of creating.
  ApiException? createError;

  /// Thrown by every list call while set.
  ApiException? listError;

  Future<List<MealPrepBatch>> list() async {
    listCalls++;
    final e = listError;
    if (e != null) throw e;
    return List.of(batches);
  }

  Future<MealPrepBatch> create({
    required String recipeId,
    required int totalServings,
    required String cookDate,
    required List<MealPrepAssignment> assignments,
  }) async {
    final e = createError;
    if (e != null) throw e;
    created.add({
      'recipe_id': recipeId,
      'total_servings': totalServings,
      'cook_date': cookDate,
      'assignments': [for (final a in assignments) a.toRequestJson()],
    });
    final b = MealPrepBatch(
      id: 'b${batches.length + 1}',
      recipeId: recipeId,
      totalServings: totalServings,
      assignedServings: assignments.length.toDouble(),
      remainingServings: (totalServings - assignments.length).toDouble(),
      cookDate: cookDate,
      status: 'active',
      assignments: assignments,
    );
    batches.add(b);
    return b;
  }

  Future<String> cancel(String id) async {
    cancelled.add(id);
    batches.removeWhere((b) => b.id == id);
    return id;
  }

  MealPlanProvider provider({MealPlan Function()? planResult}) =>
      MealPlanProvider(
        recipeSyncFn: (r) async =>
            RecipeSyncResult(syncedIds: [for (final x in r) x.id]),
        planFn: (req) async {
          planRequests.add(req);
          return (planResult ?? twoDayPlan)();
        },
        mealPrepListFn: list,
        mealPrepCreateFn: create,
        mealPrepCancelFn: cancel,
      );
}

Future<RecipeProvider> recipeProviderWith(List<Recipe> recipes) async {
  await StorageService.saveRecipes(recipes);
  final rp = RecipeProvider(
    recipeDetailFn: (id) async =>
        recipes.firstWhere((r) => r.id == id, orElse: () => throw StateError(id)),
    recipeListFn: () async => const [],
  );
  await rp.load();
  return rp;
}

Widget wrapWithProviders(
  Widget child, {
  required MealPlanProvider plan,
  required RecipeProvider recipes,
}) {
  return MultiProvider(
    providers: [
      ChangeNotifierProvider<MealPlanProvider>.value(value: plan),
      ChangeNotifierProvider<RecipeProvider>.value(value: recipes),
    ],
    child: MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(
        body: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: child,
        ),
      ),
    ),
  );
}
