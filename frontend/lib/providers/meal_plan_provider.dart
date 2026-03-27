import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/models.dart';
import '../models/recipe.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

/// Deterministic default busyness: first → 2, middle → 2–3, last → 3–4.
int defaultMealBusyness(int mealIndex, int mealCount) {
  if (mealCount <= 0) return 2;
  if (mealCount == 1) return 2;
  if (mealIndex == 0) return 2;
  if (mealIndex == mealCount - 1) {
    return mealCount >= 3 ? 4 : 3;
  }
  return 2 + (mealIndex % 2);
}

List<String>? defaultMealTags(int mealIndex, int mealCount) {
  if (mealCount >= 3) {
    if (mealIndex == 0) return ['breakfast'];
    if (mealIndex == mealCount - 1) return ['dinner'];
    if (mealIndex == mealCount ~/ 2) return ['lunch'];
  }
  return null;
}

DaySchedule buildDefaultDaySchedule(int dayIndex, int mealCount) {
  final n = mealCount.clamp(1, 8);
  final meals = List<MealSlot>.generate(
    n,
    (i) => MealSlot(
      index: i + 1,
      busynessLevel: defaultMealBusyness(i, n),
      tags: defaultMealTags(i, n),
      preferredTime: null,
    ),
  );
  return DaySchedule(dayIndex: dayIndex, meals: meals, workouts: const []);
}

/// Map legacy UI timing to one canonical workout in a meal gap.
List<WorkoutSlot> legacyTimingToWorkouts(int mealCount, String timing) {
  if (mealCount < 2) return [];
  final lastGap = mealCount - 1;
  switch (timing) {
    case 'morning':
      return [
        const WorkoutSlot(afterMealIndex: 1, type: 'AM', intensity: null),
      ];
    case 'afternoon':
      final gap = mealCount >= 3 ? 2 : 1;
      return [
        WorkoutSlot(
          afterMealIndex: gap.clamp(1, lastGap),
          type: 'general',
          intensity: null,
        ),
      ];
    case 'evening':
      return [
        WorkoutSlot(afterMealIndex: lastGap, type: 'PM', intensity: null),
      ];
    default:
      return [];
  }
}

class MealPlanProvider extends ChangeNotifier {
  MealPlan? _mealPlan;
  bool _loading = false;
  bool _syncing = false;
  String? _error;

  int _days = 7;
  /// Per-day canonical schedule; length always equals [_days].
  List<DaySchedule> _scheduleDays = [];

  final Set<String> _selectedRecipeIds = {};
  /// Matches backend `planning_mode`; keep `deterministic` until assisted UX is gated.
  String _planningMode = 'deterministic';
  /// `local` | `api` per OpenAPI / server PlanRequest.
  String _ingredientSource = 'local';

  MealPlanProvider() {
    _scheduleDays = List.generate(
      _days,
      (i) => buildDefaultDaySchedule(i + 1, 3),
    );
  }

  MealPlan? get mealPlan => _mealPlan;
  bool get loading => _loading;
  bool get syncing => _syncing;
  String? get error => _error;
  int get days => _days;
  List<DaySchedule> get scheduleDays => List.unmodifiable(_scheduleDays);
  Set<String> get selectedRecipeIds => Set.unmodifiable(_selectedRecipeIds);
  String get planningMode => _planningMode;
  String get ingredientSource => _ingredientSource;

  /// First day meal count (for compact summary strings).
  int get mealsPerDaySummary =>
      _scheduleDays.isEmpty ? 3 : _scheduleDays.first.meals.length;

  Future<void> load() async {
    final raw = await StorageService.loadPlannerConfig();
    if (raw == null) return;

    _days = (raw['days'] as num?)?.toInt().clamp(1, 7) ?? _days;

    final sd = raw['schedule_days'];
    if (sd is List && sd.isNotEmpty) {
      _scheduleDays = sd
          .map((e) => DaySchedule.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      while (_scheduleDays.length < _days) {
        final template = _scheduleDays.last;
        _scheduleDays.add(
          buildDefaultDaySchedule(
            _scheduleDays.length + 1,
            template.meals.length,
          ),
        );
      }
      if (_scheduleDays.length > _days) {
        _scheduleDays = _scheduleDays.sublist(0, _days);
      }
      _renumberDayIndices();
    } else {
      final mpd =
          (raw['meals_per_day'] as num?)?.toInt().clamp(1, 8) ?? 3;
      _scheduleDays = [];
      final ws = raw['workout_schedule'];
      for (var d = 0; d < _days; d++) {
        String? timing;
        if (ws is Map) {
          for (final e in ws.entries) {
            final idx = int.tryParse(e.key.toString());
            if (idx == d && e.value is String) {
              timing = e.value as String;
              break;
            }
          }
        }
        var day = buildDefaultDaySchedule(d + 1, mpd);
        if (timing != null) {
          final w = legacyTimingToWorkouts(day.meals.length, timing);
          day = DaySchedule(
            dayIndex: day.dayIndex,
            meals: day.meals,
            workouts: w,
          );
        }
        _scheduleDays.add(day);
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

  void _renumberDayIndices() {
    _scheduleDays = [
      for (var i = 0; i < _scheduleDays.length; i++)
        DaySchedule(
          dayIndex: i + 1,
          meals: _scheduleDays[i].meals,
          workouts: _scheduleDays[i].workouts,
        ),
    ];
  }

  Future<void> _persistConfig() => StorageService.savePlannerConfig({
        'days': _days,
        'schedule_days': _scheduleDays.map((d) => d.toJson()).toList(),
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
    while (_scheduleDays.length < _days) {
      final mc = _scheduleDays.isNotEmpty ? _scheduleDays.last.meals.length : 3;
      _scheduleDays.add(buildDefaultDaySchedule(_scheduleDays.length + 1, mc));
    }
    while (_scheduleDays.length > _days) {
      _scheduleDays.removeLast();
    }
    _renumberDayIndices();
    notifyListeners();
    unawaited(_persistConfig());
  }

  void setMealCountForDay(int dayIndex0, int mealCount) {
    if (dayIndex0 < 0 || dayIndex0 >= _scheduleDays.length) return;
    final n = mealCount.clamp(1, 8);
    final meals = List<MealSlot>.generate(
      n,
      (i) => MealSlot(
        index: i + 1,
        busynessLevel: defaultMealBusyness(i, n),
        tags: defaultMealTags(i, n),
        preferredTime: null,
      ),
    );
    var w = List<WorkoutSlot>.from(_scheduleDays[dayIndex0].workouts);
    w = w
        .where((x) => x.afterMealIndex >= 1 && x.afterMealIndex < n)
        .toList();
    if (w.length > 2) w = w.take(2).toList();
    _scheduleDays[dayIndex0] = DaySchedule(
      dayIndex: dayIndex0 + 1,
      meals: meals,
      workouts: w,
    );
    _renumberDayIndices();
    notifyListeners();
    unawaited(_persistConfig());
  }

  void setMealBusyness(int dayIndex0, int mealIndex0, int level) {
    if (dayIndex0 < 0 || dayIndex0 >= _scheduleDays.length) return;
    final day = _scheduleDays[dayIndex0];
    if (mealIndex0 < 0 || mealIndex0 >= day.meals.length) return;
    final b = level.clamp(1, 4);
    final meals = List<MealSlot>.from(day.meals);
    final m = meals[mealIndex0];
    meals[mealIndex0] = MealSlot(
      index: m.index,
      busynessLevel: b,
      tags: m.tags,
      preferredTime: m.preferredTime,
    );
    _scheduleDays[dayIndex0] = DaySchedule(
      dayIndex: day.dayIndex,
      meals: meals,
      workouts: day.workouts,
    );
    notifyListeners();
    unawaited(_persistConfig());
  }

  void addWorkoutInGap(int dayIndex0, int afterMealIndex) {
    if (dayIndex0 < 0 || dayIndex0 >= _scheduleDays.length) return;
    final day = _scheduleDays[dayIndex0];
    final n = day.meals.length;
    if (n < 2) return;
    if (afterMealIndex < 1 || afterMealIndex >= n) return;
    var w = List<WorkoutSlot>.from(day.workouts);
    if (w.any((x) => x.afterMealIndex == afterMealIndex)) return;
    if (w.length >= 2) return;
    w.add(
      WorkoutSlot(
        afterMealIndex: afterMealIndex,
        type: 'general',
        intensity: null,
      ),
    );
    _scheduleDays[dayIndex0] = DaySchedule(
      dayIndex: day.dayIndex,
      meals: day.meals,
      workouts: w,
    );
    notifyListeners();
    unawaited(_persistConfig());
  }

  void removeWorkoutAt(int dayIndex0, int workoutListIndex) {
    if (dayIndex0 < 0 || dayIndex0 >= _scheduleDays.length) return;
    final day = _scheduleDays[dayIndex0];
    if (workoutListIndex < 0 || workoutListIndex >= day.workouts.length) {
      return;
    }
    final w = List<WorkoutSlot>.from(day.workouts)..removeAt(workoutListIndex);
    _scheduleDays[dayIndex0] = DaySchedule(
      dayIndex: day.dayIndex,
      meals: day.meals,
      workouts: w,
    );
    notifyListeners();
    unawaited(_persistConfig());
  }

  /// Request payload: one [DaySchedule] per planning day.
  List<DaySchedule> scheduleDaysForApi() =>
      List<DaySchedule>.from(_scheduleDays);

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

  void applyPlanResult(MealPlan plan) {
    _mealPlan = plan;
    _error = null;
    notifyListeners();
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
}
