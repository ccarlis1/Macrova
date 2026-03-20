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
