import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/models.dart';
import '../models/recipe.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

class MealPlanProvider extends ChangeNotifier {
  MealPlan? _mealPlan;
  bool _loading = false;
  bool _syncing = false;
  String? _error;

  // Planner config state
  int _days = 7;
  int _mealsPerDay = 3;
  final Map<int, String> _workoutSchedule = {}; // day index -> timing ('morning', 'afternoon', 'evening') or absent = rest
  final Set<String> _selectedRecipeIds = {};
  /// Matches backend `planning_mode`; keep `deterministic` until assisted UX is gated.
  String _planningMode = 'deterministic';
  /// `local` | `api` per OpenAPI / server PlanRequest.
  String _ingredientSource = 'local';

  MealPlan? get mealPlan => _mealPlan;
  bool get loading => _loading;
  bool get syncing => _syncing;
  String? get error => _error;
  int get days => _days;
  int get mealsPerDay => _mealsPerDay;
  Map<int, String> get workoutSchedule => Map.unmodifiable(_workoutSchedule);
  Set<String> get selectedRecipeIds => Set.unmodifiable(_selectedRecipeIds);
  String get planningMode => _planningMode;
  String get ingredientSource => _ingredientSource;

  Future<void> load() async {
    final raw = await StorageService.loadPlannerConfig();
    if (raw == null) return;

    _days = (raw['days'] as num?)?.toInt().clamp(1, 7) ?? _days;
    _mealsPerDay =
        (raw['meals_per_day'] as num?)?.toInt().clamp(1, 8) ?? _mealsPerDay;

    _workoutSchedule.clear();
    final ws = raw['workout_schedule'];
    if (ws is Map) {
      for (final e in ws.entries) {
        final idx = int.tryParse(e.key.toString());
        final v = e.value;
        if (idx != null && v is String && idx >= 0 && idx < _days) {
          _workoutSchedule[idx] = v;
        }
      }
    }

    _selectedRecipeIds.clear();
    final ids = raw['selected_recipe_ids'];
    if (ids is List) {
      for (final id in ids) {
        if (id is String && id.isNotEmpty) _selectedRecipeIds.add(id);
      }
    }

    final mode = raw['planning_mode'] as String?;
    if (mode != null && mode.isNotEmpty) _planningMode = mode;

    final ingSrc = raw['ingredient_source'] as String?;
    if (ingSrc != null && ingSrc.isNotEmpty) _ingredientSource = ingSrc;

    notifyListeners();
  }

  Future<void> _persistConfig() => StorageService.savePlannerConfig({
        'days': _days,
        'meals_per_day': _mealsPerDay,
        'workout_schedule': {
          for (final e in _workoutSchedule.entries) '${e.key}': e.value,
        },
        'selected_recipe_ids': _selectedRecipeIds.toList(),
        'planning_mode': _planningMode,
        'ingredient_source': _ingredientSource,
      });

  void setPlanningMode(String mode) {
    _planningMode = mode;
    notifyListeners();
    unawaited(_persistConfig());
  }

  void setIngredientSource(String source) {
    _ingredientSource = source;
    notifyListeners();
    unawaited(_persistConfig());
  }

  void setDays(int days) {
    _days = days.clamp(1, 7);
    _workoutSchedule.removeWhere((k, _) => k >= _days);
    notifyListeners();
    unawaited(_persistConfig());
  }

  void setMealsPerDay(int meals) {
    _mealsPerDay = meals.clamp(1, 8);
    notifyListeners();
    unawaited(_persistConfig());
  }

  void setWorkoutDay(int dayIndex, String? timing) {
    if (timing == null) {
      _workoutSchedule.remove(dayIndex);
    } else {
      _workoutSchedule[dayIndex] = timing;
    }
    notifyListeners();
    unawaited(_persistConfig());
  }

  void toggleRecipe(String recipeId) {
    if (_selectedRecipeIds.contains(recipeId)) {
      _selectedRecipeIds.remove(recipeId);
    } else {
      _selectedRecipeIds.add(recipeId);
    }
    notifyListeners();
    unawaited(_persistConfig());
  }

  Future<void> generatePlan(PlanRequest request) async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      _mealPlan = await ApiService.plan(request);
    } catch (e) {
      _error = e is ApiException ? e.message : e.toString();
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  /// Uploads [recipesToSync] then runs [generatePlan]. On sync failure, plan is not called.
  Future<void> generatePlanWithRecipeSync({
    required List<Recipe> recipesToSync,
    required PlanRequest request,
  }) async {
    _syncing = true;
    _error = null;
    notifyListeners();

    try {
      await ApiService.syncRecipes(recipesToSync);
    } catch (e) {
      _error = e is ApiException ? e.message : e.toString();
      return;
    } finally {
      _syncing = false;
      notifyListeners();
    }

    await generatePlan(request);
  }

  void clearPlan() {
    _mealPlan = null;
    _error = null;
    notifyListeners();
  }
}
