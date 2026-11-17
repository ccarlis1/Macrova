import 'micronutrient_metadata.dart';
import 'user_profile.dart';

/// Turn `/api/v1/plan` [warnings] (object or list) into user-facing lines.
List<String> formatPlanApiWarnings(dynamic w) {
  if (w == null) return [];
  if (w is List) {
    return w.map((e) => e.toString()).toList();
  }
  if (w is! Map) {
    return [w.toString()];
  }
  final m = Map<String, dynamic>.from(w);
  final out = <String>[];

  String fmtNum(dynamic n) {
    if (n == null) return '?';
    if (n is num) {
      final d = n.toDouble();
      if ((d - d.round()).abs() < 1e-6) return d.round().toString();
      return d.toStringAsFixed(1);
    }
    return n.toString();
  }

  String fmtPct(dynamic n) {
    if (n is num) return '${(100 * n.toDouble()).toStringAsFixed(0)}%';
    return n?.toString() ?? '?';
  }

  final t = m['type']?.toString();
  if (t == 'sodium_advisory') {
    out.add(
      'Sodium advisory: weekly total about ${fmtNum(m['weekly_sodium_mg'])} mg '
      'vs recommended max ${fmtNum(m['recommended_max_mg'])} mg '
      '(${fmtNum(m['ratio'])}×).',
    );
  } else if (t == 'sodium_advisory_text') {
    final msg = m['message']?.toString();
    if (msg != null && msg.isNotEmpty) out.add(msg);
  }

  final soft = m['micronutrient_soft_deficit'];
  if (soft is List && soft.isNotEmpty) {
    out.add(
      'Micronutrients between τ-floor and full weekly RDI (for transparency):',
    );
    for (final raw in soft) {
      if (raw is Map) {
        final item = Map<String, dynamic>.from(raw);
        final key = item['nutrient']?.toString() ?? '?';
        final label = micronutrientLabelForKey(key);
        final unit = micronutrientUnitForKey(key);
        final um = unit.isNotEmpty ? ' $unit' : '';
        out.add(
          '  • $label: ${fmtNum(item['achieved'])}$um / ${fmtNum(item['full_req'])}$um '
          '(${fmtPct(item['fraction_of_full'])} of full weekly target)',
        );
      }
    }
  }

  if (out.isEmpty && m.isNotEmpty) {
    m.forEach((k, v) {
      if (k == 'micronutrient_soft_deficit') return;
      out.add('$k: $v');
    });
  }
  return out;
}

// --- Canonical schedule contract (mirrors `src/models/schedule.py`) ---
//
// Invariants:
// - Workouts are never meals; they use [WorkoutSlot] only.
// - Meal `index` values are contiguous 1..N per day.
// - `after_meal_index` satisfies 1 <= i < meal_count (gap after meal i).
// - At most two workouts per day; no duplicate gap.

/// One assignable meal slot (JSON keys match backend `MealSlot`).
class MealSlot {
  final int index;
  final int busynessLevel;
  final List<String>? tags;
  final String? preferredTime;
  final List<String>? requiredTagSlugs;
  final List<String>? preferredTagSlugs;

  const MealSlot({
    required this.index,
    required this.busynessLevel,
    this.tags,
    this.preferredTime,
    this.requiredTagSlugs,
    this.preferredTagSlugs,
  });

  factory MealSlot.fromJson(Map<String, dynamic> json) {
    return MealSlot(
      index: json['index'] as int,
      busynessLevel: json['busyness_level'] as int,
      tags: (json['tags'] as List<dynamic>?)?.map((e) => e as String).toList(),
      preferredTime: json['preferred_time'] as String?,
      requiredTagSlugs: (json['required_tag_slugs'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
      preferredTagSlugs: (json['preferred_tag_slugs'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'index': index,
        'busyness_level': busynessLevel,
        if (tags != null) 'tags': tags,
        if (preferredTime != null) 'preferred_time': preferredTime,
        if (requiredTagSlugs != null) 'required_tag_slugs': requiredTagSlugs,
        if (preferredTagSlugs != null) 'preferred_tag_slugs': preferredTagSlugs,
      };
}

/// Workout in a gap after [afterMealIndex] (JSON keys match backend `WorkoutSlot`).
class WorkoutSlot {
  final int afterMealIndex;
  final String type;
  final String? intensity;

  const WorkoutSlot({
    required this.afterMealIndex,
    required this.type,
    this.intensity,
  });

  factory WorkoutSlot.fromJson(Map<String, dynamic> json) {
    return WorkoutSlot(
      afterMealIndex: json['after_meal_index'] as int,
      type: json['type'] as String,
      intensity: json['intensity'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'after_meal_index': afterMealIndex,
        'type': type,
        if (intensity != null) 'intensity': intensity,
      };
}

/// One day: meals + workouts (JSON keys match backend `DaySchedule`).
class DaySchedule {
  final int dayIndex;
  final List<MealSlot> meals;
  final List<WorkoutSlot> workouts;

  const DaySchedule({
    required this.dayIndex,
    required this.meals,
    this.workouts = const [],
  });

  factory DaySchedule.fromJson(Map<String, dynamic> json) {
    final mealsRaw = json['meals'] as List<dynamic>? ?? const [];
    final workoutsRaw = json['workouts'] as List<dynamic>? ?? const [];
    return DaySchedule(
      dayIndex: json['day_index'] as int,
      meals: mealsRaw
          .map((e) => MealSlot.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
      workouts: workoutsRaw
          .map((e) => WorkoutSlot.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
        'day_index': dayIndex,
        'meals': meals.map((m) => m.toJson()).toList(),
        'workouts': workouts.map((w) => w.toJson()).toList(),
      };
}

class PlanRequest {
  final int dailyCalories;
  final double dailyProteinG;
  final double dailyFatGMin;
  final double dailyFatGMax;
  /// Deprecated legacy map: `"HH:MM"` -> busyness 1–4 or 0 for workout time.
  /// Prefer [scheduleDays].
  final Map<String, int>? schedule;
  /// Canonical schedule (preferred). When set, length must equal [days].
  final List<DaySchedule>? scheduleDays;
  final List<String> likedFoods;
  final List<String> dislikedFoods;
  final List<String> allergies;
  final int days;
  final String ingredientSource;
  final Map<String, double>? micronutrientGoals;
  final double micronutrientWeeklyMinFraction;
  /// HC-5 hard daily calorie ceiling. Omitted from JSON when null.
  final int? maxDailyCalories;
  final String? planningMode;
  final List<String>? recipeIds;
  // Canonical pool-level tag filtering fields (backed by recipe_tags.json).
  final List<String>? cuisine;
  final String? costLevel;
  final String? prepTimeBucket;
  final List<String>? dietaryFlags;
  final String? recipeTagsPath;
  /// BE-17: demographic whose daily upper limits the server enforces. Sent only
  /// when it is one of [UserProfile.supportedDemographics]; does not set
  /// micronutrient goals.
  final String? demographic;

  const PlanRequest({
    required this.dailyCalories,
    required this.dailyProteinG,
    required this.dailyFatGMin,
    required this.dailyFatGMax,
    this.schedule,
    this.scheduleDays,
    this.likedFoods = const [],
    this.dislikedFoods = const [],
    this.allergies = const [],
    this.days = 1,
    this.ingredientSource = 'local',
    this.micronutrientGoals,
    this.micronutrientWeeklyMinFraction = 1.0,
    this.maxDailyCalories,
    this.planningMode,
    this.recipeIds,
    this.cuisine,
    this.costLevel,
    this.prepTimeBucket,
    this.dietaryFlags,
    this.recipeTagsPath,
    this.demographic,
  });

  factory PlanRequest.fromJson(Map<String, dynamic> json) {
    final schedRaw = json['schedule'];
    Map<String, int>? sched;
    if (schedRaw is Map) {
      sched = {
        for (final e in schedRaw.entries)
          e.key.toString(): (e.value as num).toInt(),
      };
    }
    final sdRaw = json['schedule_days'] as List<dynamic>?;
    return PlanRequest(
      dailyCalories: json['daily_calories'] as int,
      dailyProteinG: (json['daily_protein_g'] as num).toDouble(),
      dailyFatGMin: (json['daily_fat_g_min'] as num).toDouble(),
      dailyFatGMax: (json['daily_fat_g_max'] as num).toDouble(),
      schedule: sched,
      scheduleDays: sdRaw
          ?.map((e) => DaySchedule.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
      likedFoods: List<String>.from(json['liked_foods'] ?? const []),
      dislikedFoods: List<String>.from(json['disliked_foods'] ?? const []),
      allergies: List<String>.from(json['allergies'] ?? const []),
      days: json['days'] as int? ?? 1,
      ingredientSource: json['ingredient_source'] as String? ?? 'local',
      micronutrientGoals: (json['micronutrient_goals'] as Map<String, dynamic>?)
          ?.map((k, v) => MapEntry(k, (v as num).toDouble())),
      micronutrientWeeklyMinFraction:
          (json['micronutrient_weekly_min_fraction'] as num?)?.toDouble() ??
              1.0,
      maxDailyCalories: (json['max_daily_calories'] as num?)?.toInt(),
      planningMode: json['planning_mode'] as String?,
      recipeIds: (json['recipe_ids'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
      cuisine: (json['cuisine'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
      costLevel: json['cost_level'] as String?,
      prepTimeBucket: json['prep_time_bucket'] as String?,
      dietaryFlags: (json['dietary_flags'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
      recipeTagsPath: json['recipe_tags_path'] as String?,
      demographic: json['demographic'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{
      'daily_calories': dailyCalories,
      'daily_protein_g': dailyProteinG,
      'daily_fat_g_min': dailyFatGMin,
      'daily_fat_g_max': dailyFatGMax,
      'liked_foods': likedFoods,
      'disliked_foods': dislikedFoods,
      'allergies': allergies,
      'days': days,
      'ingredient_source': ingredientSource,
      'micronutrient_weekly_min_fraction': micronutrientWeeklyMinFraction,
    };
    final s = schedule;
    if (s != null) {
      map['schedule'] = s;
    }
    final sd = scheduleDays;
    if (sd != null) {
      map['schedule_days'] = sd.map((d) => d.toJson()).toList();
    }
    final micros = micronutrientGoals;
    if (micros != null && micros.isNotEmpty) {
      map['micronutrient_goals'] = micros;
    }
    final maxCals = maxDailyCalories;
    if (maxCals != null) {
      map['max_daily_calories'] = maxCals;
    }
    if (planningMode != null && planningMode!.isNotEmpty) {
      map['planning_mode'] = planningMode;
    }
    final ids = recipeIds;
    if (ids != null && ids.isNotEmpty) {
      map['recipe_ids'] = ids;
    }
    final cuisineValues = cuisine;
    if (cuisineValues != null && cuisineValues.isNotEmpty) {
      map['cuisine'] = cuisineValues;
    }
    if (costLevel != null && costLevel!.isNotEmpty) {
      map['cost_level'] = costLevel;
    }
    if (prepTimeBucket != null && prepTimeBucket!.isNotEmpty) {
      map['prep_time_bucket'] = prepTimeBucket;
    }
    final dietaryValues = dietaryFlags;
    if (dietaryValues != null && dietaryValues.isNotEmpty) {
      map['dietary_flags'] = dietaryValues;
    }
    if (recipeTagsPath != null && recipeTagsPath!.isNotEmpty) {
      map['recipe_tags_path'] = recipeTagsPath;
    }
    final demo = UserProfile.normalizeDemographic(demographic);
    if (demo.isNotEmpty) {
      map['demographic'] = demo;
    }
    return map;
  }

  /// Same request with a different `planning_mode` (every other field kept).
  PlanRequest withPlanningMode(String mode) => PlanRequest(
        dailyCalories: dailyCalories,
        dailyProteinG: dailyProteinG,
        dailyFatGMin: dailyFatGMin,
        dailyFatGMax: dailyFatGMax,
        schedule: schedule,
        scheduleDays: scheduleDays,
        likedFoods: likedFoods,
        dislikedFoods: dislikedFoods,
        allergies: allergies,
        days: days,
        ingredientSource: ingredientSource,
        micronutrientGoals: micronutrientGoals,
        micronutrientWeeklyMinFraction: micronutrientWeeklyMinFraction,
        maxDailyCalories: maxDailyCalories,
        planningMode: mode,
        recipeIds: recipeIds,
        cuisine: cuisine,
        costLevel: costLevel,
        prepTimeBucket: prepTimeBucket,
        dietaryFlags: dietaryFlags,
        recipeTagsPath: recipeTagsPath,
        demographic: demographic,
      );
}

class NutritionProfile {
  final double calories;
  final double proteinG;
  final double fatG;
  final double carbsG;
  /// Keys match backend `MicronutrientProfile` (e.g. `vitamin_a_ug`).
  final Map<String, double>? _micronutrients;

  /// Never null (avoids web / hot-reload edge cases where storage was omitted).
  Map<String, double> get micronutrients => _micronutrients ?? const {};

  const NutritionProfile({
    required this.calories,
    required this.proteinG,
    required this.fatG,
    required this.carbsG,
    Map<String, double>? micronutrients,
  }) : _micronutrients = micronutrients;

  factory NutritionProfile.fromJson(Map<String, dynamic> json) {
    final microRaw = json['micronutrients'];
    Map<String, double>? micros;
    if (microRaw is Map) {
      micros = {
        for (final e in microRaw.entries)
          if (e.value != null && e.value is num)
            e.key.toString(): (e.value as num).toDouble(),
      };
    }
    return NutritionProfile(
      calories: (json['calories'] as num).toDouble(),
      proteinG: (json['protein_g'] as num).toDouble(),
      fatG: (json['fat_g'] as num).toDouble(),
      carbsG: (json['carbs_g'] as num).toDouble(),
      micronutrients: micros,
    );
  }
}

/// One entry from `PlanResponse.report.failures[]` (OpenAPI `PlanFailure`).
class PlanFailure {
  final String code;
  final String message;
  final int? dayIndex;
  final int? slotIndex;
  final String? slotId;
  final String? date;
  final Map<String, dynamic> details;
  final String? fixHint;
  /// Plain-language headline (`src/api/failure_explanations.py`); null on old servers.
  final String? explanation;
  /// Plain-language one-line fix; null on old servers (fall back to [fixHint]).
  final String? fix;
  /// Diagnosis cause (`GapSpec.kind` / `UnrecoverableReason.code`); informational.
  final String? cause;

  const PlanFailure({
    required this.code,
    required this.message,
    this.dayIndex,
    this.slotIndex,
    this.slotId,
    this.date,
    this.details = const {},
    this.fixHint,
    this.explanation,
    this.fix,
    this.cause,
  });

  /// True when the failure names one meal slot (0-based [dayIndex] + [slotIndex]).
  bool get isSlotFailure => dayIndex != null && slotIndex != null;

  factory PlanFailure.fromJson(Map<String, dynamic> json) {
    final detailsRaw = json['details'];
    return PlanFailure(
      code: json['code'] as String? ?? '',
      message: json['message'] as String? ?? '',
      dayIndex: (json['day_index'] as num?)?.toInt(),
      slotIndex: (json['slot_index'] as num?)?.toInt(),
      slotId: json['slot_id'] as String?,
      date: json['date'] as String?,
      details: detailsRaw is Map
          ? Map<String, dynamic>.from(detailsRaw)
          : const {},
      fixHint: json['fix_hint'] as String?,
      explanation: json['explanation'] as String?,
      fix: json['fix'] as String?,
      cause: json['cause'] as String?,
    );
  }
}

/// `report.failure_cause.recipe_gap` (`PlanRecipeGap` in OpenAPI): what a new recipe
/// would need to satisfy. Indices in [slots] are 0-based `[day_index, slot_index]`.
class PlanRecipeGap {
  final double? perMealCalories;
  final double? perMealProteinG;
  final double? perMealFatGMax;
  final double? perMealCarbsG;
  final int? cookTimeCapMinutes;
  final List<String> excludedIngredients;
  final Map<String, double> nutrientMinPerRecipe;
  final List<String> mealTypes;
  final List<List<int>> slots;

  const PlanRecipeGap({
    this.perMealCalories,
    this.perMealProteinG,
    this.perMealFatGMax,
    this.perMealCarbsG,
    this.cookTimeCapMinutes,
    this.excludedIngredients = const [],
    this.nutrientMinPerRecipe = const {},
    this.mealTypes = const [],
    this.slots = const [],
  });

  factory PlanRecipeGap.fromJson(Map<String, dynamic> json) {
    List<String> strings(dynamic raw) => raw is List
        ? [for (final e in raw) if (e is String) e]
        : const [];
    final nutrientsRaw = json['nutrient_min_per_recipe'];
    final slotsRaw = json['slots'];
    return PlanRecipeGap(
      perMealCalories: (json['per_meal_calories'] as num?)?.toDouble(),
      perMealProteinG: (json['per_meal_protein_g'] as num?)?.toDouble(),
      perMealFatGMax: (json['per_meal_fat_g_max'] as num?)?.toDouble(),
      perMealCarbsG: (json['per_meal_carbs_g'] as num?)?.toDouble(),
      cookTimeCapMinutes: (json['cook_time_cap_minutes'] as num?)?.toInt(),
      excludedIngredients: strings(json['excluded_ingredients']),
      nutrientMinPerRecipe: nutrientsRaw is Map
          ? {
              for (final e in nutrientsRaw.entries)
                if (e.value is num)
                  e.key.toString(): (e.value as num).toDouble(),
            }
          : const {},
      mealTypes: strings(json['meal_types']),
      slots: slotsRaw is List
          ? [
              for (final s in slotsRaw)
                if (s is List)
                  [for (final i in s) if (i is num) i.toInt()],
            ]
          : const [],
    );
  }
}

/// `report.failure_cause` (`PlanFailureCause` in OpenAPI): plan-wide diagnosis.
class PlanFailureCause {
  final String? cause;
  final bool recipeCouldHelp;
  final PlanRecipeGap? recipeGap;

  const PlanFailureCause({
    this.cause,
    required this.recipeCouldHelp,
    this.recipeGap,
  });

  factory PlanFailureCause.fromJson(Map<String, dynamic> json) {
    final gapRaw = json['recipe_gap'];
    return PlanFailureCause(
      cause: json['cause'] as String?,
      recipeCouldHelp: json['recipe_could_help'] as bool? ?? false,
      recipeGap: gapRaw is Map
          ? PlanRecipeGap.fromJson(Map<String, dynamic>.from(gapRaw))
          : null,
    );
  }
}

class Meal {
  final String mealType;
  final Map<String, dynamic> recipe;
  final NutritionProfile nutrition;
  final int busynessLevel;
  /// §4.3: whether the recipe is tagged for [mealType]; null when unknown.
  final bool? mealTypeMatch;
  final String? recipeId;

  /// 0-based slot within the day (`PlannedMeal.slot_index`); a meal-prep
  /// batch assignment at the same `slot_index` lands here.
  final int? slotIndex;

  /// `PlannedMeal.source`: [sourceMealPrepBatch], [sourcePinnedAssignment] or
  /// [sourcePlanner]; null on older servers.
  final String? source;

  /// Meal-prep batch id when [source] is [sourceMealPrepBatch].
  final String? batchId;

  /// Batch servings used by this slot (batch meals only).
  final double? servings;

  static const sourceMealPrepBatch = 'meal_prep_batch';
  static const sourcePinnedAssignment = 'pinned_assignment';
  static const sourcePlanner = 'planner';

  /// True when the server placed this meal from a meal-prep batch (FE-14).
  bool get isMealPrepBatch => source == sourceMealPrepBatch;

  const Meal({
    required this.mealType,
    required this.recipe,
    required this.nutrition,
    required this.busynessLevel,
    this.mealTypeMatch,
    this.recipeId,
    this.slotIndex,
    this.source,
    this.batchId,
    this.servings,
  });

  /// One meal object from `POST /api/v1/plan` [`daily_plans[].meals`].
  factory Meal.fromPlanApiV1(Map<String, dynamic> m) {
    final recipeId = m['recipe_id']?.toString();
    final slotIndex = (m['slot_index'] as num?)?.toInt();
    final source = m['source'] as String?;
    final batchId = m['batch_id'] as String?;
    final servings = (m['servings'] as num?)?.toDouble();

    if (m['error'] != null) {
      return Meal(
        mealType: m['meal_type'] as String? ?? 'meal',
        recipe: {
          'name': 'Missing recipe ${m['recipe_id'] ?? ''}',
          'cooking_time_minutes': 0,
          'ingredients': <dynamic>[],
          'instructions': <dynamic>[],
        },
        nutrition: const NutritionProfile(
          calories: 0,
          proteinG: 0,
          fatG: 0,
          carbsG: 0,
        ),
        busynessLevel: 3,
        mealTypeMatch: m['meal_type_match'] as bool?,
        recipeId: recipeId,
        slotIndex: slotIndex,
        source: source,
        batchId: batchId,
        servings: servings,
      );
    }

    final nutritionMap =
        Map<String, dynamic>.from(m['nutrition'] as Map);
    final ingredientsRaw = m['ingredients'] as List<dynamic>? ?? const [];
    final ingredients = <Map<String, dynamic>>[
      for (final line in ingredientsRaw)
        {'display': line.toString()},
    ];

    return Meal(
      mealType: m['meal_type'] as String? ?? 'meal',
      recipe: {
        'name': m['name']?.toString() ?? 'Recipe',
        'cooking_time_minutes': m['cooking_time_minutes'],
        'ingredients': ingredients,
        'instructions': const <dynamic>[],
      },
      nutrition: NutritionProfile.fromJson(nutritionMap),
      busynessLevel: m['busyness_level'] as int? ?? 3,
      mealTypeMatch: m['meal_type_match'] as bool?,
      recipeId: recipeId,
      slotIndex: slotIndex,
      source: source,
      batchId: batchId,
      servings: servings,
    );
  }
}

class NutritionGoals {
  final int calories;
  final double proteinG;
  final double fatGMin;
  final double fatGMax;
  final double carbsG;

  const NutritionGoals({
    required this.calories,
    required this.proteinG,
    required this.fatGMin,
    required this.fatGMax,
    required this.carbsG,
  });

  /// Shaped like [format_result_json] `goals` on `/api/v1/plan`.
  factory NutritionGoals.fromPlanApi(Map<String, dynamic> g) {
    return NutritionGoals(
      calories: (g['daily_calories'] as num).round(),
      proteinG: (g['daily_protein_g'] as num).toDouble(),
      fatGMin: (g['daily_fat_g_min'] as num).toDouble(),
      fatGMax: (g['daily_fat_g_max'] as num).toDouble(),
      carbsG: (g['daily_carbs_g'] as num).toDouble(),
    );
  }
}

/// One calendar day from `POST /api/v1/plan` [`daily_plans[]`].
class MealPlanDay {
  /// 1-based index from API `day` field.
  final int day;
  final List<Meal> meals;
  /// Daily tracker totals when present; otherwise summed from [meals].
  final NutritionProfile dayTotals;

  const MealPlanDay({
    required this.day,
    required this.meals,
    required this.dayTotals,
  });
}

class MealPlan {
  final bool success;
  /// Per-day schedule from the API (order preserved).
  final List<MealPlanDay> dailyPlans;
  final NutritionProfile totalNutrition;
  final NutritionGoals goals;
  final List<String> warnings;
  /// Plan horizon from API `days` (used to scale daily profile targets for multi-day totals).
  final int days;
  /// UX branch key: `success` | `partial` | `failed` (not [terminationCode]).
  final String planStatus;
  final String? planStatusMessage;
  final List<PlanFailure> failures;
  /// `report.failure_cause`; null when nothing failed or on old servers.
  final PlanFailureCause? failureCause;
  /// Telemetry only (`TC-*`); do not use for UI branching.
  final String? terminationCode;

  /// Client-side warnings for recipes the pre-plan sync rejected (FE-13,
  /// `recipeSyncWarning`). Also at the head of [warnings]. Kept apart because
  /// they matter on a failed or partial plan too (a rejected recipe may be why
  /// it failed), where the server's [warnings] are not shown.
  final List<String> syncWarnings;

  /// This plan with [sync] as [syncWarnings], prepended to [warnings].
  MealPlan withSyncWarnings(List<String> sync) => _copy(
        warnings: [...sync, ...warnings],
        syncWarnings: sync,
      );

  MealPlan _copy({
    required List<String> warnings,
    List<String>? syncWarnings,
  }) =>
      MealPlan(
        success: success,
        dailyPlans: dailyPlans,
        totalNutrition: totalNutrition,
        goals: goals,
        warnings: List.unmodifiable(warnings),
        days: days,
        planStatus: planStatus,
        planStatusMessage: planStatusMessage,
        failures: failures,
        failureCause: failureCause,
        terminationCode: terminationCode,
        syncWarnings: List.unmodifiable(syncWarnings ?? this.syncWarnings),
      );

  /// All meals in plan order (flattened). Legacy / simple UIs.
  List<Meal> get meals =>
      dailyPlans.expand((d) => d.meals).toList(growable: false);

  const MealPlan({
    required this.success,
    required this.dailyPlans,
    required this.totalNutrition,
    required this.goals,
    required this.warnings,
    this.days = 1,
    this.planStatus = 'success',
    this.planStatusMessage,
    this.failures = const [],
    this.failureCause,
    this.terminationCode,
    this.syncWarnings = const [],
  });

  static Map<String, double> _microMapFromJson(dynamic raw) {
    if (raw is! Map) return const {};
    return raw.map(
      (k, v) => MapEntry(k.toString(), (v as num).toDouble()),
    );
  }

  /// Resolves plan-level micronutrient totals from `weekly_totals`, day `totals`, or summed meals.
  static Map<String, double> _planMicronutrientTotals(
    Map<String, dynamic> json,
    List<dynamic> dailyPlans,
    int days,
    List<Meal> meals,
  ) {
    if (days > 1) {
      final wt = json['weekly_totals'];
      if (wt is Map) {
        final wmap = Map<String, dynamic>.from(wt);
        final m = _microMapFromJson(wmap['micronutrients']);
        if (m.isNotEmpty) return m;
      }
      final acc = <String, double>{};
      for (final day in dailyPlans) {
        if (day is! Map) continue;
        final t = day['totals'];
        if (t is Map) {
          final tm = Map<String, dynamic>.from(t);
          for (final e in _microMapFromJson(tm['micronutrients']).entries) {
            acc[e.key] = (acc[e.key] ?? 0) + e.value;
          }
        }
      }
      if (acc.isNotEmpty) return acc;
    } else if (dailyPlans.isNotEmpty) {
      final first = dailyPlans.first;
      if (first is Map) {
        final t = first['totals'];
        if (t is Map) {
          final tm = Map<String, dynamic>.from(t);
          final m = _microMapFromJson(tm['micronutrients']);
          if (m.isNotEmpty) return m;
        }
      }
    }
    final microAcc = <String, double>{};
    for (final m in meals) {
      for (final e in m.nutrition.micronutrients.entries) {
        microAcc[e.key] = (microAcc[e.key] ?? 0) + e.value;
      }
    }
    return microAcc;
  }

  static NutritionProfile _sumMealNutrition(List<Meal> meals) {
    double c = 0, p = 0, f = 0, cb = 0;
    final microAcc = <String, double>{};
    for (final m in meals) {
      c += m.nutrition.calories;
      p += m.nutrition.proteinG;
      f += m.nutrition.fatG;
      cb += m.nutrition.carbsG;
      for (final e in m.nutrition.micronutrients.entries) {
        microAcc[e.key] = (microAcc[e.key] ?? 0) + e.value;
      }
    }
    return NutritionProfile(
      calories: c,
      proteinG: p,
      fatG: f,
      carbsG: cb,
      micronutrients: microAcc,
    );
  }

  static NutritionProfile _nutritionProfileFromDayTotalsMap(
      Map<String, dynamic> tm) {
    return NutritionProfile(
      calories: (tm['calories'] as num).toDouble(),
      proteinG: (tm['protein_g'] as num).toDouble(),
      fatG: (tm['fat_g'] as num).toDouble(),
      carbsG: (tm['carbs_g'] as num).toDouble(),
      micronutrients: _microMapFromJson(tm['micronutrients']),
    );
  }

  static NutritionProfile _dayTotalsFromApi(
    dynamic totals,
    List<Meal> dayMeals,
  ) {
    if (totals is Map &&
        totals['calories'] != null &&
        totals['protein_g'] != null) {
      return _nutritionProfileFromDayTotalsMap(
        Map<String, dynamic>.from(totals),
      );
    }
    return _sumMealNutrition(dayMeals);
  }

  static NutritionProfile _sumDayNutritionProfiles(List<MealPlanDay> days) {
    double c = 0, p = 0, f = 0, cb = 0;
    final microAcc = <String, double>{};
    for (final d in days) {
      c += d.dayTotals.calories;
      p += d.dayTotals.proteinG;
      f += d.dayTotals.fatG;
      cb += d.dayTotals.carbsG;
      for (final e in d.dayTotals.micronutrients.entries) {
        microAcc[e.key] = (microAcc[e.key] ?? 0) + e.value;
      }
    }
    return NutritionProfile(
      calories: c,
      proteinG: p,
      fatG: f,
      carbsG: cb,
      micronutrients: microAcc,
    );
  }

  /// `/api/v1/plan` JSON from [format_result_json] (`daily_plans`, `goals`, …).
  factory MealPlan.fromPlanApiV1Response(Map<String, dynamic> json) {
    final success = json['success'] as bool? ?? false;
    final dailyPlansRaw = json['daily_plans'] as List<dynamic>? ?? const [];
    final days = json['days'] as int? ?? 1;

    final schedule = <MealPlanDay>[];
    for (var i = 0; i < dailyPlansRaw.length; i++) {
      final day = dailyPlansRaw[i];
      if (day is! Map) continue;
      final dayMap = Map<String, dynamic>.from(day);
      final dayNum = (dayMap['day'] as num?)?.toInt() ?? i + 1;
      final mealList = dayMap['meals'] as List<dynamic>? ?? const [];
      final dayMeals = <Meal>[];
      for (final raw in mealList) {
        if (raw is Map) {
          dayMeals.add(Meal.fromPlanApiV1(Map<String, dynamic>.from(raw)));
        }
      }
      final dayTot = _dayTotalsFromApi(dayMap['totals'], dayMeals);
      schedule.add(
        MealPlanDay(day: dayNum, meals: dayMeals, dayTotals: dayTot),
      );
    }

    final allMeals = schedule.expand((d) => d.meals).toList();

    NutritionProfile macroTotals;
    if (days > 1 && json['weekly_totals'] is Map) {
      final wt = Map<String, dynamic>.from(json['weekly_totals'] as Map);
      if (wt['calories'] != null && wt['protein_g'] != null) {
        macroTotals = _nutritionProfileFromDayTotalsMap(wt);
      } else if (schedule.isNotEmpty) {
        macroTotals = _sumDayNutritionProfiles(schedule);
      } else {
        macroTotals = const NutritionProfile(
          calories: 0,
          proteinG: 0,
          fatG: 0,
          carbsG: 0,
        );
      }
    } else if (schedule.length == 1) {
      macroTotals = schedule.first.dayTotals;
    } else if (schedule.isNotEmpty) {
      macroTotals = _sumDayNutritionProfiles(schedule);
    } else {
      macroTotals = const NutritionProfile(
        calories: 0,
        proteinG: 0,
        fatG: 0,
        carbsG: 0,
      );
    }

    final micros =
        _planMicronutrientTotals(json, dailyPlansRaw, days, allMeals);
    final totalNutrition = NutritionProfile(
      calories: macroTotals.calories,
      proteinG: macroTotals.proteinG,
      fatG: macroTotals.fatG,
      carbsG: macroTotals.carbsG,
      micronutrients: micros,
    );

    final goalsRaw = json['goals'];
    if (goalsRaw is! Map) {
      throw const FormatException('Plan response missing goals');
    }
    final goals = NutritionGoals.fromPlanApi(
      Map<String, dynamic>.from(goalsRaw),
    );

    final w = json['warnings'];
    final warnings = formatPlanApiWarnings(w);

    final termination = json['termination_code'] as String?;

    final reportRaw = json['report'];
    final failures = <PlanFailure>[];
    PlanFailureCause? failureCause;
    if (reportRaw is Map) {
      final causeRaw = reportRaw['failure_cause'];
      if (causeRaw is Map) {
        failureCause =
            PlanFailureCause.fromJson(Map<String, dynamic>.from(causeRaw));
      }
      final failuresRaw = reportRaw['failures'];
      if (failuresRaw is List) {
        for (final f in failuresRaw) {
          if (f is Map) {
            failures.add(
              PlanFailure.fromJson(Map<String, dynamic>.from(f)),
            );
          }
        }
      }
    }

    final planStatusMessage = json['plan_status_message'] as String?;
    // Mirror formatters.py when plan_status is absent (old fixtures).
    String derivedPlanStatus;
    if (success && failures.isEmpty && planStatusMessage == null) {
      derivedPlanStatus = 'success';
    } else if (schedule.isNotEmpty) {
      derivedPlanStatus = 'partial';
    } else {
      derivedPlanStatus = 'failed';
    }
    final planStatus = json['plan_status'] as String? ?? derivedPlanStatus;

    return MealPlan(
      success: success,
      dailyPlans: schedule,
      totalNutrition: totalNutrition,
      goals: goals,
      warnings: warnings,
      days: days,
      planStatus: planStatus,
      planStatusMessage: planStatusMessage,
      failures: failures,
      failureCause: failureCause,
      terminationCode: termination,
    );
  }
}

class RecipeSummary {
  final String id;
  final String name;

  const RecipeSummary({
    required this.id,
    required this.name,
  });

  factory RecipeSummary.fromJson(Map<String, dynamic> json) {
    return RecipeSummary(
      id: json['id'] as String,
      name: json['name'] as String,
    );
  }
}
