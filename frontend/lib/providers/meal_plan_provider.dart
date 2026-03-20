import 'package:flutter/foundation.dart';

import '../models/models.dart';
import '../services/api_service.dart';

class MealPlanProvider extends ChangeNotifier {
  MealPlan? _mealPlan;
  bool _loading = false;
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
  String? get error => _error;
  int get days => _days;
  int get mealsPerDay => _mealsPerDay;
  Map<int, String> get workoutSchedule => Map.unmodifiable(_workoutSchedule);
  Set<String> get selectedRecipeIds => Set.unmodifiable(_selectedRecipeIds);
  String get planningMode => _planningMode;
  String get ingredientSource => _ingredientSource;

  void setPlanningMode(String mode) {
    _planningMode = mode;
    notifyListeners();
  }

  void setIngredientSource(String source) {
    _ingredientSource = source;
    notifyListeners();
  }

  void setDays(int days) {
    _days = days.clamp(1, 7);
    notifyListeners();
  }

  void setMealsPerDay(int meals) {
    _mealsPerDay = meals.clamp(1, 8);
    notifyListeners();
  }

  void setWorkoutDay(int dayIndex, String? timing) {
    if (timing == null) {
      _workoutSchedule.remove(dayIndex);
    } else {
      _workoutSchedule[dayIndex] = timing;
    }
    notifyListeners();
  }

  void toggleRecipe(String recipeId) {
    if (_selectedRecipeIds.contains(recipeId)) {
      _selectedRecipeIds.remove(recipeId);
    } else {
      _selectedRecipeIds.add(recipeId);
    }
    notifyListeners();
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

  void clearPlan() {
    _mealPlan = null;
    _error = null;
    notifyListeners();
  }
}
