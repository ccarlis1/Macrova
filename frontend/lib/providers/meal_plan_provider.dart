import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/meal_prep_batch.dart';
import '../models/models.dart';
import '../models/recipe.dart';
import '../models/recipe_sync_result.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

/// Plan warning for a recipe the pre-plan sync rejected.
String recipeSyncWarning(RecipeSyncError e) {
  final label = e.recipeLabel;
  return label == null
      ? 'A recipe was not synced, so the planner could not use it: ${e.raw}'
      : 'Recipe "$label" was not synced, so the planner could not use it: '
          '${e.message}';
}

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

/// Sends a plan request ([ApiService.plan] or a test fake).
typedef PlanRequestFn = Future<MealPlan> Function(PlanRequest request);

/// `GET /api/v1/meal_prep_batches` (active only) or a test fake.
typedef MealPrepListFn = Future<List<MealPrepBatch>> Function();

/// `POST /api/v1/meal_prep_batches` or a test fake.
typedef MealPrepCreateFn = Future<MealPrepBatch> Function({
  required String recipeId,
  required int totalServings,
  required String cookDate,
  required List<MealPrepAssignment> assignments,
});

/// `DELETE /api/v1/meal_prep_batches/{id}` or a test fake.
typedef MealPrepCancelFn = Future<String> Function(String batchId);

/// A plan slot a meal-prep batch can be assigned to (create-batch sheet).
/// [dayIndex] / [slotIndex] are 0-based, as in batch assignments and
/// `PlanFailure`; the plan shows the slot as day `dayIndex + 1`.
class PlanSlotOption {
  final int dayIndex;
  final int slotIndex;

  /// The meal planned there (`Meal.mealType · name`), or null when the slot
  /// only carries a slot failure.
  final String? label;

  const PlanSlotOption({
    required this.dayIndex,
    required this.slotIndex,
    this.label,
  });

  int get day => dayIndex + 1;
}

class MealPlanProvider extends ChangeNotifier {
  final RecipeListSyncFn _recipeSyncFn;
  final PlanRequestFn _planFn;
  final MealPrepListFn _mealPrepListFn;
  final MealPrepCreateFn _mealPrepCreateFn;
  final MealPrepCancelFn _mealPrepCancelFn;

  /// Active meal-prep batches as last fetched from the server (FE-14). The
  /// server owns them and applies them to every `/plan` itself; this list is
  /// only for the tray and the create-batch sheet, never sent with a plan.
  List<MealPrepBatch> _mealPrepBatches = const [];
  bool _mealPrepLoading = false;
  bool _mealPrepLoaded = false;
  String? _mealPrepErrorCode;
  String? _mealPrepErrorMessage;

  /// Meal-prep tray collapsed (device-local convenience; expanded by default).
  bool _mealPrepTrayCollapsed = false;

  MealPlan? _mealPlan;
  bool _loading = false;
  bool _syncing = false;
  String? _error;
  String? _errorCode;
  String? _errorMessage;

  /// Request behind the current plan when it came from [generatePlan]; null after
  /// [applyPlanResult] / [clearPlan] (e.g. agent `plan-from-text` results).
  PlanRequest? _lastRequest;

  int _days = 7;
  /// Per-day canonical schedule; length always equals [_days].
  List<DaySchedule> _scheduleDays = [];

  final Set<String> _selectedRecipeIds = {};
  /// Matches backend `planning_mode`. Assisted modes are only offered behind the
  /// `LlmConfigProvider` ready gate (Planner Config, FE-11 "Find a recipe").
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

  MealPlanProvider({
    RecipeListSyncFn? recipeSyncFn,
    PlanRequestFn? planFn,
    MealPrepListFn? mealPrepListFn,
    MealPrepCreateFn? mealPrepCreateFn,
    MealPrepCancelFn? mealPrepCancelFn,
  })  : _recipeSyncFn = recipeSyncFn ?? ApiService.syncRecipes,
        _planFn = planFn ?? ApiService.plan,
        _mealPrepListFn =
            mealPrepListFn ?? (() => ApiService.listMealPrepBatches()),
        _mealPrepCreateFn = mealPrepCreateFn ?? _apiCreateMealPrepBatch,
        _mealPrepCancelFn = mealPrepCancelFn ??
            ((id) => ApiService.cancelMealPrepBatch(id)) {
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
  PlanRequest? get lastRequest => _lastRequest;

  /// Whether [rerunLastRequest] can re-send the request behind the current plan.
  bool get canRerunLastRequest => _lastRequest != null;
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

  static Future<MealPrepBatch> _apiCreateMealPrepBatch({
    required String recipeId,
    required int totalServings,
    required String cookDate,
    required List<MealPrepAssignment> assignments,
  }) =>
      ApiService.createMealPrepBatch(
        recipeId: recipeId,
        totalServings: totalServings,
        cookDate: cookDate,
        assignments: assignments,
      );

  // ---------------------------------------------------------------------------
  // Meal-prep batches (FE-14). Server-owned; see [mealPrepBatches].

  /// Active batches from the last [loadMealPrepBatches] (server order).
  List<MealPrepBatch> get mealPrepBatches =>
      List.unmodifiable(_mealPrepBatches);
  bool get mealPrepLoading => _mealPrepLoading;

  /// True once a [loadMealPrepBatches] succeeded.
  bool get mealPrepLoaded => _mealPrepLoaded;

  /// Server `code` / message of the last failed list or cancel call.
  String? get mealPrepErrorCode => _mealPrepErrorCode;
  String? get mealPrepErrorMessage => _mealPrepErrorMessage;
  bool get mealPrepTrayCollapsed => _mealPrepTrayCollapsed;

  /// Fetches the active batches (`GET /meal_prep_batches?active=true`).
  /// A failure keeps the previous list and sets [mealPrepErrorCode].
  Future<void> loadMealPrepBatches() async {
    _mealPrepLoading = true;
    notifyListeners();
    try {
      _mealPrepBatches = await _mealPrepListFn();
      _mealPrepLoaded = true;
      _mealPrepErrorCode = null;
      _mealPrepErrorMessage = null;
    } catch (e) {
      _setMealPrepError(e);
    } finally {
      _mealPrepLoading = false;
      notifyListeners();
    }
  }

  void _setMealPrepError(Object e) {
    if (e is ApiException) {
      _mealPrepErrorCode = e.code;
      _mealPrepErrorMessage = e.message;
    } else {
      _mealPrepErrorCode = null;
      _mealPrepErrorMessage = e.toString();
    }
  }

  /// Creates a batch on the server, refreshes [mealPrepBatches], then re-runs
  /// the request behind the current plan (same mode) so the batch's fixed
  /// slots show up. A server rejection (`BATCH_CONFLICT`,
  /// `RECIPE_NOT_BATCHABLE`, `BATCH_INVALID`, `RECIPE_NOT_FOUND`) throws
  /// [ApiException] before anything else happens. Returns whether the plan
  /// was re-run (false when the plan didn't come from [generatePlan]).
  Future<bool> createMealPrepBatch({
    required String recipeId,
    required int totalServings,
    required String cookDate,
    required List<MealPrepAssignment> assignments,
  }) async {
    await _mealPrepCreateFn(
      recipeId: recipeId,
      totalServings: totalServings,
      cookDate: cookDate,
      assignments: assignments,
    );
    await loadMealPrepBatches();
    final last = _lastRequest;
    if (last == null) return false;
    await generatePlan(last);
    return true;
  }

  /// Cancels a batch (`DELETE`) and refreshes [mealPrepBatches]. Throws
  /// [ApiException] on failure. The current plan is not re-run: its batch
  /// meals stay until the next plan.
  Future<void> cancelMealPrepBatch(String batchId) async {
    await _mealPrepCancelFn(batchId);
    await loadMealPrepBatches();
  }

  void setMealPrepTrayCollapsed(bool collapsed) {
    if (collapsed == _mealPrepTrayCollapsed) return;
    _mealPrepTrayCollapsed = collapsed;
    notifyListeners();
    unawaited(StorageService.saveMealPrepTrayCollapsed(collapsed));
  }

  /// Slots of the current plan a batch can take: every planned meal (its
  /// `slot_index`, else its position) and every slot failure, by day then slot.
  /// Empty without a plan.
  List<PlanSlotOption> get planSlotOptions {
    final plan = _mealPlan;
    if (plan == null) return const [];
    final byKey = <(int, int), PlanSlotOption>{};
    for (final d in plan.dailyPlans) {
      for (var i = 0; i < d.meals.length; i++) {
        final m = d.meals[i];
        final slot = m.slotIndex ?? i;
        final name = m.recipe['name'] as String? ?? '';
        byKey[(d.day - 1, slot)] = PlanSlotOption(
          dayIndex: d.day - 1,
          slotIndex: slot,
          label: name.isEmpty ? m.mealType : '${m.mealType} · $name',
        );
      }
    }
    for (final f in plan.failures) {
      if (!f.isSlotFailure) continue;
      byKey.putIfAbsent(
        (f.dayIndex!, f.slotIndex!),
        () => PlanSlotOption(dayIndex: f.dayIndex!, slotIndex: f.slotIndex!),
      );
    }
    final out = byKey.values.toList()
      ..sort((a, b) => a.dayIndex != b.dayIndex
          ? a.dayIndex.compareTo(b.dayIndex)
          : a.slotIndex.compareTo(b.slotIndex));
    return out;
  }

  Future<void> load() async {
    _cookedSlots
      ..clear()
      ..addAll(await StorageService.loadCookedSlots());
    _mealPrepTrayCollapsed = await StorageService.loadMealPrepTrayCollapsed();

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

  /// Test-only: seed the request [rerunLastRequest] re-sends.
  @visibleForTesting
  void debugSetLastRequest(PlanRequest? request) => _lastRequest = request;

  Future<void> generatePlan(PlanRequest request) =>
      _generatePlan(request);

  /// [syncWarnings] (from [generatePlanWithRecipeSync]) become the plan's
  /// [MealPlan.syncWarnings], ahead of its own warnings.
  Future<void> _generatePlan(
    PlanRequest request, {
    List<String> syncWarnings = const [],
  }) async {
    _lastRequest = request;
    _loading = true;
    _clearError();
    notifyListeners();

    try {
      final plan = await _planFn(request);
      _mealPlan = syncWarnings.isEmpty
          ? plan
          : plan.withSyncWarnings(syncWarnings);
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

    final RecipeSyncResult synced;
    try {
      synced = await _recipeSyncFn(recipesToSync);
    } catch (e) {
      _setError(e);
      return;
    } finally {
      _syncing = false;
      notifyListeners();
    }

    // Rejected recipes (BE-19) aren't stored, so the planner can't use them:
    // say so on the plan instead of planning as if they were synced.
    await _generatePlan(
      request,
      syncWarnings: [
        for (final e in synced.errors) recipeSyncWarning(e),
      ],
    );
  }

  /// Re-send the request behind the current plan with another `planning_mode`
  /// (FE-11: `assisted` runs the server's diagnosed recipe recovery). One-off:
  /// the persisted [planningMode] is unchanged. No-op without a last request.
  Future<void> rerunLastRequest({required String planningMode}) async {
    final last = _lastRequest;
    if (last == null) return;
    await generatePlan(last.withPlanningMode(planningMode));
  }

  void clearPlan() {
    _lastRequest = null;
    _mealPlan = null;
    _clearError();
    unawaited(_clearCookedSlots());
    notifyListeners();
  }

  void applyPlanResult(MealPlan plan) {
    _lastRequest = null;
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
