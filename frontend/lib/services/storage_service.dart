import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/ingredient.dart';
import '../models/recipe.dart';
import '../models/user_profile.dart';

class StorageService {
  static const _profileKey = 'user_profile';
  static const _plannerConfigKey = 'planner_config';
  static const _ingredientsKey = 'ingredients';
  static const _recipesKey = 'recipes';
  /// Local-only cooked meal slots (`"$day:$mealIndex"`). Not synced to the server.
  static const _cookedSlotsKey = 'cooked_slots';
  /// Local-only favorite recipe ids. Not a planner tag / not synced.
  static const _favoriteRecipeIdsKey = 'favorite_recipe_ids';

  static Future<void> saveProfile(UserProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_profileKey, jsonEncode(profile.toJson()));
  }

  static Future<UserProfile?> loadProfile() async {
    final prefs = await SharedPreferences.getInstance();
    final json = prefs.getString(_profileKey);
    if (json == null) return null;
    return UserProfile.fromJson(jsonDecode(json) as Map<String, dynamic>);
  }

  /// Meal planner UI state (days, recipe pool selection, etc.) — not the generated plan.
  static Future<void> savePlannerConfig(Map<String, dynamic> json) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_plannerConfigKey, jsonEncode(json));
  }

  static Future<Map<String, dynamic>?> loadPlannerConfig() async {
    final prefs = await SharedPreferences.getInstance();
    final json = prefs.getString(_plannerConfigKey);
    if (json == null) return null;
    return jsonDecode(json) as Map<String, dynamic>;
  }

  static Future<void> saveIngredients(List<Ingredient> ingredients) async {
    final prefs = await SharedPreferences.getInstance();
    final json = jsonEncode(ingredients.map((e) => e.toJson()).toList());
    await prefs.setString(_ingredientsKey, json);
  }

  static Future<List<Ingredient>> loadIngredients() async {
    final prefs = await SharedPreferences.getInstance();
    final json = prefs.getString(_ingredientsKey);
    if (json == null) return [];
    final list = jsonDecode(json) as List<dynamic>;
    return list
        .map((e) => Ingredient.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  static Future<void> saveRecipes(List<Recipe> recipes) async {
    final prefs = await SharedPreferences.getInstance();
    final json = jsonEncode(recipes.map((e) => e.toJson()).toList());
    await prefs.setString(_recipesKey, json);
  }

  static Future<List<Recipe>> loadRecipes() async {
    final prefs = await SharedPreferences.getInstance();
    final json = prefs.getString(_recipesKey);
    if (json == null) return [];
    final list = jsonDecode(json) as List<dynamic>;
    return list
        .map((e) => Recipe.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Persists cooked slot keys (`"${day}:${mealIndex}"`, 1-based day, 0-based index).
  static Future<void> saveCookedSlots(Set<String> keys) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_cookedSlotsKey, keys.toList()..sort());
  }

  static Future<Set<String>> loadCookedSlots() async {
    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList(_cookedSlotsKey);
    if (list == null) return {};
    return list.where((k) => k.isNotEmpty).toSet();
  }

  /// Persists favorite recipe ids (device-local only).
  static Future<void> saveFavoriteRecipeIds(Set<String> ids) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_favoriteRecipeIdsKey, ids.toList()..sort());
  }

  static Future<Set<String>> loadFavoriteRecipeIds() async {
    final prefs = await SharedPreferences.getInstance();
    final list = prefs.getStringList(_favoriteRecipeIdsKey);
    if (list == null) return {};
    return list.where((id) => id.isNotEmpty).toSet();
  }
}
