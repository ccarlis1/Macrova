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
  String? _errorCode;
  String? _errorMessage;

  int _days = 7;
  /// Per-day canonical schedule; length always equals [_days].
  List<DaySchedule> _scheduleDays = [];

  final Set<String> _selectedRecipeIds = {};
  /// Matches backend `planning_mode`; keep `deterministic` until assisted UX is gated.
  String _planningMode = 'deterministic';
  /// `local` | `api` per OpenAPI / server PlanRequest.
  String _ingredientSource = 'local';

  /// Pool-level tag filters (hard AND constraints on the server).
  final List<String> _cuisine = [];
  String? _costLevel;
  String? _prepTimeBucket;
  final List<String> _dietaryFlags = [];

  /// Local-only cooked slots (`"$day:$mealIndex"`). Cleared on successful new plan.
  final Set<String> _cookedSlots = {};

  static const Set<String> allowedCostLevels = {
    'cheap',
    'standard',
    'premium',
  };
  static const Set<String> allowedPrepTimeBuckets = {
    'snack',
    'quick_meal',
    'weeknight_meal',
    'meal_prep',
  };
  static const Set<String> allowedDietaryFlags = {
    'vegetarian',
    'vegan',
    'gluten_free',
    'dairy_free',
  };

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
  String? get errorCode => _errorCode;
  String? get errorMessage => _errorMessage;
  int get days => _days;
  List<DaySchedule> get scheduleDays => List.unmodifiable(_scheduleDays);
  Set<String> get selectedRecipeIds => Set.unmodifiable(_selectedRecipeIds);
  String get planningMode => _planningMode;
  String get ingredientSource => _ingredientSource;

  List<String> get cuisine => List.unmodifiable(_cuisine);
  String? get costLevel => _costLevel;
  String? get prepTimeBucket => _prepTimeBucket;
  List<String> get dietaryFlags => List.unmodifiable(_dietaryFlags);

  /// Device-local cooked slot keys; not sent to the planner or API.
  Set<String> get cookedSlots => Set.unmodifiable(_cookedSlots);

  /// Slot key: 1-based [day], 0-based [mealIndex] within that day's meals.
  static String cookedSlotKey(int day, int mealIndex) => '$day:$mealIndex';

  bool isCooked(int day, int mealIndex) =>
      _cookedSlots.contains(cookedSlotKey(day, mealIndex));

  /// Count of active pool-filter dimensions (for CTA detail).
  int get activePoolFilterCount {
    var n = 0;
    if (_cuisine.isNotEmpty) n++;
    if (_costLevel != null) n++;
    if (_prepTimeBucket != null) n++;
    if (_dietaryFlags.isNotEmpty) n++;
    return n;
  }

  bool get hasActivePoolFilters => activePoolFilterCount > 0;

  /// First day meal count (for compact summary strings).
  int get mealsPerDaySummary =>
      _scheduleDays.isEmpty ? 3 : _scheduleDays.first.meals.length;

  Future<void> load() async {
    _cookedSlots
      ..clear()
      ..addAll(await StorageService.loadCookedSlots());

    final raw = await StorageService.loadPlannerConfig();
    if (raw == null) {
      notifyListeners();
      return;
    }

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

    _cuisine.clear();
    final cuisineRaw = raw['cuisine'];
    if (cuisineRaw is List) {
      for (final c in cuisineRaw) {
        if (c is String && c.isNotEmpty) _cuisine.add(c);
      }
    }

    final cost = raw['cost_level'] as String?;
    _costLevel =
        (cost != null && allowedCostLevels.contains(cost)) ? cost : null;

    final prep = raw['prep_time_bucket'] as String?;
    _prepTimeBucket =
        (prep != null && allowedPrepTimeBuckets.contains(prep)) ? prep : null;

    _dietaryFlags.clear();
    final dietaryRaw = raw['dietary_flags'];
    if (dietaryRaw is List) {
      for (final f in dietaryRaw) {
        if (f is String && allowedDietaryFlags.contains(f)) {
          _dietaryFlags.add(f);
        }
      }
    }

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
        'cuisine': List<String>.from(_cuisine),
        'cost_level': _costLevel,
        'prep_time_bucket': _prepTimeBucket,
        'dietary_flags': List<String>.from(_dietaryFlags),
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

  void toggleCuisine(String value) {
    if (value.isEmpty) return;
    if (_cuisine.contains(value)) {
      _cuisine.remove(value);
    } else {
      _cuisine.add(value);
    }
    notifyListeners();
    unawaited(_persistConfig());
  }

  void clearCuisine() {
    if (_cuisine.isEmpty) return;
    _cuisine.clear();
    notifyListeners();
    unawaited(_persistConfig());
  }

  /// Single-select; pass null or the current value again to clear.
  void setCostLevel(String? value) {
    if (value != null && !allowedCostLevels.contains(value)) return;
    final next = (value != null && value == _costLevel) ? null : value;
    if (next == _costLevel) return;
    _costLevel = next;
    notifyListeners();
    unawaited(_persistConfig());
  }

  /// Single-select; pass null or the current value again to clear.
  void setPrepTimeBucket(String? value) {
    if (value != null && !allowedPrepTimeBuckets.contains(value)) return;
    final next =
        (value != null && value == _prepTimeBucket) ? null : value;
    if (next == _prepTimeBucket) return;
    _prepTimeBucket = next;
    notifyListeners();
    unawaited(_persistConfig());
  }

  void toggleDietaryFlag(String value) {
    if (!allowedDietaryFlags.contains(value)) return;
    if (_dietaryFlags.contains(value)) {
      _dietaryFlags.remove(value);
    } else {
      _dietaryFlags.add(value);
    }
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

  void _setError(Object e) {
    if (e is ApiException) {
      _errorCode = e.code;
      _errorMessage = e.message;
      _error = e.message;
    } else {
      _errorCode = null;
      _errorMessage = e.toString();
      _error = e.toString();
    }
  }

  void _clearError() {
    _error = null;
    _errorCode = null;
    _errorMessage = null;
  }

  /// Test-only: apply the same error mapping used by [generatePlan] catch.
  @visibleForTesting
  void debugSetError(Object e) => _setError(e);

  Future<void> generatePlan(PlanRequest request) async {
    _loading = true;
    _clearError();
    notifyListeners();

    try {
      _mealPlan = await ApiService.plan(request);
      await _clearCookedSlots();
    } catch (e) {
      _setError(e);
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
    _clearError();
    notifyListeners();

    try {
      await ApiService.syncRecipes(recipesToSync);
    } catch (e) {
      _setError(e);
      return;
    } finally {
      _syncing = false;
      notifyListeners();
    }

    await generatePlan(request);
  }

  void clearPlan() {
    _mealPlan = null;
    _clearError();
    unawaited(_clearCookedSlots());
    notifyListeners();
  }

  void applyPlanResult(MealPlan plan) {
    _mealPlan = plan;
    _clearError();
    if (_cookedSlots.isNotEmpty) {
      _cookedSlots.clear();
      unawaited(StorageService.saveCookedSlots(_cookedSlots));
    }
    notifyListeners();
  }

  void toggleCooked(int day, int mealIndex) {
    final key = cookedSlotKey(day, mealIndex);
    if (_cookedSlots.contains(key)) {
      _cookedSlots.remove(key);
    } else {
      _cookedSlots.add(key);
    }
    notifyListeners();
    unawaited(StorageService.saveCookedSlots(_cookedSlots));
  }

  Future<void> _clearCookedSlots() async {
    if (_cookedSlots.isEmpty) return;
    _cookedSlots.clear();
    await StorageService.saveCookedSlots(_cookedSlots);
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
