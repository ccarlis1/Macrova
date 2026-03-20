import 'micronutrient_metadata.dart';

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

class PlanRequest {
  final int dailyCalories;
  final double dailyProteinG;
  final double dailyFatGMin;
  final double dailyFatGMax;
  final Map<String, int> schedule;
  final List<String> likedFoods;
  final List<String> dislikedFoods;
  final List<String> allergies;
  final int days;
  final String ingredientSource;
  final Map<String, double>? micronutrientGoals;
  final double micronutrientWeeklyMinFraction;
  final String? planningMode;
  final List<String>? recipeIds;

  const PlanRequest({
    required this.dailyCalories,
    required this.dailyProteinG,
    required this.dailyFatGMin,
    required this.dailyFatGMax,
    required this.schedule,
    this.likedFoods = const [],
    this.dislikedFoods = const [],
    this.allergies = const [],
    this.days = 1,
    this.ingredientSource = 'local',
    this.micronutrientGoals,
    this.micronutrientWeeklyMinFraction = 1.0,
    this.planningMode,
    this.recipeIds,
  });

  factory PlanRequest.fromJson(Map<String, dynamic> json) {
    return PlanRequest(
      dailyCalories: json['daily_calories'] as int,
      dailyProteinG: (json['daily_protein_g'] as num).toDouble(),
      dailyFatGMin: (json['daily_fat_g_min'] as num).toDouble(),
      dailyFatGMax: (json['daily_fat_g_max'] as num).toDouble(),
      schedule: Map<String, int>.from(json['schedule'] as Map),
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
      planningMode: json['planning_mode'] as String?,
      recipeIds: (json['recipe_ids'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{
      'daily_calories': dailyCalories,
      'daily_protein_g': dailyProteinG,
      'daily_fat_g_min': dailyFatGMin,
      'daily_fat_g_max': dailyFatGMax,
      'schedule': schedule,
      'liked_foods': likedFoods,
      'disliked_foods': dislikedFoods,
      'allergies': allergies,
      'days': days,
      'ingredient_source': ingredientSource,
      'micronutrient_weekly_min_fraction': micronutrientWeeklyMinFraction,
    };
    final micros = micronutrientGoals;
    if (micros != null && micros.isNotEmpty) {
      map['micronutrient_goals'] = micros;
    }
    if (planningMode != null && planningMode!.isNotEmpty) {
      map['planning_mode'] = planningMode;
    }
    final ids = recipeIds;
    if (ids != null && ids.isNotEmpty) {
      map['recipe_ids'] = ids;
    }
    return map;
  }
}

class NutritionProfile {
  final double calories;
  final double proteinG;
  final double fatG;
  final double carbsG;

  const NutritionProfile({
    required this.calories,
    required this.proteinG,
    required this.fatG,
    required this.carbsG,
  });

  factory NutritionProfile.fromJson(Map<String, dynamic> json) {
    return NutritionProfile(
      calories: (json['calories'] as num).toDouble(),
      proteinG: (json['protein_g'] as num).toDouble(),
      fatG: (json['fat_g'] as num).toDouble(),
      carbsG: (json['carbs_g'] as num).toDouble(),
    );
  }
}

class RecipeIngredient {
  final String name;
  final String unit;
  final String display;
  final double quantity;
  final bool isToTaste;

  const RecipeIngredient({
    required this.name,
    required this.unit,
    required this.display,
    required this.quantity,
    required this.isToTaste,
  });

  factory RecipeIngredient.fromJson(Map<String, dynamic> json) {
    return RecipeIngredient(
      name: json['name'] as String,
      unit: json['unit'] as String? ?? '',
      display: json['display'] as String? ?? '',
      quantity: (json['quantity'] as num).toDouble(),
      isToTaste: json['is_to_taste'] as bool? ?? false,
    );
  }
}

class Meal {
  final String mealType;
  final Map<String, dynamic> recipe;
  final NutritionProfile nutrition;
  final int busynessLevel;

  const Meal({
    required this.mealType,
    required this.recipe,
    required this.nutrition,
    required this.busynessLevel,
  });

  factory Meal.fromJson(Map<String, dynamic> json) {
    return Meal(
      mealType: json['meal_type'] as String,
      recipe: Map<String, dynamic>.from(json['recipe'] as Map),
      nutrition:
          NutritionProfile.fromJson(json['nutrition'] as Map<String, dynamic>),
      busynessLevel: json['busyness_level'] as int,
    );
  }

  /// One meal object from `POST /api/v1/plan` [`daily_plans[].meals`].
  factory Meal.fromPlanApiV1(Map<String, dynamic> m) {
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

  factory NutritionGoals.fromJson(Map<String, dynamic> json) {
    return NutritionGoals(
      calories: json['calories'] as int,
      proteinG: (json['protein_g'] as num).toDouble(),
      fatGMin: (json['fat_g_min'] as num).toDouble(),
      fatGMax: (json['fat_g_max'] as num).toDouble(),
      carbsG: (json['carbs_g'] as num).toDouble(),
    );
  }

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

class MealPlan {
  final bool success;
  final bool meetsGoals;
  final String date;
  final List<Meal> meals;
  final NutritionProfile totalNutrition;
  final NutritionGoals goals;
  final Map<String, double> targetAdherence;
  final List<String> warnings;

  const MealPlan({
    required this.success,
    required this.meetsGoals,
    required this.date,
    required this.meals,
    required this.totalNutrition,
    required this.goals,
    required this.targetAdherence,
    required this.warnings,
  });

  factory MealPlan.fromJson(Map<String, dynamic> json) {
    final adherenceRaw =
        Map<String, dynamic>.from(json['target_adherence'] as Map);
    return MealPlan(
      success: json['success'] as bool,
      meetsGoals: json['meets_goals'] as bool,
      date: json['date'] as String? ?? '',
      meals: (json['meals'] as List<dynamic>)
          .map((e) => Meal.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
      totalNutrition: NutritionProfile.fromJson(
        Map<String, dynamic>.from(json['total_nutrition'] as Map),
      ),
      goals: NutritionGoals.fromJson(
        Map<String, dynamic>.from(json['goals'] as Map),
      ),
      targetAdherence: adherenceRaw.map(
        (key, value) => MapEntry(key, (value as num).toDouble()),
      ),
      warnings: List<String>.from(json['warnings'] ?? const []),
    );
  }

  static NutritionProfile _sumMealNutrition(List<Meal> meals) {
    double c = 0, p = 0, f = 0, cb = 0;
    for (final m in meals) {
      c += m.nutrition.calories;
      p += m.nutrition.proteinG;
      f += m.nutrition.fatG;
      cb += m.nutrition.carbsG;
    }
    return NutritionProfile(
      calories: c,
      proteinG: p,
      fatG: f,
      carbsG: cb,
    );
  }

  static Map<String, double> _adherence(
    NutritionProfile actual,
    NutritionGoals goals,
  ) {
    double pct(double a, double t) {
      if (t <= 0) return 100;
      return (100 * a / t).clamp(0, 200).toDouble();
    }

    final fatMid = (goals.fatGMin + goals.fatGMax) / 2;
    return {
      'calories': pct(actual.calories, goals.calories.toDouble()),
      'protein': pct(actual.proteinG, goals.proteinG),
      'carbs': pct(actual.carbsG, goals.carbsG),
      'fat': pct(actual.fatG, fatMid),
    };
  }

  /// `/api/v1/plan` JSON from [format_result_json] (`daily_plans`, `goals`, …).
  factory MealPlan.fromPlanApiV1Response(Map<String, dynamic> json) {
    final success = json['success'] as bool? ?? false;
    final dailyPlans = json['daily_plans'] as List<dynamic>? ?? const [];
    final days = json['days'] as int? ?? 1;

    final meals = <Meal>[];
    for (final day in dailyPlans) {
      if (day is! Map) continue;
      final dayMap = Map<String, dynamic>.from(day);
      final mealList = dayMap['meals'] as List<dynamic>? ?? const [];
      for (final raw in mealList) {
        if (raw is Map) {
          meals.add(Meal.fromPlanApiV1(Map<String, dynamic>.from(raw)));
        }
      }
    }

    NutritionProfile totalNutrition;
    if (days == 1 && dailyPlans.isNotEmpty) {
      final first = dailyPlans.first;
      final totals = first is Map ? first['totals'] : null;
      if (totals is Map &&
          totals['calories'] != null &&
          totals['protein_g'] != null) {
        final tm = Map<String, dynamic>.from(totals);
        totalNutrition = NutritionProfile(
          calories: (tm['calories'] as num).toDouble(),
          proteinG: (tm['protein_g'] as num).toDouble(),
          fatG: (tm['fat_g'] as num).toDouble(),
          carbsG: (tm['carbs_g'] as num).toDouble(),
        );
      } else if (meals.isNotEmpty) {
        totalNutrition = _sumMealNutrition(meals);
      } else {
        totalNutrition = const NutritionProfile(
          calories: 0,
          proteinG: 0,
          fatG: 0,
          carbsG: 0,
        );
      }
    } else {
      totalNutrition = meals.isEmpty
          ? const NutritionProfile(
              calories: 0,
              proteinG: 0,
              fatG: 0,
              carbsG: 0,
            )
          : _sumMealNutrition(meals);
    }

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
    if (!success &&
        termination != null &&
        termination.isNotEmpty &&
        !warnings.any((s) => s.contains(termination))) {
      warnings.add('Planner ended with $termination');
    }

    return MealPlan(
      success: success,
      meetsGoals: success,
      date: '',
      meals: meals,
      totalNutrition: totalNutrition,
      goals: goals,
      targetAdherence: _adherence(totalNutrition, goals),
      warnings: warnings,
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
